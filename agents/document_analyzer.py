"""
文書分析モジュール - アップロードされた文書の構造、コンテンツ、特性を分析し、構造化データを生成する
"""

import os
import re
import logging
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple, Union
from collections import Counter

import tiktoken
from langchain_google_genai import ChatGoogleGenerativeAI

# ドキュメント処理モジュールの関数をインポート
from agents.document_processor import count_tokens

# ログ設定
logger = logging.getLogger(__name__)

def analyze_document_structure(text: str) -> Dict[str, Any]:
    """
    文書の構造を分析して、セクション、段落、重要な要素などを特定する
    
    Args:
        text: 分析する文書のテキスト
        
    Returns:
        Dict: 文書構造の分析結果
    """
    structure = {
        "total_length": len(text),
        "estimated_tokens": count_tokens(text),
        "sections": [],
        "paragraph_count": 0,
        "potential_headers": [],
        "tabular_data": [],
        "lists": [],
        "key_terms": [],
        "metadata": {}
    }
    
    try:
        # 改行で分割して段落を特定
        paragraphs = [p for p in text.split('\n') if p.strip()]
        structure["paragraph_count"] = len(paragraphs)
        
        # ヘッダーのパターン検出（数字で始まるもの、短いもの、改行+スペースなし）
        header_patterns = [
            r'^\s*第[一二三四五六七八九十１２３４５６７８９０]+[章節項].*',  # 第一章、第二節など
            r'^\s*\d+[\.\-\s].*',  # 1. や 2- など数字で始まるもの
            r'^\s*[IVXivx]+[\.\s].*',  # I. や iv. などローマ数字
            r'^【.*】$',  # 【見出し】形式
            r'^［.*］$',  # ［見出し］形式
            r'^■.*$',  # ■マーク付き見出し
            r'^●.*$',  # ●マーク付き見出し
        ]
        
        current_section = None
        
        for i, para in enumerate(paragraphs):
            # 見出しかどうかをチェック
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, para):
                    is_header = True
                    # 見出しと思われるものを記録
                    structure["potential_headers"].append(para.strip())
                    # 新しいセクションを開始
                    current_section = {
                        "header": para.strip(),
                        "start_index": i,
                        "content": [],
                        "length": 0
                    }
                    structure["sections"].append(current_section)
                    break
                    
            # 表形式データの検出（|で囲まれた部分、カンマや区切り文字が規則的に現れる）
            if "|" in para and para.count("|") >= 2:
                structure["tabular_data"].append(para.strip())
            
            # リスト項目の検出
            list_patterns = [r'^\s*[\-\*•◦▪▫]', r'^\s*\d+[\.\)]', r'^\s*[a-zA-Zａ-ｚＡ-Ｚ][\.\)]']
            for pattern in list_patterns:
                if re.match(pattern, para):
                    if "lists" not in structure:
                        structure["lists"] = []
                    structure["lists"].append(para.strip())
                    break
            
            # 現在のセクションにコンテンツを追加
            if current_section is not None and not is_header:
                current_section["content"].append(para)
                current_section["length"] += len(para)
        
        # セクションがない場合（見出しが検出されなかった場合）
        if not structure["sections"]:
            structure["sections"].append({
                "header": "本文",
                "start_index": 0,
                "content": paragraphs,
                "length": len(text)
            })
        
        # 重要な用語を抽出（繰り返し出現する名詞や特殊な表現）
        # 簡易的な実装 - 実際には形態素解析などを使うとより精度が上がる
        words = re.findall(r'[一-龠ぁ-んァ-ヶー々a-zA-Z0-9]{2,}', text)
        word_count = Counter(words)
        # 出現回数の多い単語を抽出
        structure["key_terms"] = [word for word, count in word_count.most_common(20) if count > 1]
        
        # メタデータ（ファイルタイプの推測）
        if "===" in text and "シート" in text:
            structure["metadata"]["file_type"] = "Excel表計算"
        elif re.search(r'図\s*\d+', text) or re.search(r'表\s*\d+', text):
            structure["metadata"]["file_type"] = "レポート/論文"
        elif re.search(r'第\s*\d+\s*条', text):
            structure["metadata"]["file_type"] = "契約書/規約"
        
        return structure
        
    except Exception as e:
        logger.error(f"Error analyzing document structure: {str(e)}")
        return structure

