"""
文書処理モジュール - ユーザーがアップロードした文書を処理し、RAGシステムとして利用する機能
"""

import os
import logging
import tempfile
from typing import List, Dict, Union, Optional

# ドキュメント処理用のライブラリ
import PyPDF2
from docx import Document
import pandas as pd
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# ログ設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# サポートされるファイル形式
SUPPORTED_FORMATS = ['.pdf', '.txt', '.docx', '.xlsx']

def count_tokens(text: str) -> int:
    """テキストのトークン数をカウントする"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Failed to count tokens: {str(e)}")
        # 文字数から大まかに推定（日本語の場合）
        return len(text) // 2

def extract_text_from_pdf(file_path: str) -> str:
    """PDFからテキストを抽出する"""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        return ""

def extract_text_from_docx(file_path: str) -> str:
    """DOCXからテキストを抽出する"""
    try:
        doc = Document(file_path)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX: {str(e)}")
        return ""

def extract_text_from_txt(file_path: str) -> str:
    """TXTファイルからテキストを抽出する"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # UTF-8でデコードできない場合はSJISなど他のエンコーディングを試す
        try:
            with open(file_path, 'r', encoding='shift_jis') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Failed to extract text from TXT: {str(e)}")
            return ""
    except Exception as e:
        logger.error(f"Failed to extract text from TXT: {str(e)}")
        return ""

def extract_text_from_xlsx(file_path: str) -> str:
    """Excelファイル（.xlsx）からテキストを抽出する"""
    try:
        # Excelファイルを読み込む
        excel_data = pd.read_excel(file_path, sheet_name=None)
        text = ""
        
        # すべてのシートを処理
        for sheet_name, sheet_data in excel_data.items():
            text += f"=== シート: {sheet_name} ===\n\n"
            
            # 数値データを含む列を文字列に変換
            sheet_data = sheet_data.astype(str)
            
            # 列名（ヘッダー）を追加
            headers = sheet_data.columns.tolist()
            text += "| " + " | ".join(headers) + " |\n"
            text += "| " + " | ".join(["---" for _ in headers]) + " |\n"
            
            # 各行のデータを追加
            for _, row in sheet_data.iterrows():
                text += "| " + " | ".join(row.values) + " |\n"
            
            text += "\n\n"
        
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from XLSX: {str(e)}")
        return ""

def extract_text_from_file(file_path: str) -> str:
    """ファイルの拡張子に基づいてテキスト抽出関数を選択する"""
    extension = os.path.splitext(file_path)[1].lower()
    
    if extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif extension == '.docx':
        return extract_text_from_docx(file_path)
    elif extension == '.txt':
        return extract_text_from_txt(file_path)
    elif extension == '.xlsx':
        return extract_text_from_xlsx(file_path)
    else:
        logger.error(f"Unsupported file format: {extension}")
        return ""

def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """テキストを意味のあるチャンクに分割する"""
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=count_tokens,
            separators=["\n\n", "\n", "。", "、", " ", ""]
        )
        return text_splitter.split_text(text)
    except Exception as e:
        logger.error(f"Failed to split text: {str(e)}")
        return [text]

def create_vector_store(chunks: List[str], api_key: str) -> Optional[FAISS]:
    """テキストチャンクからベクトルストアを作成する"""
    try:
        # Gemini-2.0-flash-lite モデルに最適化したエンベディング設定
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=api_key,
            task_type="retrieval_query",
            dimensions=768  # Gemini エンベディングに適した次元数
        )
        
        # より多くのRAGコンテキストを提供するために、チャンクごとにメタデータを追加
        texts_with_metadata = []
        for i, chunk in enumerate(chunks):
            # 各チャンクに意味のある識別子とメタデータを付与
            metadata = {
                "chunk_id": f"chunk_{i}",
                "priority": "high",
                "token_count": count_tokens(chunk)
            }
            texts_with_metadata.append((chunk, metadata))
        
        # メタデータ付きでベクトルストアを作成
        vector_store = FAISS.from_texts(
            [t[0] for t in texts_with_metadata],
            embeddings,
            metadatas=[t[1] for t in texts_with_metadata]
        )
        
        logger.info(f"成功: ベクトルストアを作成しました。チャンク数: {len(chunks)}")
        return vector_store
    except Exception as e:
        logger.error(f"Failed to create vector store: {str(e)}")
        return None

