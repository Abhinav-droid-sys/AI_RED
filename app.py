from flask import Flask, request, jsonify, render_template, render_template_string
from groq import Groq
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore


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
# FIREBASE / FIRESTORE CONFIG
# =========================

FIREBASE_SERVICE_ACCOUNT_PATH = (os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()
if not FIREBASE_SERVICE_ACCOUNT_PATH:
    # Fallback for local setup when the key file is placed at project root.
    FIREBASE_SERVICE_ACCOUNT_PATH = "Database_key.json"
if not os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
    raise ValueError(
        "Firebase service account JSON not found. "
        f"Checked: {FIREBASE_SERVICE_ACCOUNT_PATH}. "
        "Set FIREBASE_SERVICE_ACCOUNT_PATH in .env to a valid JSON key file."
    )

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)

firestore_db = firestore.client()

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

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def request_user_id() -> str:
    user_id = (request.headers.get("X-User-Id") or "anonymous").strip()
    return user_id if user_id else "anonymous"


def history_preview(history: list) -> str:
    if not history:
        return ""
    for msg in reversed(history):
        content = (msg.get("content") or "").strip()
        if content:
            return content[:90]
    return ""


def chats_collection(user_id: str):
    return firestore_db.collection("users").document(user_id).collection("chats")


def chat_doc_ref(user_id: str, session_id: str):
    return chats_collection(user_id).document(session_id)

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


@app.route("/api/voice/process", methods=["POST"])
def process_voice_text():
    """
    Normalize and translate spoken input text to a clean prompt.
    Request JSON:
    {
      "text": "spoken transcript",
      "target_lang": "en"
    }
    """
    try:
        data = request.get_json(force=True)
        text = (data.get("text") or "").strip()
        target_lang = (data.get("target_lang") or "en").strip().lower()

        if not text:
            return jsonify({"success": False, "error": "text is required"}), 400

        instruction = (
            "You are a voice transcript post-processor. "
            "Clean obvious ASR mistakes when confidence is high, normalize punctuation, "
            "and translate to natural {} if input is another language. "
            "Do not add meaning, explanations, or extra text. "
            "Return only the final cleaned sentence."
        ).format("English" if target_lang == "en" else target_lang)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=300,
            top_p=1.0,
            stream=False,
        )
        processed = (response.choices[0].message.content or "").strip()
        if not processed:
            processed = text
        return jsonify({"success": True, "processed_text": processed})
    except Exception as e:
        print(f"[VOICE PROCESS ERROR] {e}")
        return jsonify({"success": False, "processed_text": text if 'text' in locals() else ""}), 200


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
        session_id = (data.get("session_id", "default") or "default").strip()
        user_id = request_user_id()
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
            existing_doc = chat_doc_ref(user_id, session_id).get()
            existing_chat = existing_doc.to_dict() if existing_doc.exists else {}
            stored_history = existing_chat.get("history", [])
            for msg in stored_history:
                role = "user" if msg.get("role") == "user" else "assistant"
                content = msg.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

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
            existing_doc = chat_doc_ref(user_id, session_id).get()
            existing_chat = existing_doc.to_dict() if existing_doc.exists else {}
            existing_history = existing_chat.get("history", [])
            is_first_message = not existing_history
            timestamp = now_utc_iso()
            updated_history = existing_history + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": assistant_text},
            ]

            if is_first_message:
                chat_title = generate_chat_title(prompt)
            else:
                chat_title = existing_chat.get("title")

            chat_doc_ref(user_id, session_id).set(
                {
                    "id": session_id,
                    "user_id": user_id,
                    "title": chat_title or "New Chat",
                    "history": updated_history,
                    "preview": history_preview(updated_history),
                    "created_at": existing_chat.get("created_at") or timestamp,
                    "updated_at": timestamp,
                }
            )

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
    try:
        user_id = request_user_id()
        docs = chats_collection(user_id).order_by("updated_at", direction=firestore.Query.DESCENDING).stream()
        chats = []
        for doc in docs:
            d = doc.to_dict() or {}
            chats.append(
                {
                    "id": d.get("id") or doc.id,
                    "title": d.get("title") or "New Chat",
                    "updated_at": d.get("updated_at"),
                    "created_at": d.get("created_at"),
                    "preview": d.get("preview") or history_preview(d.get("history", [])),
                }
            )
        return jsonify({"success": True, "chats": chats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "chats": []}), 500


@app.route("/api/chat/history", methods=["POST"])
def get_chat_history():
    """Return full history for a session_id."""
    try:
        data = request.get_json(force=True)
        session_id = (data.get("session_id") or "").strip()
        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        user_id = request_user_id()
        doc = chat_doc_ref(user_id, session_id).get()
        history = (doc.to_dict() or {}).get("history", []) if doc.exists else []
        return jsonify({"success": True, "history": history})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chat/delete", methods=["POST"])
def delete_chat():
    """Delete a stored chat session."""
    try:
        data = request.get_json(force=True)
        session_id = (data.get("session_id") or "").strip()
        if not session_id:
            return jsonify({"success": False, "error": "session_id is required"}), 400
        user_id = request_user_id()
        chat_doc_ref(user_id, session_id).delete()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chats/clear", methods=["POST"])
def clear_chats():
    """Delete all stored chat sessions for current user."""
    try:
        user_id = request_user_id()
        docs = list(chats_collection(user_id).stream())
        for doc in docs:
            doc.reference.delete()
        return jsonify({"success": True, "deleted": len(docs)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RED AI Assistant ")
    print("🤖 Persona: RED (named after the red, high-energy UI)")
    print("=" * 60)
    print(f"✅ Groq API Key Loaded: {GROQ_API_KEY[:9]}...***")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