def extract_document_metadata(text: str, filename: str = "") -> Dict[str, Any]:
    """
    文書からメタデータ（作成日、タイトル、著者など）を抽出
    
    Args:
        text: 文書本文
        filename: ファイル名（オプション）
        
    Returns:
        Dict: 抽出されたメタデータ
    """
    metadata = {
        "estimated_title": "",
        "possible_date": "",
        "detected_language": "ja",  # デフォルトは日本語
        "document_type": "",
        "key_entities": [],
        "file_extension": os.path.splitext(filename)[1].lower() if filename else ""
    }
    
    try:
        # 文書のサンプル（最初の部分）
        sample = text[:1000]
        
        # タイトルの推測（最初の行、または【】[]で囲まれた部分）
        first_line = text.split('\n')[0].strip()
        if first_line and len(first_line) < 100:
            metadata["estimated_title"] = first_line
        else:
            # 【】または[]内のテキストを探す
            title_match = re.search(r'【(.+?)】|\[(.+?)\]', sample)
            if title_match:
                metadata["estimated_title"] = title_match.group(1) or title_match.group(2)
        
        # 日付情報の検索
        date_patterns = [
            r'\d{4}[年/\-]\s*\d{1,2}[月/\-]\s*\d{1,2}日?',  # 2023年1月1日, 2023/1/1
            r'令和\d+年\d+月\d+日',  # 令和3年1月1日
            r'平成\d+年\d+月\d+日',  # 平成30年1月1日
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, sample)
            if date_match:
                metadata["possible_date"] = date_match.group(0)
                break
        
        # 文書タイプの推測
        document_types = {
            "報告書": ["報告", "レポート", "調査結果", "分析", "報告書"],
            "議事録": ["議事録", "会議", "打ち合わせ", "ミーティング"],
            "仕様書": ["仕様", "要件", "設計", "specification"],
            "マニュアル": ["マニュアル", "手順", "ガイド", "使い方"],
            "契約書": ["契約", "規約", "約款", "条項", "第○条"],
            "企画書": ["企画", "プロポーザル", "提案", "計画"],
            "データ分析": ["データ", "統計", "分析結果", "調査データ"]
        }
        
        # 各文書タイプのキーワードとマッチするか確認
        for doc_type, keywords in document_types.items():
            if any(keyword in text[:2000] for keyword in keywords):
                metadata["document_type"] = doc_type
                break
        
        # ファイル拡張子からもタイプを推測
        if metadata["file_extension"]:
            extension_types = {
                ".xlsx": "表計算データ",
                ".pdf": "PDF文書",
                ".docx": "ワード文書",
                ".txt": "テキスト文書"
            }
            if metadata["file_extension"] in extension_types:
                if not metadata["document_type"]:
                    metadata["document_type"] = extension_types[metadata["file_extension"]]
        
        # 重要なエンティティ（固有名詞や組織名など）の抽出
        entity_patterns = [
            r'株式会社[^\s\d]{2,}',  # 株式会社〇〇
            r'[^\s]{2,}株式会社',     # 〇〇株式会社
            r'[^\s]{2,}大学',        # 〇〇大学
            r'[^\s]{2,}協会',        # 〇〇協会
            r'[A-Z][A-Za-z]+\s*社',  # Alpha社 など
        ]
        
        for pattern in entity_patterns:
            for match in re.finditer(pattern, text):
                if match.group(0) not in metadata["key_entities"]:
                    metadata["key_entities"].append(match.group(0))
                    # 最大10個まで
                    if len(metadata["key_entities"]) >= 10:
                        break
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting document metadata: {str(e)}")
        return metadata

