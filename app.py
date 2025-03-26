import os
import logging
from flask import Flask, render_template, request, jsonify, session
from agents.discussion import generate_discussion, get_gemini_model

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
        
        # 入力検証
        if not topic:
            logger.warning("Empty topic provided")
            return jsonify({'error': '議題を入力してください'}), 400
        
        if not roles or len(roles) < 2:
            logger.warning(f"Insufficient roles: {len(roles)}")
            return jsonify({'error': '少なくとも2つの役割が必要です'}), 400
            
        if num_turns < 1 or num_turns > 10:
            logger.warning(f"Invalid turn count: {num_turns}")
            return jsonify({'error': 'ターン数は1から10の間で指定してください'}), 400
        
        # リソース使用量の警告
        total_requests = len(roles) * num_turns
        if total_requests > 12:  # リソース使用量の閾値
            logger.warning(f"High resource request detected: {total_requests} total LLM calls")
            # 警告するが、処理は続行
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