def process_uploaded_file(file, api_key: str) -> Dict[str, Union[bool, str, FAISS]]:
    """
    アップロードされたファイルを処理し、ベクトルストアを作成する
    
    Args:
        file: Flaskのアップロードファイルオブジェクト
        api_key: Google APIキー
        
    Returns:
        Dict: 処理結果と生成されたベクトルストア
    """
    result = {
        "success": False,
        "message": "",
        "vector_store": None,
        "text_content": ""
    }
    
    try:
        # ファイル名と拡張子をチェック
        filename = file.filename
        extension = os.path.splitext(filename)[1].lower()
        
        if extension not in SUPPORTED_FORMATS:
            result["message"] = f"サポートされていないファイル形式です。サポート形式: {', '.join(SUPPORTED_FORMATS)}"
            return result
        
        logger.info(f"Processing file: {filename} (type: {extension})")
        
        # 一時ファイルとして保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            file.save(temp_file.name)
            file_path = temp_file.name
            
            # テキスト抽出
            text = extract_text_from_file(file_path)
            
            if not text:
                result["message"] = "ファイルからテキストを抽出できませんでした。"
                logger.error(f"Failed to extract text from {filename}")
                return result
            
            logger.info(f"Successfully extracted {len(text)} characters from {filename}")
            
            # 文書内容のサンプルをログに記録（デバッグ用）
            if len(text) > 200:
                sample_text = text[:200] + "..."
            else:
                sample_text = text
            logger.info(f"Sample text from document: {sample_text}")
            
            # テキストを分割
            chunks = split_text(text)
            
            if not chunks:
                result["message"] = "テキストを適切に分割できませんでした。"
                logger.error("Failed to split text into chunks")
                return result
            
            logger.info(f"Text split into {len(chunks)} chunks")
            
            # ベクトルストアを作成
            vector_store = create_vector_store(chunks, api_key)
            
            if not vector_store:
                result["message"] = "ベクトルストアの作成に失敗しました。"
                logger.error("Failed to create vector store")
                return result
            
            logger.info(f"Successfully created vector store with {len(chunks)} chunks")
            
            # 成功
            result["success"] = True
            result["message"] = f"ファイル '{filename}' を正常に処理しました。"
            result["vector_store"] = vector_store
            result["text_content"] = text
            
    except Exception as e:
        result["message"] = f"ファイル処理中にエラーが発生しました: {str(e)}"
        logger.error(f"File processing error: {str(e)}")
    
    finally:
        # 一時ファイルを削除（存在する場合）
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")
    
    return result

def search_documents(vector_store: FAISS, query: str, top_k: int = 3) -> List[str]:
    """
    検索クエリに対して関連するドキュメントチャンクを取得する
    
    Args:
        vector_store: FAISSベクトルストア
        query: 検索クエリ
        top_k: 取得する結果の数
        
    Returns:
        List[str]: 関連するテキストチャンクのリスト
    """
    try:
        logger.info(f"Searching for documents relevant to: '{query}'")
        
        # より関連性の高い結果を取得するために、より多くの結果を検索して後でフィルタリング
        # 文書が短い場合は、もっと多くの結果を取得して結合する可能性がある
        expanded_top_k = max(top_k * 3, 15)  # より多くの候補を取得
        
        search_results = vector_store.similarity_search(query, k=expanded_top_k)
        logger.info(f"Retrieved {len(search_results)} initial results for query")
        
        # 結果をフィルタリングと正規化
        filtered_results = []
        seen_content = set()
        
        for doc in search_results:
            content = doc.page_content.strip()
            
            # 重複を除外し、内容のある結果のみを含める
            if content and content not in seen_content and len(content) > 20:
                # メタデータがある場合はログに記録
                if hasattr(doc, 'metadata') and doc.metadata:
                    metadata_str = str(doc.metadata)
                    logger.info(f"Document metadata: {metadata_str}")
                
                # 内容の一部をログに記録
                content_preview = content[:100] + "..." if len(content) > 100 else content
                logger.info(f"Adding relevant chunk: {content_preview}")
                
                filtered_results.append(content)
                seen_content.add(content)
            
            # 必要な数の結果を得たら停止
            if len(filtered_results) >= top_k:
                break
        
        # 十分な結果が得られない場合、追加の取得を試みる
        if len(filtered_results) < top_k / 2 and top_k > 2:
            logger.warning(f"Retrieved only {len(filtered_results)} relevant results, less than expected")
            
            # 検索クエリの拡張を試みる
            expanded_query = f"{query} 重要 情報 データ 分析"
            logger.info(f"Trying with expanded query: '{expanded_query}'")
            
            additional_results = vector_store.similarity_search(expanded_query, k=top_k)
            
            for doc in additional_results:
                content = doc.page_content.strip()
                if content and content not in seen_content and len(content) > 20:
                    filtered_results.append(content)
                    seen_content.add(content)
                
                if len(filtered_results) >= top_k:
                    break
        
        if filtered_results:
            logger.info(f"Successfully retrieved {len(filtered_results)} relevant document chunks")
            # サンプルとして最初のチャンクの一部をログに記録
            sample = filtered_results[0][:100] + "..." if len(filtered_results[0]) > 100 else filtered_results[0]
            logger.info(f"Sample content: {sample}")
        else:
            logger.warning("No relevant document chunks found for the query")
        
        return filtered_results
        
    except Exception as e:
        logger.error(f"ドキュメント検索エラー: {str(e)}")
        return []