def analyze_document_content(text: str, api_key: str, model: str = "gemini-2.0-flash-lite", temperature: float = 0.0, max_output_tokens: int = 1024) -> Dict[str, Any]:
    """
    文書の内容を分析し、主要な情報、トピック、重要なポイントを抽出する
    
    Args:
        text: 文書テキスト
        api_key: Google Gemini API キー
        model (str): 使用するGeminiモデル名 (デフォルト: "gemini-2.0-flash-lite")
        temperature (float): 生成の温度パラメータ (0.0-1.0) (デフォルト: 0.0)
        max_output_tokens (int): 生成する最大トークン数 (デフォルト: 1024)
        
    Returns:
        Dict: 文書内容の分析結果
    """
    # 結果の初期化
    analysis = {
        "success": False,
        "summary": "",
        "main_topics": [],
        "key_points": [],
        "key_data": [],
        "recommendations": [],
        "analysis_details": ""
    }
    
    try:
        # テキストが短すぎる場合は分析しない
        if not text or len(text) < 100:
            analysis["summary"] = "テキストが短すぎるため、分析できません。"
            return analysis
            
        # テキストサンプルを準備（長すぎる場合は要約用に一部を使用）
        text_for_analysis = text
        if len(text) > 12000:
            # 先頭、中間、末尾から部分を抽出
            head = text[:4000]
            middle_start = len(text) // 2 - 2000
            middle = text[middle_start:middle_start + 4000]
            tail = text[-4000:]
            text_for_analysis = f"{head}\n...\n{middle}\n...\n{tail}"
            
        # Gemini モデルをセットアップ
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        # プロンプトを作成（日本語に特化）
        prompt = f"""
        以下の文書を分析し、その内容と構造を詳細に解析してください。
        分析結果は以下の形式で提供してください：
        
        1. 要約（3-5文で文書全体の内容を簡潔に要約）
        2. 主要トピック（文書から抽出された3-7個の主要なトピックをリスト）
        3. 重要ポイント（箇条書きで5-10個の重要な事実や主張）
        4. 重要データ（文書に含まれる重要な数値、統計、数量データを箇条書き。ない場合は「なし」）
        5. 文書分析（文書の目的、対象読者、全体的な特徴について2-3段落）
        
        必ず文書の内容に厳密に基づいた分析を行い、文書に存在しない情報や推測を含めないでください。
        重要ポイントやデータを挙げる際は、可能な限り元の文書の該当部分からの引用を「」で囲んで含めてください。
        
        [ここに分析する文書]
        {text_for_analysis}
        """
        
        # Gemini APIを呼び出す
        logger.info("Calling Gemini API for document content analysis")
        response = llm.invoke(prompt)
        analysis_text = response.content if hasattr(response, 'content') else str(response)
        
        # レスポンスをパースして構造化データに変換
        analysis["analysis_details"] = analysis_text
        
        # 1. 要約を抽出
        summary_match = re.search(r'1\.\s*要約.*?(?=2\.\s*主要トピック)', analysis_text, re.DOTALL)
        if summary_match:
            analysis["summary"] = summary_match.group(0).replace('1. 要約', '').strip()
        
        # 2. 主要トピックを抽出
        topics_match = re.search(r'2\.\s*主要トピック.*?(?=3\.\s*重要ポイント)', analysis_text, re.DOTALL)
        if topics_match:
            topics_text = topics_match.group(0).replace('2. 主要トピック', '').strip()
            topics = re.findall(r'[・\-\*]\s*(.*?)(?=$|[\n\r][・\-\*])', topics_text, re.DOTALL)
            if not topics:  # 別のフォーマットを試す
                topics = [line.strip() for line in topics_text.split('\n') if line.strip() and not line.startswith('2.')]
            analysis["main_topics"] = topics
        
        # 3. 重要ポイントを抽出
        points_match = re.search(r'3\.\s*重要ポイント.*?(?=4\.\s*重要データ)', analysis_text, re.DOTALL)
        if points_match:
            points_text = points_match.group(0).replace('3. 重要ポイント', '').strip()
            points = re.findall(r'[・\-\*]\s*(.*?)(?=$|[\n\r][・\-\*])', points_text, re.DOTALL)
            if not points:  # 別のフォーマットを試す
                points = [line.strip() for line in points_text.split('\n') if line.strip() and not line.startswith('3.')]
            analysis["key_points"] = points
        
        # 4. 重要データを抽出
        data_match = re.search(r'4\.\s*重要データ.*?(?=5\.\s*文書分析)', analysis_text, re.DOTALL)
        if data_match:
            data_text = data_match.group(0).replace('4. 重要データ', '').strip()
            if "なし" not in data_text:
                data_points = re.findall(r'[・\-\*]\s*(.*?)(?=$|[\n\r][・\-\*])', data_text, re.DOTALL)
                if not data_points:  # 別のフォーマットを試す
                    data_points = [line.strip() for line in data_text.split('\n') if line.strip() and not line.startswith('4.')]
                analysis["key_data"] = data_points
        
        # 分析成功
        analysis["success"] = True
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing document content: {str(e)}")
        # エラーが発生した場合でも、部分的な分析結果を返す
        if not analysis["summary"]:
            analysis["summary"] = "文書分析中にエラーが発生しました。"
        return analysis

