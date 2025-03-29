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
        
        # 一時ファイルとして保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
            file.save(temp_file.name)
            file_path = temp_file.name
            
            # テキスト抽出
            text = extract_text_from_file(file_path)
            
            if not text:
                result["message"] = "ファイルからテキストを抽出できませんでした。"
                return result
            
            # テキストを分割
            chunks = split_text(text)
            
            if not chunks:
                result["message"] = "テキストを適切に分割できませんでした。"
                return result
            
            # ベクトルストアを作成
            vector_store = create_vector_store(chunks, api_key)
            
            if not vector_store:
                result["message"] = "ベクトルストアの作成に失敗しました。"
                return result
            
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
        # より関連性の高い結果を取得するために、より多くの結果を検索して後でフィルタリング
        search_results = vector_store.similarity_search(query, k=top_k * 2)
        
        # 結果をフィルタリングと正規化
        filtered_results = []
        seen_content = set()
        
        for doc in search_results:
            content = doc.page_content.strip()
            
            # 重複を除外し、内容のある結果のみを含める
            if content and content not in seen_content and len(content) > 20:
                filtered_results.append(content)
                seen_content.add(content)
            
            # 必要な数の結果を得たら停止
            if len(filtered_results) >= top_k:
                break
        
        logger.info(f"検索クエリ「{query[:30]}...」に対して {len(filtered_results)} 件の関連ドキュメントを取得しました。")
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
        return ""
    
    # チャンクを重要度でソート (短すぎるチャンクや長すぎるチャンクは優先度を下げる)
    def chunk_importance(chunk):
        length = len(chunk)
        # 理想的な長さ: 100〜500文字
        if 100 <= length <= 500:
            return 2  # 高優先度
        elif 50 <= length <= 1000:
            return 1  # 中優先度
        else:
            return 0  # 低優先度
    
    # 重要度に基づいてチャンクをソート (降順)
    sorted_chunks = sorted(chunks, key=chunk_importance, reverse=True)
    
    # コンテキストの構築
    context = ""
    current_tokens = 0
    
    # まず高優先度のチャンクを追加
    for chunk in sorted_chunks:
        chunk_tokens = count_tokens(chunk)
        
        # トークン制限を超える場合はスキップ
        if current_tokens + chunk_tokens > max_tokens:
            continue
        
        # チャンクごとにセクション番号をつけて明確に区切る
        context += f"[情報{len(context.split('[情報'))}] " + chunk.strip() + "\n\n"
        current_tokens += chunk_tokens
    
    logger.info(f"合計 {len(sorted_chunks)} チャンクからコンテキストを作成しました。使用トークン: {current_tokens}/{max_tokens}")
    return context.strip()