def create_context_from_documents(chunks: List[str], max_tokens: int = 2000) -> str:
    """
    ドキュメントチャンクからコンテキスト文字列を作成する
    
    Args:
        chunks: テキストチャンクのリスト
        max_tokens: コンテキストの最大トークン数
        
    Returns:
        str: コンテキスト文字列
    """
    if not chunks:
        logger.warning("No document chunks provided for context creation")
        return ""
    
    logger.info(f"Creating context from {len(chunks)} document chunks (max tokens: {max_tokens})")
    
    # チャンクの品質と関連性を評価する関数
    def chunk_quality(chunk):
        length = len(chunk)
        
        # 基本スコア - 長さに基づく
        if 100 <= length <= 800:
            base_score = 3  # 最適な長さ
        elif 50 <= length <= 1200:
            base_score = 2  # 許容範囲
        else:
            base_score = 1  # 短すぎるか長すぎる
        
        # 追加のヒューリスティック - 数値データを含むチャンクを優先
        has_numbers = any(c.isdigit() for c in chunk)
        has_percentage = "%" in chunk
        has_tables = "\t" in chunk or "|" in chunk or "表" in chunk
        
        # 特定のキーワードを含むチャンクも優先
        important_keywords = ["重要", "課題", "分析", "結果", "データ", "調査", "結論"]
        keyword_score = sum(1 for keyword in important_keywords if keyword in chunk)
        
        # 最終スコアの計算
        additional_score = sum([
            2 if has_numbers else 0,
            1 if has_percentage else 0,
            2 if has_tables else 0,
            min(3, keyword_score)  # キーワードスコアは最大3とする
        ])
        
        return base_score + additional_score
    
    # 優先順位に基づいてチャンクをソート
    prioritized_chunks = sorted(chunks, key=chunk_quality, reverse=True)
    
    # より良いコンテキスト作成のために、チャンクに識別子を追加
    # 同時にサンプルをログに記録
    if prioritized_chunks:
        sample_chunk = prioritized_chunks[0]
        preview = sample_chunk[:100] + "..." if len(sample_chunk) > 100 else sample_chunk
        logger.info(f"Top priority chunk: {preview}")
    
    # コンテキストの構築
    context = ""
    current_tokens = 0
    added_chunks = 0
    
    for i, chunk in enumerate(prioritized_chunks):
        chunk_tokens = count_tokens(chunk)
        
        # トークン制限をチェック
        if current_tokens + chunk_tokens > max_tokens:
            # 最優先チャンクの場合は部分的に含める
            if i < 3 and current_tokens < max_tokens * 0.7:
                # より重要なチャンクの場合は、トークン制限内に収まるように部分的に含める
                available_tokens = max_tokens - current_tokens - 50  # バッファを残す
                if available_tokens > 200:  # 少なくとも200トークンが使える場合
                    truncated_chunk = chunk[:int(len(chunk) * (available_tokens / chunk_tokens))]
                    context += f"[文書セクション {added_chunks+1}] {truncated_chunk.strip()} [...続き省略]\n\n"
                    current_tokens += count_tokens(truncated_chunk) + 20  # 見出し分も追加
                    added_chunks += 1
            continue
        
        # チャンクに識別子を追加して区別しやすくする
        context += f"[文書セクション {added_chunks+1}] {chunk.strip()}\n\n"
        current_tokens += chunk_tokens + 20  # 見出し分も追加
        added_chunks += 1
    
    if added_chunks == 0:
        logger.warning("Could not add any chunks to context due to token limit constraints")
        # 最小限のコンテキストを提供
        if chunks:
            first_chunk = chunks[0]
            truncated = first_chunk[:min(len(first_chunk), 500)]
            context = f"[文書抜粋] {truncated.strip()} [...トークン制限のため省略]\n\n"
    
    logger.info(f"Created context with {added_chunks} chunks, using approximately {current_tokens} tokens")
    return context.strip()