def create_document_analysis_report(document_text: str, 
                                  filename: str, 
                                  api_key: str,
                                  language: str = "ja",
                                  model: str = "gemini-2.0-flash-lite",
                                  temperature: float = 0.0,
                                  max_output_tokens: int = 1024) -> Dict[str, Any]:
    """
    文書の総合的な分析レポートを作成する
    
    Args:
        document_text: 文書のテキスト内容
        filename: ファイル名
        api_key: Google Gemini API キー
        language: 出力言語（デフォルト: 日本語）
        model (str): 使用するGeminiモデル名 (デフォルト: "gemini-2.0-flash-lite")
        temperature (float): 生成の温度パラメータ (0.0-1.0) (デフォルト: 0.0)
        max_output_tokens (int): 生成する最大トークン数 (デフォルト: 1024)
        
    Returns:
        Dict: 分析レポート
    """
    report = {
        "success": False,
        "timestamp": datetime.datetime.now().isoformat(),
        "filename": filename,
        "filesize_bytes": len(document_text.encode('utf-8')),
        "structure": {},
        "metadata": {},
        "content_analysis": {},
        "summary": "",
        "error": ""
    }
    
    try:
        # 1. 文書構造の分析
        logger.info(f"Analyzing structure for document: {filename}")
        report["structure"] = analyze_document_structure(document_text)
        
        # 2. メタデータの抽出
        logger.info(f"Extracting metadata for document: {filename}")
        report["metadata"] = extract_document_metadata(document_text, filename)
        
        # 3. 内容の分析（APIを使用）
        logger.info(f"Analyzing content for document: {filename}")
        report["content_analysis"] = analyze_document_content(document_text, api_key, model, temperature, max_output_tokens)
        
        # 4. サマリーの作成
        if report["content_analysis"]["success"] and report["content_analysis"]["summary"]:
            report["summary"] = report["content_analysis"]["summary"]
        else:
            # 内容分析が失敗した場合は、構造分析に基づく基本的なサマリーを作成
            structure = report["structure"]
            metadata = report["metadata"]
            
            summary_parts = []
            if metadata["estimated_title"]:
                summary_parts.append(f"文書「{metadata['estimated_title']}」")
            else:
                summary_parts.append(f"文書「{filename}」")
                
            if metadata["document_type"]:
                summary_parts.append(f"（{metadata['document_type']}）")
                
            summary_parts.append(f"は{structure['paragraph_count']}段落、")
            
            if structure["sections"]:
                summary_parts.append(f"{len(structure['sections'])}セクションで構成されています。")
            else:
                summary_parts.append("構成されています。")
                
            if metadata["possible_date"]:
                summary_parts.append(f" 文書の日付は{metadata['possible_date']}です。")
                
            report["summary"] = "".join(summary_parts)
        
        report["success"] = True
        logger.info(f"Successfully created analysis report for document: {filename}")
        return report
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating document analysis report: {error_msg}")
        report["error"] = error_msg
        return report

