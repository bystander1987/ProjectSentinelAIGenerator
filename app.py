import os
import logging
import tempfile
import time
import json
import pickle
from flask import Flask, render_template, request, jsonify, session, url_for
from agents.discussion import (
    generate_discussion, get_gemini_model, summarize_discussion,
    provide_discussion_guidance, continue_discussion, generate_next_turn
)
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


@app.route('/clear-document', methods=['POST'])
def clear_document():
    """セッションからドキュメント情報をクリアする"""
    try:
        logger.info("Clearing document from session")
        session.pop('document_text', None)
        session.pop('document_uploaded', None)
        session.pop('document_name', None)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error clearing document session: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate-action-items', methods=['POST'])
def create_action_items():
    """議論の内容からアクションアイテムを生成する"""
    try:
        logger.info("Received action items generation request")
        
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
        
        # アクションアイテムを生成
        logger.info("Generating action items from discussion")
        result = generate_action_items(api_key, discussion_data, language)
        
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
        if use_document and session.get('document_uploaded', False):
            try:
                vector_store_pickle = session.get('vector_store', None)
                vector_store = pickle.loads(vector_store_pickle) if vector_store_pickle else None
                logger.info("Using document reference for guided discussion continuation")
            except Exception as e:
                logger.error(f"Error loading vector store: {str(e)}")
                return jsonify({'error': f'文書参照データの読み込みに失敗しました: {str(e)}'}), 500
        
        # 指導内容を新しいシステムプロンプトとして議論に追加
        system_message = {
            'role': 'システム',
            'content': f"次の指示に従って議論を継続してください: {instruction}"
        }
        discussion_with_guidance = discussion_data.copy()
        discussion_with_guidance.append(system_message)
        
        # 指導を適用した状態で議論を継続
        logger.info(f"Continuing discussion with guidance on topic: {topic}")
        logger.info(f"Instruction: {instruction}")
        logger.info(f"Additional turns: {num_additional_turns}")
        
        # 議論を継続
        continued_discussion = continue_discussion(
            api_key, 
            discussion_with_guidance, 
            topic, 
            roles, 
            num_additional_turns, 
            language, 
            vector_store
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
        
        # リクエストデータの取得
        data = request.json
        topic = data.get('topic', '')
        roles = data.get('roles', [])
        language = data.get('language', 'ja')
        current_discussion = data.get('discussion', [])
        current_turn = int(data.get('currentTurn', 0))
        current_role_index = int(data.get('currentRoleIndex', 0))
        num_turns = int(data.get('numTurns', 3))
        
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
        if 'document_uploaded' in session and session['document_uploaded']:
            # ドキュメントテキストからベクトルストアを再作成
            from agents.document_processor import create_vector_store
            document_text = session.get('document_text', '')
            if document_text:
                logger.info("Recreating vector store from session document")
                text_chunks = document_text.split('\n\n')  # 単純化のため段落で分割
                vector_store = create_vector_store(text_chunks, api_key)
                
        # 次のターンを生成
        from agents.discussion import generate_next_turn
        result = generate_next_turn(
            api_key=api_key,
            topic=topic,
            roles=roles,
            current_discussion=current_discussion,
            current_turn=current_turn,
            current_role_index=current_role_index,
            language=language,
            vector_store=vector_store
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
        
        # リクエストデータの取得
        data = request.json
        discussion_data = data.get('discussion_data', [])
        topic = data.get('topic', '')
        roles = data.get('roles', [])
        num_additional_turns = int(data.get('num_additional_turns', 1))
        language = data.get('language', 'ja')
        current_turn = int(data.get('current_turn', 0))
        current_role_index = int(data.get('current_role_index', 0))
        
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
        use_document = data.get('use_document', False)
        
        if use_document and session.get('document_uploaded', False):
            logger.info("Using document reference for discussion continuation")
            vector_store_pickle = session.get('vector_store', None)
            try:
                vector_store = pickle.loads(vector_store_pickle) if vector_store_pickle else None
            except Exception as e:
                logger.warning(f"Failed to load vector store: {str(e)}")
                
                # ドキュメントがセッションにある場合は再作成
                document_text = session.get('document_text', '')
                if document_text:
                    from agents.document_processor import split_text, create_vector_store
                    chunks = split_text(document_text)
                    vector_store = create_vector_store(chunks, api_key)
                
                if not vector_store:
                    logger.warning("Failed to create vector store for continuation")
                    # 継続はするが、文書参照なしで
                    logger.info("Continuing without document reference")
        
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
                topic=topic,
                roles=roles,
                current_discussion=discussion_data,
                current_turn=current_turn,
                current_role_index=current_role_index,
                language=language,
                vector_store=vector_store
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
