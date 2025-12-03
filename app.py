from flask import Flask, request, jsonify, render_template
import os
import random

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    print("🌐 Chat UI served")
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])  # ← FIXED ROUTE
def chat():
    print("🔥 /api/chat WORKING!")
    data = request.json or {}
    message = data.get('message', 'Hello!')
    
    responses = [
        f"🚀 RED AI LIVE! You: '{message[:50]}'",
        "✅ redai.live fully working! Backend OK!",
        f"💬 Chat perfect. Message: '{message[:30]}...'",
        "Your AI assistant RED online! 🎉"
    ]
    
    response = random.choice(responses)
    print(f"🤖 Sent: {response[:50]}")
    
    return jsonify({'success': True, 'response': response})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 RED AI live on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
