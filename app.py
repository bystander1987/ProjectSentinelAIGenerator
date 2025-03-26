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
        
        # Validate input
        if not topic:
            return jsonify({'error': 'Topic is required'}), 400
        
        if not roles or len(roles) < 2:
            return jsonify({'error': 'At least two roles are required'}), 400
            
        if num_turns < 1 or num_turns > 10:
            return jsonify({'error': 'Number of turns must be between 1 and 10'}), 400
        
        # Get API key from environment
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'API key not configured'}), 500
            
        # Try to initialize the Gemini model to check API key validity
        try:
            get_gemini_model(api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}")
            return jsonify({'error': 'Failed to initialize AI model. Check API key.'}), 500
        
        # Generate the discussion
        discussion_data = generate_discussion(
            api_key=api_key,
            topic=topic,
            roles=roles,
            num_turns=num_turns
        )
        
        return jsonify({'discussion': discussion_data})
    
    except Exception as e:
        logger.error(f"Error generating discussion: {str(e)}")
        return jsonify({'error': f'Failed to generate discussion: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
