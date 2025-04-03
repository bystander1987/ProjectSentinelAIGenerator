import os
import logging
import tempfile
import time
import json
import pickle
import hashlib
import uuid
import codecs
from flask import Flask, render_template, request, jsonify, session, url_for
from agents.discussion import (
    generate_discussion, get_gemini_model, summarize_discussion,
    provide_discussion_guidance, continue_discussion, generate_next_turn
)
from agents.document_processor import process_uploaded_file, SUPPORTED_FORMATS
from agents.action_items import generate_action_items

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 一時保存ディレクトリの設定
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'multirai_sessions')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)

def get_session_file_path(file_type: str) -> str:
    """セッションID（またはユーザー固有のID）に基づいたファイルパスを生成する"""
    # セッションIDがない場合は新しいIDを生成
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user_id = session['user_id']
    # セッションIDをハッシュ化してファイル名に使用（安全対策）
    hashed_id = hashlib.md5(user_id.encode()).hexdigest()
    
    # ファイルタイプに応じたパスを返す
    return os.path.join(TEMP_DIR, f"{hashed_id}_{file_type}.json")
    
def save_large_session_data(data, file_type: str) -> bool:
    """大きなセッションデータをファイルに保存する"""
    try:
        file_path = get_session_file_path(file_type)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving session data to file: {str(e)}")
        return False
        
def load_large_session_data(file_type: str) -> dict:
    """ファイルからセッションデータを読み込む"""
    try:
        file_path = get_session_file_path(file_type)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading session data from file: {str(e)}")
    return {}

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/process-json-file', methods=['POST'])
def process_json_file():
    """サーバー側でJSONファイルを処理する"""
    import os
    import json
    import codecs
    
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルが選択されていません。'}), 400
            
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません。'}), 400
    
    # 拡張子の確認
    filename = file.filename
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext != '.json':
        return jsonify({'error': 'JSONファイル（.json）のみサポートしています。'}), 400
    
    # 複数のエンコーディングを試す
    content = None
    result = {'success': False, 'error': 'すべてのエンコーディングでの読み込みに失敗しました。'}
    
    # 一時ファイルとして保存
    temp_path = os.path.join('/tmp', 'uploaded_json.json')
    file.save(temp_path)
    
    # 複数のエンコーディングで試行
    encodings = ['utf-8', 'shift-jis', 'euc-jp', 'cp932']
    
    for encoding in encodings:
        try:
            with codecs.open(temp_path, 'r', encoding=encoding) as f:
                content = f.read()
                
            # JSONとして解析を試みる
            data = json.loads(content)
            
            # 成功した場合
            result = {
                'success': True,
                'encoding': encoding,
                'data': data
            }
            
            # 一つでも成功したら終了
            break
            
        except UnicodeDecodeError:
            # このエンコーディングでは読めなかった
            continue
        except json.JSONDecodeError as e:
            # エンコーディングは正しいがJSONパース失敗
            result = {
                'success': False,
                'error': f'JSONパースエラー: {str(e)}',
                'encoding': encoding
            }
    
    # 一時ファイルを削除
    if os.path.exists(temp_path):
        os.remove(temp_path)
        
    return jsonify(result)

@app.route('/')
def index():
    """Render the main page of the application."""
    # ページリロード時にドキュメントセッションを検証
    # パス検索パラメータに 'reset=true' がある場合は完全リセット
    if request.args.get('reset') == 'true':
        logger.info("Reset parameter detected, performing full session reset")
        try:
            # セッションを完全クリア
            session.clear()
            
            # 必要な場合は特定の一時ファイルも削除
            try:
                import os
                import tempfile
                import glob
                import shutil
                
                # ドキュメント分析用の一時ディレクトリクリア
                temp_dir = os.path.join(tempfile.gettempdir(), 'document_analysis')
                if os.path.exists(temp_dir):
                    for file_path in glob.glob(os.path.join(temp_dir, "*.json")):
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                logger.info(f"Reset mode: Removed temporary file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Error removing temporary file {file_path}: {str(e)}")
            except Exception as cleanup_error:
                logger.error(f"Error during reset cleanup: {str(cleanup_error)}")
        except Exception as e:
            logger.error(f"Error during session reset: {str(e)}")
    
    # document_uploaded フラグが不正にセットされている可能性があるため検証
    # テキストがなければ強制的にフラグをリセットする
    if session.get('document_uploaded', False):
        document_text = session.get('document_text', '')
        if not document_text or not isinstance(document_text, str) or len(document_text) == 0:
            # 不整合を検出: テキストがないのにフラグが立っている
            logger.warning("Inconsistent document session state detected: flag is set but text is missing")
            session['document_uploaded'] = False
            # 関連するセッションキーもクリア
            for key in ['document_text', 'document_name', 'document_analysis', 'document_rag_data']:
                if key in session:
                    session.pop(key, None)
    
    # セッション変更を確実に保存
    session.modified = True
    
    # メインページをレンダリング
    return render_template('index.html')

