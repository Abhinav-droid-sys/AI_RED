from flask import Flask, request, jsonify, render_template, render_template_string, send_from_directory
from groq import Groq
import os
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, render_template


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")


# =========================
# GROQ CONFIG (SECURE)
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Check if API key exists
if not GROQ_API_KEY:
    print("❌ ERROR: GROQ_API_KEY not found in .env file!")
    print("Please create a .env file with:")
    print("GROQ_API_KEY=your_groq_api_key_here")
    raise ValueError("GROQ_API_KEY environment variable is required!")

client = Groq(api_key=GROQ_API_KEY)

# =========================
# RED PERSONA (SYSTEM PROMPT)
# =========================

SYSTEM_PROMPT = (
    "You are an AI assistant called RED. "
    "Your name comes from the app's bold red visual theme, which represents speed, focus, and power. "
    "When users ask who you are or why you're called RED, say that you're RED, "
    "the AI assistant for this app, and your name reflects its red, high-energy interface design. "
    "Be helpful, concise, and friendly."
)

# =========================
# IN-MEMORY CHAT STORAGE
# =========================

chat_histories = {}  # { session_id: [ {role, content}, ... ] }
chat_titles = {}     # { session_id: "Title" }

def generate_chat_title(first_message: str) -> str:
    """Generate a short title for the chat based on first user message."""
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Generate a very short title (max 4-5 words) for a chat that starts with: "
                    f"'{first_message[:120]}'. Only return the title, nothing else."
                ),
            },
        ]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=32,
            temperature=0.5,
        )
        title = response.choices[0].message.content.strip()
        title = title.replace('"', "").replace("'", "")
        return title[:50] if title else (first_message[:30] + "..." if len(first_message) > 30 else first_message)
    except Exception as e:
        print(f"[TITLE ERROR] {e}")
        return first_message[:30] + "..." if len(first_message) > 30 else first_message


# =========================
# ROUTES
# =========================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/privacy")
def privacy():
    # A minimal privacy page — you can expand this further (save as template if you prefer)
    content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Privacy — RED</title>
      <style>
        body { font-family: Inter, system-ui, Arial; background:#070708; color: #eee; padding:30px; }
        .card { max-width:800px; margin:30px auto; background:#0f0f10; border-radius:12px; padding:24px; border:1px solid #222; }
        a { color:#FF6B6B; text-decoration:none; font-weight:700; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Privacy & Data</h1>
        <p>This is a brief privacy note for <strong>RED</strong>.</p>
        <ul>
          <li>By default messages are stored locally in your browser (localStorage).</li>
          <li>If you use <em>Incognito</em> mode in the app, messages are kept only temporarily (in memory) and not saved to localStorage.</li>
          <li>Server-side requests are sent to the Groq API to generate assistant responses. Inputs sent to the server will be processed by the underlying model provider.</li>
          <li>We recommend avoiding sharing highly-sensitive personal data (SSNs, passwords, payment details) in chats.</li>
        </ul>
        <p>If you need a formal privacy policy for compliance, add a more detailed page here with contact & retention details.</p>
        <p><a href="/">Back to RED</a></p>
      </div>
    </body>
    </html>
    """
    return render_template_string(content)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat() + "Z"}), 200


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Request JSON format from frontend:
    {
      "prompt": "user text",
      "session_id": "chat_xxx",
      "is_incognito": true/false,
      "history": [ { "role": "user"|"assistant", "content": "..." }, ... ]
    }

    Response JSON:
    {
      "success": true/false,
      "response": "assistant text",
      "chat_title": "optional title or null",
      "error": "message on failure"
    }
    """
    try:
        data = request.get_json(force=True)
        prompt = data.get("prompt", "").strip()
        session_id = data.get("session_id", "default")
        is_incognito = bool(data.get("is_incognito", False))
        incognito_history = data.get("history", []) or []

        if not prompt:
            return jsonify({"success": False, "error": "No prompt provided"})

        # Build messages for Groq
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if is_incognito:
            for msg in incognito_history:
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})
        else:
            if session_id in chat_histories:
                for msg in chat_histories[session_id]:
                    role = "user" if msg["role"] == "user" else "assistant"
                    messages.append({"role": role, "content": msg["content"]})

        messages.append({"role": "user", "content": prompt})

        # Call Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            top_p=1.0,
            stream=False,
        )
        assistant_text = response.choices[0].message.content

        chat_title = None

        if not is_incognito:
            is_first_message = session_id not in chat_histories

            if session_id not in chat_histories:
                chat_histories[session_id] = []

            chat_histories[session_id].append({"role": "user", "content": prompt})
            chat_histories[session_id].append({"role": "assistant", "content": assistant_text})

            if is_first_message:
                chat_title = generate_chat_title(prompt)
                chat_titles[session_id] = chat_title

        return jsonify({"success": True, "response": assistant_text, "chat_title": chat_title})

    except Exception as e:
        error_msg = str(e)
        print(f"[CHAT ERROR] {error_msg}")

        if "rate" in error_msg.lower() or "429" in error_msg:
            return jsonify({"success": False, "error": "Rate limit reached. Please wait a moment. (Free tier: 30 requests/minute)"}), 429
        return jsonify({"success": False, "error": "Internal server error"}), 500


@app.route("/api/chats", methods=["GET"])
def get_chats():
    """Return list of all named chat sessions for sidebar."""
    chats = []
    for session_id, title in chat_titles.items():
        chats.append({"id": session_id, "title": title or "New Chat"})
    return jsonify({"success": True, "chats": chats})


@app.route("/api/chat/history", methods=["POST"])
def get_chat_history():
    """Return full history for a session_id."""
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")
        history = chat_histories.get(session_id, [])
        return jsonify({"success": True, "history": history})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chat/delete", methods=["POST"])
def delete_chat():
    """Delete a stored chat session."""
    try:
        data = request.get_json(force=True)
        session_id = data.get("session_id")

        if session_id in chat_titles:
            del chat_titles[session_id]
        if session_id in chat_histories:
            del chat_histories[session_id]

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RED AI Assistant - Powered by Groq")
    print("🤖 Persona: RED (named after the red, high-energy UI)")
    print("=" * 60)
    print(f"✅ Groq API Key Loaded: {GROQ_API_KEY[:10]}...***")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
