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
        data = request.json
        topic = data.get('topic', '')
        num_turns = int(data.get('num_turns', 3))
        roles = data.get('roles', [])
        language = data.get('language', 'en')  # 言語設定を取得 (デフォルトは英語)
        
        # 入力検証
        if not topic:
            return jsonify({'error': '議題を入力してください'}), 400
        
        if not roles or len(roles) < 2:
            return jsonify({'error': '少なくとも2つの役割が必要です'}), 400
            
        if num_turns < 1 or num_turns > 10:
            return jsonify({'error': 'ターン数は1から10の間で指定してください'}), 400
        
        # 環境変数からAPIキーを取得
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'APIキーが設定されていません'}), 500
            
        # Geminiモデルを初期化してAPIキーの有効性を確認
        try:
            get_gemini_model(api_key, language)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}")
            return jsonify({'error': 'AIモデルの初期化に失敗しました。APIキーを確認してください。'}), 500
        
        # ディスカッションを生成
        discussion_data = generate_discussion(
            api_key=api_key,
            topic=topic,
            roles=roles,
            num_turns=num_turns,
            language=language
        )
        
        return jsonify({'discussion': discussion_data})
    
    except Exception as e:
        logger.error(f"Error generating discussion: {str(e)}")
        return jsonify({'error': f'{str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
