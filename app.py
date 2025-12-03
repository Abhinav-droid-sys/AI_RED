from flask import Flask, request, jsonify, render_template
from groq import Groq
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file (local development)
load_dotenv()

app = Flask(__name__)

# =========================
# GROQ CONFIG (RENDER SAFE)
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Handle missing API key gracefully for Render
if not GROQ_API_KEY:
    print("⚠️ WARNING: GROQ_API_KEY not found! Chat will show error messages.")
    client = None
else:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        print("✅ Groq client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Groq client: {e}")
        client = None

# =========================
# RED PERSONA (SYSTEM PROMPT)
# =========================

SYSTEM_PROMPT = (
    "You are an AI assistant called RED. "
    "Your name comes from the app's bold red visual theme, which represents speed, focus, and power. "
    "When users ask who you are or why you're called RED, say that you're RED, "
    "the AI assistant for this app, and your name reflects the app's fast, powerful red design. "
    "You are helpful, concise, and respond quickly. "
    "Use bullet points when explaining lists or steps. "
    "Keep responses under 300 words unless asked for more detail. "
    "Always be friendly and professional."
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat requests with error handling"""
    
    # Check if client is available
    if not client:
        return jsonify({
            'success': False,
            'error': 'AI service not configured. Please contact administrator.'
        }), 503
    
    try:
        data = request.json
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Empty message'}), 400
        
        print(f"📨 User message: {message[:50]}...")
        
        # Create chat completion
        chat_completion = client.chat.completions.create(
            model="llama-3.1-70b-versatile",  # Fast and powerful model
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=1000,
            stream=False
        )
        
        response = chat_completion.choices[0].message.content
        print(f"🤖 AI response sent: {len(response)} chars")
        
        return jsonify({
            'success': True,
            'response': response
        })
        
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        return jsonify({
            'success': False, 
            'error': 'AI service temporarily unavailable. Please try again.'
        }), 503

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Route not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Render requires binding to 0.0.0.0 and using PORT env var
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
