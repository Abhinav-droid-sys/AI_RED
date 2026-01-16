from flask import Flask, request, jsonify, render_template, render_template_string, send_from_directory
from groq import Groq
import os
from dotenv import load_dotenv
from datetime import datetime

# ===== FIREBASE ADDITIONS =====
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

# =========================
# FIREBASE INIT (ADDED)
# =========================
if not firebase_admin._apps:
    cred = credentials.Certificate("Database_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================
# GROQ CONFIG (UNCHANGED)
# =========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# =========================
# FIREBASE AUTH HELPER
# =========================
def verify_firebase_token(req):
    auth_header = req.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split("Bearer ")[1]
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        return None

# =========================
# ROUTES (UNCHANGED)
# =========================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

# =========================
# CHAT API (ENHANCED, NOT REWRITTEN)
# =========================
@app.route("/api/chat", methods=["POST"])
def chat():
    # 🔐 AUTH GUARD
    user = verify_firebase_token(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    uid = user["uid"]

    data = request.json
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "Empty prompt"}), 400

    # ===== LOAD CHAT HISTORY (NEW) =====
    chat_ref = (
        db.collection("users")
        .document(uid)
        .collection("chats")
        .document("default")
    )

    chat_doc = chat_ref.get()
    history = chat_doc.to_dict().get("messages", []) if chat_doc.exists else []

    # ===== APPEND USER MESSAGE =====
    history.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.utcnow()
    })

    # ===== GROQ CALL (UNCHANGED BEHAVIOR) =====
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "You are RED, a sharp, intelligent AI assistant."},
            *[
                {"role": m["role"], "content": m["content"]}
                for m in history[-10:]
            ]
        ],
        temperature=0.7
    )

    ai_response = completion.choices[0].message.content

    # ===== APPEND AI MESSAGE =====
    history.append({
        "role": "assistant",
        "content": ai_response,
        "timestamp": datetime.utcnow()
    })

    # ===== SAVE TO FIRESTORE =====
    chat_ref.set({
        "messages": history[-40:],  # prevent unlimited growth
        "updated_at": datetime.utcnow()
    }, merge=True)

    return jsonify({"response": ai_response})

# =========================
# HEALTH CHECK (UNCHANGED)
# =========================
@app.route("/health")
def health():
    try:
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =========================
# RUN
# =========================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RED AI Assistant - Powered by Groq")
    print("🤖 Persona: RED (named after the red, high-energy UI)")
    print("=" * 60)
    print(f"✅ Groq API Key Loaded: {GROQ_API_KEY[:10]}...***")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
