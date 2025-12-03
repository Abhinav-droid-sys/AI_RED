from flask import Flask, request, jsonify, render_template
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

@app.route('/')
def index():
    print("🌐 Chat UI served")
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    print("🔥 Chat working!")
    data = request.json or {}
    message = data.get('message', 'Hello!') 
    
    # Simple AI-like responses (no external API)
    responses = [
        "RED here! Your message: '{}'. AI backend working perfectly!".format(message[:50]),
        "✅ Connection success! Flask + Render = LIVE 🚀",
        "Chat endpoint active. Message received: '{}'".format(message[:30]),
        "RED AI online! Your site at redai.live is working!"
    ]
    
    import random
    response = random.choice(responses)
    
    print(f"🤖 Sent: {response[:50]}")
    return jsonify({'success': True, 'response': response})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 RED AI starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