@app.route('/generate-discussion', methods=['POST'])
def create_discussion():
    """Generate a discussion based on the roles and topic provided."""
    try:
        logger.info("Received discussion generation request")
        
        # リクエストデータの取得
        data = request.json
        topic = data.get('topic', '')
        num_turns = int(data.get('num_turns', 3))
        roles = data.get('roles', [])
        language = data.get('language', 'ja')  # デフォルトを日本語に変更
        
        # リクエストデータのログ（機密情報は除く）
        logger.info(f"Request data: topic='{topic}', num_turns={num_turns}, roles_count={len(roles)}, language='{language}'")
        
        # 入力検証と長さの制限
        if not topic:
            logger.warning("Empty topic provided")
            return jsonify({'error': '議題を入力してください'}), 400
            
        # トピックの長さを制限してメモリ使用量を抑制
        if len(topic) > 100:
            logger.warning(f"Topic too long: {len(topic)} chars, truncating")
            topic = topic[:97] + '...'
        
        if not roles or len(roles) < 2:
            logger.warning(f"Insufficient roles: {len(roles)}")
            return jsonify({'error': '少なくとも2つの役割が必要です'}), 400
            
        # 各役割の長さを制限してメモリ使用量を抑制
        for i, role in enumerate(roles):
            if len(role) > 50:
                logger.warning(f"Role too long: {len(role)} chars, truncating")
                roles[i] = role[:47] + '...'
            
        if num_turns < 1 or num_turns > 10:
            logger.warning(f"Invalid turn count: {num_turns}")
            return jsonify({'error': 'ターン数は1から10の間で指定してください'}), 400
        
        # より厳格なリソース制限
        total_requests = len(roles) * num_turns
        
        # ロール数の制限を緩和
        if len(roles) > 6:
            logger.warning(f"Too many roles: {len(roles)}")
            return jsonify({'error': 'メモリ使用量削減のため、役割は最大6つまでしか指定できません。'}), 400
            
        # ターン数の上限をさらに緩和
        if num_turns > 10:
            logger.warning(f"Too many turns: {num_turns}")
            return jsonify({'error': 'メモリ使用量削減のため、ターン数は最大10までしか指定できません。'}), 400
            
        # 総リクエスト数の制限をさらに緩和
        if total_requests > 30:  # 非常に緩いリソース使用量の閾値
            logger.warning(f"Very high resource request detected: {total_requests} total LLM calls")
            return jsonify({'error': 'リソース制限のため、役割数×ターン数の組み合わせが大きすぎます。役割数またはターン数を減らしてください。'}), 400
        # 高リソース使用量の場合は警告のみ
        elif total_requests > 20:
            logger.warning(f"High resource request detected: {total_requests} total LLM calls, proceeding anyway")
        
        # 環境変数からAPIキーを取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found in environment variables")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
            
        # Geminiモデルを初期化してAPIキーの有効性を確認
        try:
            logger.info("Initializing Gemini model to validate API key")
            get_gemini_model(api_key, language)
            logger.info("API key validation successful")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to initialize Gemini model: {error_msg}")
            
            if "quota" in error_msg.lower() or "429" in error_msg or "rate" in error_msg.lower():
                logger.error("API rate limit or quota exceeded")
                return jsonify({'error': 'APIのリクエスト制限に達しました。しばらく待ってから再試行してください。'}), 429
            elif "key" in error_msg.lower() or "auth" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                logger.error("API authentication error")
                return jsonify({'error': 'APIキーが無効です。有効なAPIキーを設定してください。'}), 401
            else:
                logger.error(f"Unknown API initialization error: {error_msg}")
                return jsonify({'error': 'AIモデルの初期化に失敗しました: ' + error_msg}), 500
        
        # ディスカッションを生成
        logger.info(f"Starting discussion generation for topic: {topic}")
        discussion_data = generate_discussion(
            api_key=api_key,
            topic=topic,
            roles=roles,
            num_turns=num_turns,
            language=language
        )
        
        logger.info(f"Successfully generated discussion with {len(discussion_data)} messages")
        return jsonify({'discussion': discussion_data})
    
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating discussion: {error_message}")
        
        # クライアントに返すエラーメッセージを分類
        if "timeout" in error_message.lower() or "time" in error_message.lower():
            return jsonify({'error': 'リクエストがタイムアウトしました。少ないロール数やターン数で再試行してください。'}), 504
        elif "memory" in error_message.lower():
            return jsonify({'error': 'メモリ制限エラー：少ないロール数や少ないターン数でお試しください。'}), 500
        else:
            return jsonify({'error': f'{error_message}'}), 500