def extract_key_information_for_rag(document_text: str, api_key: str, model: str = "gemini-2.0-flash-lite", temperature: float = 0.0, max_output_tokens: int = 1024) -> Dict[str, Any]:
    """
    RAG向けに文書から重要情報を抽出し、検索性を高める構造化データを作成する
    
    Args:
        document_text: 文書テキスト
        api_key: Google Gemini API キー
        model (str): 使用するGeminiモデル名 (デフォルト: "gemini-2.0-flash-lite")
        temperature (float): 生成の温度パラメータ (0.0-1.0) (デフォルト: 0.0)
        max_output_tokens (int): 生成する最大トークン数 (デフォルト: 1024)
        
    Returns:
        Dict: RAG向け構造化データ
    """
    rag_data = {
        "key_passages": [],
        "key_entities": [],
        "key_relationships": [],
        "key_concepts": [],
        "search_keywords": [],
        "success": False
    }
    
    try:
        # テキストが短すぎる場合は処理しない
        if not document_text or len(document_text) < 100:
            return rag_data
            
        # 1. 構造ベースのキーパッセージ抽出
        structure = analyze_document_structure(document_text)
        
        # セクションから重要パッセージを抽出
        if structure["sections"]:
            for section in structure["sections"]:
                # 各セクションの冒頭部分を重要パッセージとして追加
                if section["content"] and len(section["content"]) > 0:
                    first_para = section["content"][0]
                    if len(first_para) > 50:  # 十分な長さがある場合
                        rag_data["key_passages"].append({
                            "text": first_para,
                            "source": section["header"],
                            "importance": "high"
                        })
        
        # リストアイテムを重要パッセージとして追加
        if structure["lists"]:
            for i, list_item in enumerate(structure["lists"]):
                if i < 5:  # 最初の5つのリストアイテムのみ
                    rag_data["key_passages"].append({
                        "text": list_item,
                        "source": "リスト項目",
                        "importance": "medium"
                    })
        
        # 表形式データを重要パッセージとして追加
        if structure["tabular_data"]:
            for i, table_row in enumerate(structure["tabular_data"]):
                if i < 3:  # 最初の3つの表行のみ
                    rag_data["key_passages"].append({
                        "text": table_row,
                        "source": "表データ",
                        "importance": "high"
                    })
        
        # 2. メタデータから重要エンティティと検索キーワードを抽出
        metadata = extract_document_metadata(document_text)
        
        if metadata["key_entities"]:
            rag_data["key_entities"] = [{"name": entity, "type": "organization"} 
                                       for entity in metadata["key_entities"]]
        
        # 検索キーワードとして使用可能な用語を追加
        if structure["key_terms"]:
            rag_data["search_keywords"] = structure["key_terms"]
        
        # 3. 内容分析から重要概念を抽出
        if api_key:
            content_analysis = analyze_document_content(document_text, api_key, model, temperature, max_output_tokens)
            
            if content_analysis["success"]:
                # 主要トピックを重要概念として追加
                if content_analysis["main_topics"]:
                    rag_data["key_concepts"] = [{"name": topic, "relevance": "high"} 
                                               for topic in content_analysis["main_topics"]]
                
                # 重要ポイントを検索キーワードに追加
                if content_analysis["key_points"]:
                    # 各ポイントから要約文や重要単語を抽出
                    for point in content_analysis["key_points"]:
                        words = re.findall(r'[一-龠ぁ-んァ-ヶー々a-zA-Z0-9]{2,}', point)
                        important_words = [word for word in words if len(word) >= 2]
                        if important_words:
                            rag_data["search_keywords"].extend(important_words[:3])  # 各ポイントから最大3単語
        
        # 検索キーワードの重複を削除
        if rag_data["search_keywords"]:
            rag_data["search_keywords"] = list(set(rag_data["search_keywords"]))
        
        rag_data["success"] = True
        return rag_data
        
    except Exception as e:
        logger.error(f"Error extracting key information for RAG: {str(e)}")
        return rag_data