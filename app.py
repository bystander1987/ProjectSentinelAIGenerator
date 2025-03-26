import os
import logging
import tempfile
from flask import Flask, render_template, request, jsonify, session
from agents.discussion import generate_discussion, get_gemini_model
from agents.document_processor import process_uploaded_file, SUPPORTED_FORMATS
from agents.action_items import generate_action_items

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/')
def index():
    """Render the main page of the application."""
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
            
        # ベクトルストアをセッションに保存
        # 注意: ベクトルストアオブジェクト自体は保存できないため、テキスト内容だけを保存
        session['document_text'] = result['text_content']
        session['document_uploaded'] = True
        session['document_name'] = filename
        
        logger.info(f"Document successfully processed and stored in session: {filename}")
        return jsonify({
            'success': True,
            'message': result['message'],
            'filename': filename
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
        
        # セッションに保存されたドキュメントをチェック
        if not session.get('document_uploaded', False):
            logger.warning("No document uploaded in session")
            return jsonify({'error': '参照ドキュメントがアップロードされていません。先にドキュメントをアップロードしてください。'}), 400
            
        # リクエストデータの取得
        data = request.json
        topic = data.get('topic', '')
        num_turns = int(data.get('num_turns', 3))
        roles = data.get('roles', [])
        language = data.get('language', 'ja')
        
        # 基本的な検証（通常の議論生成と同じ）
        if not topic:
            return jsonify({'error': '議題を入力してください'}), 400
            
        if len(topic) > 100:
            topic = topic[:97] + '...'
        
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
        document_text = session.get('document_text', '')
        
        # テキストから再度ベクトルストアを作成
        from agents.document_processor import split_text, create_vector_store
        
        # テキストをチャンクに分割
        chunks = split_text(document_text)
        
        # ベクトルストアを作成
        vector_store = create_vector_store(chunks, api_key)
        
        if not vector_store:
            logger.error("Failed to create vector store from document")
            return jsonify({'error': 'ドキュメントからベクトルストアを作成できませんでした。'}), 500
        
        # RAG対応の議論生成
        logger.info(f"Starting RAG-enhanced discussion generation for topic: {topic}")
        discussion_data = generate_discussion(
            api_key=api_key,
            topic=topic,
            roles=roles,
            num_turns=num_turns,
            language=language,
            vector_store=vector_store
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


@app.route('/generate-action-items', methods=['POST'])
def create_action_items():
    """議論の内容からアクションアイテムを生成する"""
    try:
        logger.info("Received action items generation request")
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion', [])
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
        
        # アクションアイテムを生成
        logger.info("Generating action items from discussion")
        result = generate_action_items(api_key, discussion_data, language)
        
        if not result['success']:
            logger.error(f"Failed to generate action items: {result.get('error', 'Unknown error')}")
            return jsonify({'error': f'アクションアイテムの生成に失敗しました: {result.get("error", "不明なエラー")}'}), 500
        
        logger.info("Successfully generated action items")
        return jsonify({'action_items': result['action_items']})
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error generating action items: {error_message}")
        return jsonify({'error': f'アクションアイテムの生成中にエラーが発生しました: {error_message}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