@app.route('/upload-document', methods=['POST'])
def upload_document():
    """ファイルをアップロードして処理する"""
    try:
        logger.info("Document upload request received")
        # グローバルインポートを使用
        import os
        
        # ファイルが存在するか確認
        if 'file' not in request.files:
            logger.warning("No file part in the request")
            return jsonify({'error': 'ファイルが選択されていません。'}), 400
            
        file = request.files['file']
        
        # ファイル名が空でないか確認
        if file.filename == '':
            logger.warning("No file selected")
            return jsonify({'error': 'ファイルが選択されていません。'}), 400
            
        # ファイル拡張子の確認
        filename = file.filename
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in SUPPORTED_FORMATS:
            logger.warning(f"Unsupported file format: {file_ext}")
            return jsonify({'error': f'サポートされていないファイル形式です。サポート形式: {", ".join(SUPPORTED_FORMATS)}'}), 400
            
        # APIキーを取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found for document processing")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
            
        # ファイルを処理
        logger.info(f"Processing uploaded file: {filename}")
        result = process_uploaded_file(file, api_key)
        
        if not result['success']:
            logger.error(f"Failed to process document: {result['message']}")
            return jsonify({'error': result['message']}), 400
            
        # 重要な問題: セッションクッキーのサイズ制限
        # テキストをセッションに直接保存するとクッキーサイズが大きくなりすぎる問題があるため、
        # 一時ファイルに保存するよう変更
        try:
            import os
            import tempfile
            import uuid
            
            # 一時ファイルのパスを構築
            temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
            os.makedirs(temp_dir, exist_ok=True)
            
            # 一意のIDを生成
            document_id = str(uuid.uuid4())
            
            # ドキュメントテキストをファイルに保存
            document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
            with open(document_file_path, 'w', encoding='utf-8') as f:
                f.write(result['text_content'])
            
            # セッションにはファイルへの参照のみを保存
            session['document_id'] = document_id
            session['document_uploaded'] = True
            session['document_name'] = filename
            
            logger.info(f"Document text saved to temporary file: {document_file_path}")
            
            # 文書の概要情報も保存（最初の300文字程度に制限）
            document_summary = result['text_content'][:300] + "..." if len(result['text_content']) > 300 else result['text_content']
            session['document_summary'] = document_summary
        except Exception as file_error:
            logger.error(f"Error saving document to temporary file: {str(file_error)}")
            # エラー発生時は直接セッションに保存を試みる（リスク承知）
            session['document_text'] = result['text_content']
            session['document_uploaded'] = True
            session['document_name'] = filename
        
        # 文書分析を自動的に開始する
        has_analysis = False
        try:
            logger.info(f"Starting automatic document analysis for: {filename}")
            # 文書分析モジュールを動的にインポート
            from agents.document_analyzer import create_document_analysis_report
            
            # モデル設定を取得
            settings = request.json.get('settings', {})
            model = settings.get('model', 'gemini-2.0-flash-lite')
            temperature = float(settings.get('temperature', 0.0))
            max_output_tokens = int(settings.get('max_output_tokens', 1024))
            
            # 文書分析を実行
            analysis_report = create_document_analysis_report(
                document_text=result['text_content'],
                filename=filename,
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
            
            if analysis_report and analysis_report.get('success'):
                logger.info(f"Document analysis successful, storing results in session")
                # 分析結果を一時ファイルに保存（セッションサイズを小さく保つため）
                import os
                import json
                import tempfile
                import uuid
                
                # 一時ディレクトリのパスを確保
                temp_dir = os.path.join(tempfile.gettempdir(), 'document_analysis')
                os.makedirs(temp_dir, exist_ok=True)
                
                # 一意のIDを生成
                analysis_id = str(uuid.uuid4())
                
                # 分析データをJSONとして保存
                analysis_file_path = os.path.join(temp_dir, f"{analysis_id}.json")
                
                # 分析データを構築
                analysis_data = {
                    'summary': analysis_report.get('summary', ''),
                    'metadata': analysis_report.get('metadata', {}),
                    'structure': {
                        'paragraph_count': analysis_report.get('structure', {}).get('paragraph_count', 0),
                        'sections_count': len(analysis_report.get('structure', {}).get('sections', [])),
                        'key_terms': analysis_report.get('structure', {}).get('key_terms', [])[:10]
                    }
                }
                
                # RAG用のデータを追加
                if analysis_report.get('content_analysis', {}).get('success'):
                    from agents.document_analyzer import extract_key_information_for_rag
                    rag_data = extract_key_information_for_rag(
                        result['text_content'], 
                        api_key,
                        model=model,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens
                    )
                    if rag_data and rag_data.get('success'):
                        logger.info(f"RAG optimization data successfully extracted")
                        analysis_data['rag_data'] = {
                            'key_concepts': rag_data.get('key_concepts', [])[:5],
                            'search_keywords': rag_data.get('search_keywords', [])[:10]
                        }
                
                # ファイルに保存
                with open(analysis_file_path, 'w', encoding='utf-8') as f:
                    json.dump(analysis_data, f, ensure_ascii=False, indent=2)
                
                # ファイルへの参照だけをセッションに保存（軽量化）
                session['document_analysis_id'] = analysis_id
                has_analysis = True
                
                logger.info(f"Analysis data saved to temporary file: {analysis_file_path}")
            else:
                logger.warning(f"Document analysis failed: {analysis_report.get('error', '不明なエラー')}")
        except Exception as analysis_error:
            logger.error(f"Error during document analysis: {str(analysis_error)}")
            # 分析エラーは処理を中断しない
        
        logger.info(f"Document successfully processed and stored in session: {filename}")
        return jsonify({
            'success': True,
            'message': result['message'],
            'filename': filename,
            'has_analysis': has_analysis
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error processing document: {error_message}")
        return jsonify({'error': f'ファイル処理中にエラーが発生しました: {error_message}'}), 500


@app.route('/generate-discussion-with-document', methods=['POST'])
def create_discussion_with_document():
    """ドキュメントの参照情報を使用して議論を生成する"""
    try:
        logger.info("Received discussion generation request with document")
        # グローバルインポートを使用
        import os
        
        # セッションに保存されたドキュメントをチェック
        if not session.get('document_uploaded', False):
            logger.warning("No document uploaded in session")
            return jsonify({'error': '参照ドキュメントがアップロードされていません。先にドキュメントをアップロードしてください。'}), 400
            
        # リクエストデータの取得
        data = request.json
        base_topic = data.get('topic', '')
        num_turns = int(data.get('num_turns', 3))
        roles = data.get('roles', [])
        language = data.get('language', 'ja')
        
        # モデル設定の取得
        model = data.get('model', 'gemini-2.0-flash-lite')
        temperature = float(data.get('temperature', 0.7))
        max_output_tokens = int(data.get('maxOutputTokens', 1024))
        
        # 基本的な検証（通常の議論生成と同じ）
        if not base_topic:
            return jsonify({'error': '議題を入力してください'}), 400
        
        if not roles or len(roles) < 2:
            return jsonify({'error': '少なくとも2つの役割が必要です'}), 400
            
        for i, role in enumerate(roles):
            if len(role) > 50:
                roles[i] = role[:47] + '...'
            
        if num_turns < 1 or num_turns > 10:
            return jsonify({'error': 'ターン数は1から10の間で指定してください'}), 400
        
        total_requests = len(roles) * num_turns
        
        if len(roles) > 6:
            return jsonify({'error': 'メモリ使用量削減のため、役割は最大6つまでしか指定できません。'}), 400
            
        if num_turns > 10:
            return jsonify({'error': 'メモリ使用量削減のため、ターン数は最大10までしか指定できません。'}), 400
            
        if total_requests > 30:
            return jsonify({'error': 'リソース制限のため、役割数×ターン数の組み合わせが大きすぎます。役割数またはターン数を減らしてください。'}), 400
        
        # APIキーの取得と検証
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
        
        try:
            get_gemini_model(api_key, language)
        except Exception as e:
            error_msg = str(e)
            
            if "quota" in error_msg.lower() or "429" in error_msg or "rate" in error_msg.lower():
                return jsonify({'error': 'APIのリクエスト制限に達しました。しばらく待ってから再試行してください。'}), 429
            elif "key" in error_msg.lower() or "auth" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                return jsonify({'error': 'APIキーが無効です。有効なAPIキーを設定してください。'}), 401
            else:
                return jsonify({'error': 'AIモデルの初期化に失敗しました: ' + error_msg}), 500
        
        # ドキュメントのテキストを取得
        document_name = session.get('document_name', 'アップロードされた文書')
        document_text = ""
        
        # 新方式: 一時ファイルから読み込み
        if 'document_id' in session:
            document_id = session.get('document_id')
            logger.info(f"Document ID found in session: {document_id}")
            
            try:
                import os
                import tempfile
                
                # 一時ファイルのパスを構築
                temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                
                # ファイルが存在するか確認
                if os.path.exists(document_file_path):
                    # ファイルからテキストを読み込む
                    with open(document_file_path, 'r', encoding='utf-8') as f:
                        document_text = f.read()
                    
                    logger.info(f"Document text loaded from file, length: {len(document_text)} characters")
                else:
                    logger.warning(f"Document file not found: {document_file_path}")
            except Exception as file_error:
                logger.error(f"Error reading document from file: {str(file_error)}")
                # セッションから直接読み込みを試す（フォールバック）
        
        # 従来のセッションからの直接読み込み（ファイル取得に失敗した場合のフォールバック）
        if not document_text and 'document_text' in session:
            document_text = session.get('document_text', '')
            logger.info(f"Document text loaded from session, length: {len(document_text)} characters")
        
        # テキストの検証
        if not document_text or not isinstance(document_text, str) or len(document_text.strip()) == 0:
            logger.error("Document text is empty or not found")
            return jsonify({'error': '文書内容が空または見つかりません。文書を再アップロードしてください。'}), 400
            
        logger.info(f"Document name: {document_name}")
        
        # ログに文書内容のサンプルを記録（デバッグ用）
        sample_text = document_text[:200] + "..." if len(document_text) > 200 else document_text
        logger.info(f"Document content sample: {sample_text}")
        
        # テキストから再度ベクトルストアを作成
        from agents.document_processor import split_text, create_vector_store
        
        # テキストをチャンクに分割
        logger.info("Splitting document text into chunks")
        chunks = split_text(document_text)
        
        if not chunks or len(chunks) == 0:
            logger.error("Failed to split document into chunks")
            return jsonify({'error': '文書をチャンクに分割できませんでした。別の文書を試してください。'}), 400
            
        logger.info(f"Successfully split document into {len(chunks)} chunks")
        
        # ベクトルストアを作成
        logger.info("Creating vector store from document chunks")
        vector_store = create_vector_store(chunks, api_key)
        
        if not vector_store:
            logger.error("Failed to create vector store from document")
            return jsonify({'error': 'ドキュメントからベクトルストアを作成できませんでした。'}), 500
            
        logger.info("Vector store successfully created")
            
        # ドキュメントテキストとトピックを組み合わせて新しいトピックを作成
        # 文書内容の先頭部分を追加して、文脈を強化
        document_preview = document_text[:800] if len(document_text) > 800 else document_text
        topic = f"{base_topic} (対象文書: {document_name})\n\n文書内容:\n{document_preview}"
        
        logger.info(f"Enhanced topic with document content preview")
        
        logger.info(f"Created enhanced topic with document content")
        
        # RAG対応の議論生成
        logger.info(f"Starting RAG-enhanced discussion generation for topic: {base_topic}")
        discussion_data = generate_discussion(
            api_key=api_key,
            topic=topic,
            roles=roles,
            num_turns=num_turns,
            language=language,
            vector_store=vector_store,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        logger.info(f"Successfully generated RAG-enhanced discussion with {len(discussion_data)} messages")
        return jsonify({'discussion': discussion_data})
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating RAG-enhanced discussion: {error_message}")
        
        if "timeout" in error_message.lower() or "time" in error_message.lower():
            return jsonify({'error': 'リクエストがタイムアウトしました。少ないロール数やターン数で再試行してください。'}), 504
        elif "memory" in error_message.lower():
            return jsonify({'error': 'メモリ制限エラー：少ないロール数や少ないターン数でお試しください。'}), 500
        else:
            return jsonify({'error': f'{error_message}'}), 500


@app.route('/clear-document', methods=['POST'])
def clear_document():
    """セッションからドキュメント情報をクリアする"""
    try:
        logger.info("Clearing document data from session")
        
        # セッション状態を完全に整理
        session.clear()
        logger.info("Cleared entire session")
        
        # 全てのドキュメント関連データを再設定
        keys_to_remove = [
            'document_text', 
            'document_uploaded', 
            'document_name', 
            'document_summary', 
            'document_analysis', 
            'document_rag_data',
            'document_vector_store',
            'document_analysis_id'
        ]
        
        # 重要なセッションキーを明示的に削除（念のため）
        for key in keys_to_remove:
            if key in session:
                session.pop(key, None)
                logger.info(f"Explicitly removed session key: {key}")
        
        # 全てのドキュメントフラグを確実にリセット
        session['document_uploaded'] = False
        
        # 一時ファイルを削除
        try:
            import os
            import tempfile
            import glob
            import shutil
            
            # まず分析IDに基づいた特定のファイルを削除
            analysis_id = session.get('document_analysis_id')
            if analysis_id:
                # 一時ファイルのパスを構築
                temp_dir = os.path.join(tempfile.gettempdir(), 'document_analysis')
                analysis_file_path = os.path.join(temp_dir, f"{analysis_id}.json")
                
                # ファイルが存在する場合は削除
                if os.path.exists(analysis_file_path):
                    os.remove(analysis_file_path)
                    logger.info(f"Removed temporary analysis file: {analysis_file_path}")
            
            # 一時ディレクトリ内の全てのJSONファイルを削除
            temp_dir = os.path.join(tempfile.gettempdir(), 'document_analysis')
            if os.path.exists(temp_dir):
                # まず3日以上経過したファイルを削除
                import time
                current_time = time.time()
                three_days_in_seconds = 3 * 24 * 60 * 60
                
                for file_path in glob.glob(os.path.join(temp_dir, "*.json")):
                    if os.path.exists(file_path):
                        try:
                            file_modified_time = os.path.getmtime(file_path)
                            if current_time - file_modified_time > three_days_in_seconds:
                                os.remove(file_path)
                                logger.info(f"Removed old temporary file: {file_path}")
                        except Exception as file_error:
                            logger.error(f"Error removing temporary file {file_path}: {str(file_error)}")
                
                # 必要に応じてディレクトリを再作成
                try:
                    # 一時ディレクトリを完全にクリア（オプション）
                    # shutil.rmtree(temp_dir)
                    # os.makedirs(temp_dir, exist_ok=True)
                    # logger.info(f"Recreated temporary directory: {temp_dir}")
                    pass
                except Exception as dir_error:
                    logger.error(f"Error recreating temporary directory: {str(dir_error)}")
                    
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up temporary files: {str(cleanup_error)}")
            
        # アップロードディレクトリもクリア
        try:
            import os
            
            # アップロードディレクトリをチェック
            upload_dir = os.path.join('static', 'uploads')
            if os.path.exists(upload_dir):
                for item in os.listdir(upload_dir):
                    item_path = os.path.join(upload_dir, item)
                    try:
                        if os.path.isfile(item_path):
                            os.unlink(item_path)
                            logger.info(f"Removed upload file: {item_path}")
                    except Exception as upload_error:
                        logger.error(f"Error removing upload file {item_path}: {str(upload_error)}")
        except Exception as upload_cleanup_error:
            logger.error(f"Error cleaning upload directory: {str(upload_cleanup_error)}")
        
        # セッションを確実に保存（変更をすぐに反映させるため）
        session.modified = True
        
        logger.info("Document data successfully cleared from session")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error clearing document session: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'ドキュメントデータのクリア中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/generate-action-items', methods=['POST'])
def create_action_items():
    """議論の内容からアクションアイテムを生成する"""
    try:
        logger.info("Received action items generation request")
        # グローバルインポートを使用
        import os
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        language = data.get('language', 'ja')
        
        # 議論データの検証
        if not discussion_data or len(discussion_data) < 2:
            logger.warning("Insufficient discussion data for action items")
            return jsonify({'error': 'アクションアイテムの生成には最低2つの発言が必要です。'}), 400
        
        # APIキーの取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found for action items generation")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
        
        # モデル設定の取得
        settings = data.get('settings', {})
        model = settings.get('model', 'gemini-2.0-flash-lite') 
        temperature = float(settings.get('temperature', 0.2))
        max_output_tokens = int(settings.get('maxOutputTokens', 1024))
        
        # アクションアイテムを生成
        logger.info("Generating action items from discussion")
        result = generate_action_items(
            api_key, 
            discussion_data, 
            language,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        if not result['success']:
            logger.error(f"Failed to generate action items: {result.get('error', 'Unknown error')}")
            return jsonify({'error': f'アクションアイテムの生成に失敗しました: {result.get("error", "不明なエラー")}'}), 500
        
        logger.info("Successfully generated action items")
        # MarkdownのHTMLへの変換
        markdown_content = result['action_items']
        
        return jsonify({
            'success': True,
            'markdown_content': markdown_content
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating action items: {error_message}")
        return jsonify({'error': f'アクションアイテムの生成中にエラーが発生しました: {error_message}'}), 500

@app.route('/summarize-discussion', methods=['POST'])
def summarize_discussion_endpoint():
    """議論の内容を要約する"""
    try:
        logger.info("Received discussion summarization request")
        # グローバルインポートを使用
        import os
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        topic = data.get('topic', '')
        language = data.get('language', 'ja')
        
        # 議論データの検証
        if not discussion_data or len(discussion_data) < 2:
            logger.warning("Insufficient discussion data for summarization")
            return jsonify({'error': '要約には最低2つの発言が必要です。'}), 400
        
        # APIキーの取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found for discussion summarization")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
        
        # モデル設定の取得
        settings = data.get('settings', {})
        model = settings.get('model', 'gemini-2.0-flash-lite')
        temperature = float(settings.get('temperature', 0.7))
        max_output_tokens = int(settings.get('maxOutputTokens', 1024))
        
        # 要約を生成
        logger.info(f"Generating summary for discussion on topic: {topic}")
        result = summarize_discussion(api_key, discussion_data, topic, language)
        
        logger.info("Successfully generated discussion summary")
        return jsonify({
            'success': True,
            'markdown_content': result['markdown_content']
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error summarizing discussion: {error_message}")
        return jsonify({'error': f'議論の要約中にエラーが発生しました: {error_message}'}), 500

@app.route('/provide-guidance', methods=['POST'])
def provide_guidance_endpoint():
    """議論に対して指示や提案を提供し、その指示に基づいて議論を継続する"""
    try:
        logger.info("Received guidance request for discussion")
        # グローバルインポートを使用
        import os
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        topic = data.get('topic', '')
        instruction = data.get('instruction', '')
        language = data.get('language', 'ja')
        num_additional_turns = int(data.get('num_additional_turns', 1))
        use_document = data.get('use_document', False)
        
        # データの検証
        if not discussion_data or len(discussion_data) < 2:
            logger.warning("Insufficient discussion data for guidance")
            return jsonify({'error': '指導提供には最低2つの発言が必要です。'}), 400
            
        if not instruction:
            logger.warning("No instruction provided for guidance")
            return jsonify({'error': '指導内容を入力してください。'}), 400
            
        if num_additional_turns < 1 or num_additional_turns > 5:
            logger.warning(f"Invalid additional turn count: {num_additional_turns}")
            return jsonify({'error': '追加ターン数は1から5の間で指定してください。'}), 400
            
        # 役割リストを作成
        roles = list(set([message['role'] for message in discussion_data]))
        
        # リソース制限の確認
        if len(roles) > 6:
            logger.warning(f"Too many roles for continuation: {len(roles)}")
            return jsonify({'error': 'リソース制限のため、最大6つまでの役割しか指定できません。'}), 400
            
        total_additional_requests = len(roles) * num_additional_turns
        if total_additional_requests > 15:
            logger.warning(f"Too many additional requests: {total_additional_requests}")
            return jsonify({'error': 'リソース制限のため、役割数×追加ターン数の組み合わせが大きすぎます。'}), 400
        
        # APIキーの取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found for guidance generation")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
        
        # 文書参照を使用するかどうかを確認
        vector_store = None
        document_text = ""
        if use_document and session.get('document_uploaded', False):
            try:
                # 新方式: 一時ファイルからドキュメントを読み込む
                if 'document_id' in session:
                    document_id = session.get('document_id')
                    
                    import os
                    import tempfile
                    
                    # 一時ファイルのパスを構築
                    temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                    document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                    
                    # ファイルが存在するか確認
                    if os.path.exists(document_file_path):
                        # ファイルからテキストを読み込む
                        with open(document_file_path, 'r', encoding='utf-8') as f:
                            document_text = f.read()
                        
                        logger.info(f"Document text loaded from file for guidance, length: {len(document_text)} characters")
                    else:
                        logger.warning(f"Document file not found for guidance: {document_file_path}")
                
                # ファイルからの読み込みに失敗した場合、旧方式でセッションから直接読み込む
                if not document_text and 'document_text' in session:
                    document_text = session.get('document_text', '')
                    logger.info(f"Document text loaded from session for guidance, length: {len(document_text)} characters")
                
                # ドキュメントの有無を確認
                if not document_text:
                    logger.warning("No document content found for guidance")
                    return jsonify({'error': '文書内容が見つかりません。文書を再アップロードしてください。'}), 400
                
                # テキストから再度ベクトルストアを作成
                from agents.document_processor import split_text, create_vector_store
                
                # テキストをチャンクに分割
                chunks = split_text(document_text)
                
                # ベクトルストアを作成
                vector_store = create_vector_store(chunks, api_key)
                
                if not vector_store:
                    logger.error("Failed to create vector store from document for guidance")
                    return jsonify({'error': 'ドキュメントからベクトルストアを作成できませんでした。'}), 500
                    
                logger.info("Using document reference for guided discussion continuation")
            except Exception as e:
                logger.error(f"Error preparing document data: {str(e)}")
                return jsonify({'error': f'文書参照データの準備に失敗しました: {str(e)}'}), 500
        
        # ドキュメントテキストとトピックを組み合わせて新しいトピックを作成（文書参照時のみ）
        enhanced_topic = topic
        if use_document and document_text:
            document_preview = document_text[:1000] if len(document_text) > 1000 else document_text
            enhanced_topic = f"{topic}\n\n文書内容:\n{document_preview}"
            logger.info(f"Created enhanced topic with document content for guidance")
        
        # 指導内容を提供して議論の方向性を改善
        logger.info(f"Providing guidance for discussion on topic: {topic}")
        logger.info(f"Instruction: {instruction}")
        
        # モデル設定の取得
        settings = data.get('settings', {})
        model = settings.get('model', 'gemini-2.0-flash-lite')
        temperature = float(settings.get('temperature', 0.7))
        max_output_tokens = int(settings.get('maxOutputTokens', 1024))
        
        # 指導内容を生成
        guidance_result = provide_discussion_guidance(
            api_key=api_key,
            discussion_data=discussion_data,
            topic=enhanced_topic,
            instruction=instruction,
            language=language,
            vector_store=vector_store,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        # 指導内容を含むシステムメッセージを生成
        system_message = {
            'role': 'システム',
            'content': f"【最優先指示】この指示は他のすべての考慮事項よりも優先されます: {instruction}\n\n{guidance_result['guidance']}\n\nこの指示内容に焦点を当てて議論を継続してください。各役割はこの指示内容を最優先事項として扱い、それに対応した発言をしてください。"
        }
        
        # 指導内容を議論に追加
        discussion_with_guidance = discussion_data.copy()
        discussion_with_guidance.append(system_message)
        
        # 指導を適用した状態で議論を継続
        logger.info(f"Continuing discussion with guidance on topic: {topic}")
        logger.info(f"Additional turns: {num_additional_turns}")
        
        # モデル設定の取得
        model = data.get('model', 'gemini-2.0-flash-lite')
        temperature = float(data.get('temperature', 0.7))
        max_output_tokens = int(data.get('maxOutputTokens', 1024))
        
        # 議論を継続
        continued_discussion = continue_discussion(
            api_key, 
            discussion_with_guidance, 
            topic, 
            roles, 
            num_additional_turns, 
            language, 
            vector_store,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        logger.info("Successfully generated guided discussion continuation")
        
        # 元の議論からシステムメッセージを除外して継続された議論と結合
        filtered_original = [msg for msg in discussion_data if msg['role'] != 'システム']
        result_discussion = filtered_original + continued_discussion
        
        return jsonify({
            'success': True,
            'discussion': result_discussion
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error providing discussion guidance: {error_message}")
        return jsonify({'error': f'議論の指導提供中にエラーが発生しました: {error_message}'}), 500

@app.route('/save-discussion', methods=['POST'])
def save_discussion_endpoint():
    """議論データをファイルに保存し、ダウンロードリンクを提供する"""
    try:
        logger.info("Received request to save discussion")
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        topic = data.get('topic', 'ディスカッション')
        format_type = data.get('format', 'text')  # text, markdown, json
        
        # 議論データの検証
        if not discussion_data or len(discussion_data) < 1:
            logger.warning("No discussion data to save")
            return jsonify({'error': '保存するディスカッションデータがありません。'}), 400
        
        # 一時ファイル名の生成
        timestamp = int(time.time())
        filename_base = f"discussion_{timestamp}"
        
        content = ""
        mime_type = "text/plain"
        extension = "txt"
        
        if format_type == 'text':
            # プレーンテキスト形式
            content = f"ディスカッション: {topic}\n\n"
            for msg in discussion_data:
                content += f"【{msg['role']}】\n{msg['content']}\n\n"
            mime_type = "text/plain"
            extension = "txt"
            
        elif format_type == 'markdown':
            # Markdown形式
            content = f"# ディスカッション: {topic}\n\n"
            for msg in discussion_data:
                content += f"## {msg['role']}\n\n{msg['content']}\n\n---\n\n"
            mime_type = "text/markdown"
            extension = "md"
            
        elif format_type == 'json':
            # JSON形式
            content = json.dumps({
                'topic': topic,
                'timestamp': timestamp,
                'date': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
                'discussion': discussion_data
            }, ensure_ascii=False, indent=2)
            mime_type = "application/json"
            extension = "json"
        
        # 一時ファイルパスの作成
        filename = f"{filename_base}.{extension}"
        static_path = os.path.join(app.static_folder, 'downloads')
        
        # ディレクトリが存在しない場合は作成
        if not os.path.exists(static_path):
            os.makedirs(static_path)
            
        file_path = os.path.join(static_path, filename)
        
        # ファイルに書き込み
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # ダウンロードURLの生成
        download_url = url_for('static', filename=f'downloads/{filename}')
        
        logger.info(f"Discussion saved successfully: {filename}")
        return jsonify({
            'success': True,
            'filename': filename,
            'url': download_url,
            'mime_type': mime_type
        })
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error saving discussion: {error_message}")
        return jsonify({'error': f'ディスカッションの保存中にエラーが発生しました: {error_message}'}), 500

@app.route('/generate-next-turn', methods=['POST'])
def generate_next_turn_endpoint():
    """ディスカッションの次のターンを生成する"""
    try:
        logger.info("Received next turn generation request")
        
        # 必須モジュールのインポート
        import os
        
        # リクエストデータの取得
        data = request.json
        topic = data.get('topic', '')
        roles = data.get('roles', [])
        language = data.get('language', 'ja')
        current_discussion = data.get('discussion', [])
        current_turn = int(data.get('currentTurn', 0))
        current_role_index = int(data.get('currentRoleIndex', 0))
        num_turns = int(data.get('numTurns', 3))
        use_document = data.get('use_document', False)  # 文書を使用するかどうかのフラグ
        
        # モデル設定パラメータの取得
        model = data.get('model', 'gemini-2.0-flash-lite')
        temperature = float(data.get('temperature', 0.7))
        max_output_tokens = int(data.get('maxOutputTokens', 1024))
        
        logger.info(f"Request parameters: topic={topic}, roles_count={len(roles)}, use_document={use_document}")
        logger.info(f"Model settings: model={model}, temperature={temperature}, max_output_tokens={max_output_tokens}")
        
        # 入力検証
        if not topic:
            logger.warning("Empty topic provided")
            return jsonify({'error': '議題を入力してください'}), 400
            
        if not roles or len(roles) < 2:
            logger.warning(f"Insufficient roles: {len(roles)}")
            return jsonify({'error': '少なくとも2つの役割が必要です'}), 400
            
        # 環境変数からAPIキーを取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found in environment variables")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
            
        # 次のターンを生成
        logger.info(f"Generating next turn for topic: {topic}, Turn: {current_turn+1}, Role index: {current_role_index}")
        
        # ベクトルストア（RAG）を取得
        vector_store = None
        document_text = ""
        
        # 文書を使用するかどうかをチェック
        if use_document:
            logger.info("Document reference requested for this turn")
            if 'document_uploaded' in session and session['document_uploaded']:
                # 新方式: 一時ファイルからドキュメントを読み込む
                document_text = ""
                
                if 'document_id' in session:
                    document_id = session.get('document_id')
                    logger.info(f"Document ID found in session: {document_id}")
                    
                    try:
                        import os
                        import tempfile
                        
                        # 一時ファイルのパスを構築
                        temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                        document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                        
                        # ファイルが存在するか確認
                        if os.path.exists(document_file_path):
                            # ファイルからテキストを読み込む
                            with open(document_file_path, 'r', encoding='utf-8') as f:
                                document_text = f.read()
                            
                            logger.info(f"Document text loaded from file for next turn, length: {len(document_text)} characters")
                        else:
                            logger.warning(f"Document file not found for next turn: {document_file_path}")
                    except Exception as file_error:
                        logger.error(f"Error reading document from file for next turn: {str(file_error)}")
                
                # ファイルからの読み込みに失敗した場合、旧方式でセッションから直接読み込む
                if not document_text and 'document_text' in session:
                    document_text = session.get('document_text', '')
                    logger.info(f"Document text loaded from session for next turn, length: {len(document_text)} characters")
                
                # ドキュメントテキストの処理
                if document_text:
                    # ドキュメントテキストからベクトルストアを再作成
                    from agents.document_processor import create_vector_store, split_text
                    
                    sample_text = document_text[:200] + "..." if len(document_text) > 200 else document_text
                    logger.info(f"Document sample: {sample_text}")
                    
                    # テキストをチャンクに分割
                    logger.info("Splitting document text into chunks for next turn")
                    chunks = split_text(document_text)
                    
                    if chunks and len(chunks) > 0:
                        logger.info(f"Successfully split document into {len(chunks)} chunks")
                        
                        # ベクトルストアを作成
                        logger.info("Creating vector store for next turn")
                        vector_store = create_vector_store(chunks, api_key)
                        
                        if vector_store:
                            logger.info("Vector store successfully created for next turn")
                        else:
                            logger.error("Failed to create vector store for next turn")
                    else:
                        logger.error("Failed to split document into chunks for next turn")
                else:
                    logger.warning("Document text is empty in session")
            else:
                logger.warning("Document reference requested but no document in session")
        
        # ドキュメントテキストとトピックを組み合わせて新しいトピックを作成
        enhanced_topic = topic
        if use_document and document_text:
            document_preview = document_text[:800] if len(document_text) > 800 else document_text
            enhanced_topic = f"{topic} (対象文書あり)\n\n文書内容:\n{document_preview}"
            logger.info(f"Created enhanced topic with document content for next turn")
        else:
            logger.info("Using original topic without document content")
                
        # 次のターンを生成
        from agents.discussion import generate_next_turn
        logger.info(f"Calling generate_next_turn with vector_store: {vector_store is not None}")
        result = generate_next_turn(
            api_key=api_key,
            topic=enhanced_topic,
            roles=roles,
            current_discussion=current_discussion,
            current_turn=current_turn,
            current_role_index=current_role_index,
            language=language,
            vector_store=vector_store,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens
        )
        
        # 最終ターンかどうかを確認
        total_roles = len(roles)
        total_iterations = total_roles * num_turns
        current_iteration = (current_turn * total_roles) + current_role_index + 1
        is_complete = current_iteration >= total_iterations
        
        if is_complete:
            logger.info("Discussion generation completed")
            result["is_complete"] = True
        
        return jsonify(result)
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating next turn: {error_message}")
        
        # エラーメッセージを分類
        if "timeout" in error_message.lower() or "time" in error_message.lower():
            return jsonify({'error': 'リクエストがタイムアウトしました。少ないロール数やターン数で再試行してください。'}), 504
        elif "memory" in error_message.lower():
            return jsonify({'error': 'メモリ制限エラー：少ないロール数や少ないターン数でお試しください。'}), 500
        else:
            return jsonify({'error': f'{error_message}'}), 500

@app.route('/continue-discussion', methods=['POST'])
def continue_discussion_endpoint():
    """既存の議論を継続する"""
    try:
        logger.info("Received request to continue discussion")
        # グローバルインポートを使用
        import os
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        topic = data.get('topic', '')
        roles = data.get('roles', [])
        num_additional_turns = int(data.get('num_additional_turns', 1))
        language = data.get('language', 'ja')
        current_turn = int(data.get('current_turn', 0))
        current_role_index = int(data.get('current_role_index', 0))
        
        # モデル設定パラメータの取得
        model = data.get('model', 'gemini-2.0-flash-lite')
        temperature = float(data.get('temperature', 0.7))
        max_output_tokens = int(data.get('maxOutputTokens', 1024))
        
        # 新規リクエストか継続リクエストかを判断
        is_new_request = current_turn == 0 and current_role_index == 0
        
        # データの検証（新規リクエストの場合のみ）
        if is_new_request:
            if not discussion_data or len(discussion_data) < 2:
                logger.warning("Insufficient discussion data to continue")
                return jsonify({'error': '継続するには最低2つの発言が必要です。'}), 400
                
            if not roles or len(roles) < 2:
                logger.warning("Insufficient roles to continue discussion")
                return jsonify({'error': '継続するには少なくとも2つの役割が必要です。'}), 400
                
            if num_additional_turns < 1 or num_additional_turns > 5:
                logger.warning(f"Invalid additional turn count: {num_additional_turns}")
                return jsonify({'error': '追加ターン数は1から5の間で指定してください。'}), 400
                
            # リソース制限の確認
            if len(roles) > 6:
                logger.warning(f"Too many roles for continuation: {len(roles)}")
                return jsonify({'error': 'リソース制限のため、最大6つまでの役割しか指定できません。'}), 400
                
            total_additional_requests = len(roles) * num_additional_turns
            if total_additional_requests > 15:
                logger.warning(f"Too many additional requests: {total_additional_requests}")
                return jsonify({'error': 'リソース制限のため、役割数×追加ターン数の組み合わせが大きすぎます。'}), 400
        
        # APIキーの取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("No API key found for discussion continuation")
            return jsonify({'error': 'APIキーが設定されていません。GEMINI_API_KEYを環境変数に設定してください。'}), 500
            
        # 文書参照を使用するかどうかを確認
        vector_store = None
        document_text = ""
        use_document = data.get('use_document', False)
        
        if use_document and session.get('document_uploaded', False):
            logger.info("Using document reference for discussion continuation")
            
            # 新方式: 一時ファイルからドキュメントを読み込む
            if 'document_id' in session:
                document_id = session.get('document_id')
                logger.info(f"Document ID found in session for continuation: {document_id}")
                
                try:
                    import os
                    import tempfile
                    
                    # 一時ファイルのパスを構築
                    temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                    document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                    
                    # ファイルが存在するか確認
                    if os.path.exists(document_file_path):
                        # ファイルからテキストを読み込む
                        with open(document_file_path, 'r', encoding='utf-8') as f:
                            document_text = f.read()
                        
                        logger.info(f"Document text loaded from file for continuation, length: {len(document_text)} characters")
                    else:
                        logger.warning(f"Document file not found for continuation: {document_file_path}")
                except Exception as file_error:
                    logger.error(f"Error reading document from file for continuation: {str(file_error)}")
            
            # ファイルからの読み込みに失敗した場合は従来のセッション方式を試す
            if not document_text and 'document_text' in session:
                document_text = session.get('document_text', '')
                logger.info(f"Document text loaded from session for continuation, length: {len(document_text)} characters")
            
            if document_text:
                # テキストから再度ベクトルストアを作成
                from agents.document_processor import split_text, create_vector_store
                
                # テキストをチャンクに分割
                chunks = split_text(document_text)
                
                # ベクトルストアを作成
                vector_store = create_vector_store(chunks, api_key)
                
                if not vector_store:
                    logger.warning("Failed to create vector store for continuation")
                    # 継続はするが、文書参照なしで
                    logger.info("Continuing without document reference")
            else:
                logger.warning("No document content found for continuation")
                    
        # ドキュメントテキストとトピックを組み合わせて新しいトピックを作成（文書参照時のみ）
        enhanced_topic = topic
        if use_document and document_text:
            document_preview = document_text[:1000] if len(document_text) > 1000 else document_text
            enhanced_topic = f"{topic}\n\n文書内容:\n{document_preview}"
            logger.info(f"Created enhanced topic with document content for continuation")
        
        # 新規リクエストの場合は最初のメッセージを、継続リクエストの場合は次のメッセージを生成
        if is_new_request:
            logger.info(f"Starting new continuation sequence for topic: {topic}")
            
            # 最初のメッセージのターン情報を設定
            max_turns = current_turn + num_additional_turns
            total_roles = len(roles)
            total_iterations = total_roles * num_additional_turns
            
            # 一定数のターンにわたって生成を継続する代わりに、次のメッセージを生成
            current_role = roles[current_role_index]
            
            # ターンベースでの継続開始をマーク
            result = {
                'message': None,
                'next_turn': current_turn,
                'next_role_index': current_role_index,
                'is_complete': False,
                'total_iterations': total_iterations,
                'current_iteration': 0,
                'success': True
            }
            
            return jsonify(result)
        else:
            # 継続リクエストの場合、次のメッセージを生成
            logger.info(f"Continuing discussion: Turn {current_turn+1}, Role index {current_role_index}")
            
            # ターンの総数と役割を取得
            total_iterations = len(roles) * num_additional_turns
            current_iteration = (current_turn * len(roles)) + current_role_index + 1
            is_complete = current_iteration >= total_iterations
            
            # 次のターンを生成
            result = generate_next_turn(
                api_key=api_key,
                topic=enhanced_topic,
                roles=roles,
                current_discussion=discussion_data,
                current_turn=current_turn,
                current_role_index=current_role_index,
                language=language,
                vector_store=vector_store,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )
            
            # 最後のターンかどうかをマーク
            result['is_complete'] = is_complete
            result['total_iterations'] = total_iterations
            result['current_iteration'] = current_iteration
            result['success'] = True
            
            logger.info(f"Generated next message in continuation: {current_iteration}/{total_iterations}")
            
            return jsonify(result)
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error continuing discussion: {error_message}")
        return jsonify({'error': f'議論の継続中にエラーが発生しました: {error_message}'}), 500

@app.route('/get-document-text', methods=['GET'])
def get_document_text():
    """セッションに保存されているドキュメントのテキストを取得する"""
    try:
        # セッションの状態を詳細にロギング
        logger.debug(f"Session document state: document_uploaded={session.get('document_uploaded', False)}")
        logger.debug(f"Session data keys: {list(session.keys())}")
        
        # ドキュメントがアップロードされている場合
        if 'document_uploaded' in session and session['document_uploaded']:
            
            # 新方式: 一時ファイルから読み込み
            if 'document_id' in session:
                document_id = session.get('document_id')
                logger.info(f"Document ID found in session: {document_id}")
                
                try:
                    import os
                    import tempfile
                    
                    # 一時ファイルのパスを構築
                    temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                    document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                    
                    # ファイルが存在するか確認
                    if os.path.exists(document_file_path):
                        # ファイルからテキストを読み込む
                        with open(document_file_path, 'r', encoding='utf-8') as f:
                            document_text = f.read()
                        
                        # テキストの検証
                        if document_text and len(document_text) > 0:
                            logger.info(f"Document text loaded from file, length: {len(document_text)} characters")
                            return jsonify({
                                'success': True,
                                'document_text': document_text
                            })
                        else:
                            logger.warning("Document file exists but content is empty")
                            return jsonify({
                                'success': False,
                                'error': 'ドキュメントファイルの内容が空です'
                            })
                    else:
                        logger.warning(f"Document file not found: {document_file_path}")
                        # 不整合の修正
                        session['document_uploaded'] = False
                        session.pop('document_id', None)
                        return jsonify({
                            'success': False,
                            'error': 'ドキュメントファイルが見つかりません'
                        })
                except Exception as file_error:
                    logger.error(f"Error reading document from file: {str(file_error)}")
                    # ファイルからの読み込みに失敗した場合は従来のセッション方式を試す
            
            # 従来のセッションからの直接読み込み（後方互換性用）
            if 'document_text' in session:
                document_text = session.get('document_text', '')
                
                # テキストが実際に存在するかチェック
                if document_text and isinstance(document_text, str) and len(document_text) > 0:
                    logger.debug(f"Document text found in session, length: {len(document_text)} characters")
                    return jsonify({
                        'success': True,
                        'document_text': document_text
                    })
                else:
                    logger.warning("Document marked as uploaded but text in session is empty or invalid")
                    # セッションフラグを修正
                    session['document_uploaded'] = False
                    session.pop('document_text', None)
                    return jsonify({
                        'success': False,
                        'error': 'ドキュメントテキストが無効または空です'
                    })
            else:
                logger.warning("Document marked as uploaded but no text or document_id in session")
                # セッションフラグを修正
                session['document_uploaded'] = False
                return jsonify({
                    'success': False,
                    'error': 'セッションにドキュメントデータがありません'
                })
        else:
            logger.info("No document uploaded in this session")
            # セッションフラグをクリア（念のため）
            if 'document_uploaded' in session:
                session['document_uploaded'] = False
            return jsonify({
                'success': False,
                'error': 'ドキュメントがアップロードされていません'
            })
    except Exception as e:
        logger.error(f"Error retrieving document text: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'ドキュメントテキストの取得中にエラーが発生しました: {str(e)}'
        })

@app.route('/get-document-analysis', methods=['GET'])
def get_document_analysis():
    """セッションに保存されている文書分析結果を取得する"""
    try:
        # グローバルインポートを使用
        import os
        import json
        import tempfile
        
        # 新しい方式: 一時ファイルから分析結果を読み込む
        analysis_id = session.get('document_analysis_id')
        if analysis_id:
            # 一時ファイルのパスを構築
            temp_dir = os.path.join(tempfile.gettempdir(), 'document_analysis')
            analysis_file_path = os.path.join(temp_dir, f"{analysis_id}.json")
            
            # ファイルから分析データを読み込む
            if os.path.exists(analysis_file_path):
                with open(analysis_file_path, 'r', encoding='utf-8') as f:
                    analysis_data = json.load(f)
                
                # 分析データを分割
                analysis = {
                    'summary': analysis_data.get('summary', ''),
                    'metadata': analysis_data.get('metadata', {}),
                    'structure': analysis_data.get('structure', {})
                }
                
                rag_data = analysis_data.get('rag_data', {})
                
                # 分析情報と拡張RAGデータを組み合わせて返す
                return jsonify({
                    'success': True,
                    'analysis': analysis,
                    'rag_data': rag_data,
                    'document_name': session.get('document_name', '')
                })
            else:
                logger.warning(f"Analysis file not found: {analysis_file_path}")
                return jsonify({
                    'success': False,
                    'error': '文書分析結果が見つかりません'
                })
                
        # 旧式のセッション保存（互換性のため保持）
        elif 'document_analysis' in session:
            analysis = session.get('document_analysis', {})
            rag_data = session.get('document_rag_data', {})
            
            # 分析情報と拡張RAGデータを組み合わせて返す
            return jsonify({
                'success': True,
                'analysis': analysis,
                'rag_data': rag_data,
                'document_name': session.get('document_name', '')
            })
        else:
            # 分析結果がない場合は自動分析を試行
            if 'document_uploaded' in session and session['document_uploaded']:
                try:
                    # 文書IDに基づいて一時ファイルから読み込み
                    document_text = ""
                    filename = session.get('document_name', 'document.txt')
                    
                    if 'document_id' in session:
                        document_id = session.get('document_id')
                        try:
                            temp_dir = os.path.join(tempfile.gettempdir(), 'document_content')
                            document_file_path = os.path.join(temp_dir, f"{document_id}.txt")
                            
                            if os.path.exists(document_file_path):
                                with open(document_file_path, 'r', encoding='utf-8') as f:
                                    document_text = f.read()
                                logger.info(f"Document text loaded from file for analysis, length: {len(document_text)} characters")
                        except Exception as file_error:
                            logger.error(f"Error reading document from file for analysis: {str(file_error)}")
                    
                    # フォールバック: セッションから直接読み込み
                    if not document_text and 'document_text' in session:
                        document_text = session.get('document_text', '')
                        logger.info(f"Document text loaded from session for analysis, length: {len(document_text)} characters")
                        
                    api_key = os.environ.get('GEMINI_API_KEY')
                    
                    if document_text and api_key:
                        logger.info("No analysis found, generating on-demand analysis")
                        from agents.document_analyzer import create_document_analysis_report
                        
                        analysis_report = create_document_analysis_report(
                            document_text=document_text,
                            filename=filename,
                            api_key=api_key
                        )
                        
                        if analysis_report and analysis_report.get('success'):
                            logger.info("Successfully generated document analysis on-demand")
                            # 分析結果をセッションに保存
                            session['document_analysis'] = {
                                'summary': analysis_report.get('summary', ''),
                                'metadata': analysis_report.get('metadata', {}),
                                'structure': {
                                    'paragraph_count': analysis_report.get('structure', {}).get('paragraph_count', 0),
                                    'sections_count': len(analysis_report.get('structure', {}).get('sections', [])),
                                    'key_terms': analysis_report.get('structure', {}).get('key_terms', [])[:10]
                                }
                            }
                            
                            return jsonify({
                                'success': True,
                                'analysis': session['document_analysis'],
                                'document_name': filename,
                                'generated_now': True
                            })
                except Exception as analysis_error:
                    logger.error(f"Error generating on-demand analysis: {str(analysis_error)}")
                    
            return jsonify({
                'success': False,
                'error': '文書分析結果が見つかりません'
            })
    except Exception as e:
        logger.error(f"Error retrieving document analysis: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'文書分析結果の取得中にエラーが発生しました: {str(e)}'
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
