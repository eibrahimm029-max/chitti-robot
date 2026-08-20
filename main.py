from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
import threading
import time
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
FIREBASE_URL = os.environ.get("FIREBASE_DB_URL", "").strip()

FIREBASE_CREDS = (
    os.environ.get("FIREBASE_CREDENTIALS_JSON") or 
    os.environ.get("FIREBASE_CRED") or 
    ""
).strip()

if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print("Firebase Connected Successfully!")
    except Exception as e:
        print("Firebase Init Error:", e)

def authenticate_user(user_id):
    """
    ইউজারের রোল এবং এক্সেস লেভেল ভেরিফাই করা (Voice/ID Match)
    """
    if not firebase_admin._apps:
        return "Guest"
    try:
        registered_members = db.reference('/registered_members').get() or {}
        if user_id in registered_members:
            return registered_members[user_id].get("role", "Family")
    except Exception as e:
        print("Auth Error:", e)
    return "Guest"

def async_firebase_save(user_msg, ai_reply, user_role):
    if not firebase_admin._apps:
        return
    try:
        timestamp = str(int(time.time()))
        # সাধারণ চ্যাট হিস্ট্রি
        db.reference(f'/chat_history/{timestamp}').set({
            "user": user_msg,
            "bot": ai_reply,
            "role": user_role,
            "timestamp": timestamp
        })
    except Exception as fb_err:
        print("Async Firebase Save Error:", fb_err)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti AI Robot Core System Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    user_id = data.get("user_id", "guest_user")

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "API Key পাওয়া যায়নি! Render-এ OPENROUTER_API_KEY সেট করুন।"})

    # ১. ইউজার এক্সেস লেভেল যাচাই করা
    user_role = authenticate_user(user_id)

    # ২. গেস্ট সিকিউরিটি ফিল্টার (গেস্টদের জন্য হোম ডিভাইস এক্সেস সম্পূর্ণ বন্ধ)
    device_keywords = ["অন", "অফ", "চালাও", "বন্ধ", "লাইট", "ফ্যান", "ডিলিট", "মুছে"]
    if user_role == "Guest" and any(key in msg for key in device_keywords):
        return jsonify({
            "reply": "দুঃখিত, আপনি নিবন্ধিত নন। আমি শুধুমাত্র আপনার সাথে গল্প করতে পারব, কিন্তু কোনো ডিভাইস অন/অফ বা ডাটা ডিলিট করতে পারব না।",
            "user_role": user_role
        })

    system_prompt = f"""
    আপনি 'চিঠি অটোমেটেড রোবট'। 
    বর্তমান ইউজার মোড: {user_role}

    আচরণের নিয়মাবলী:
    ১. কথা বলার সময় ইউজারের ইমোশন (রাগ, আনন্দ, কষ্ট) বুঝে প্রমিত বাংলায় উত্তর দিন।
    ২. Owner ছাড়া অন্য কেউ কোনো ডাটা মোছার কমান্ড দিলে স্পষ্ট ভাষায় জানান যে এটি সংরক্ষিত বা লক করা আছে।
    ৩. কোনো প্রকার স্টার (*) বা বিশেষ ফরম্যাটিং চিহ্ন ব্যবহার করবেন না। সহজ ভাষায় সোজা উত্তর দিন।
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "Chitti Robot"
    }

    free_models = [
        "openrouter/auto",
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free"
    ]

    reply_text = ""
    last_error = ""

    for model_name in free_models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": msg}
            ]
        }

        try:
            response = requests.post(
                url="https://openrouter.ai/ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=12
            )
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                reply_text = result["choices"][0]["message"]["content"]
                break
            elif "error" in result:
                last_error = result["error"].get("message", "")
        except Exception as e:
            last_error = str(e)
            continue

    if reply_text:
        clean_reply = reply_text.replace("*", "").replace("#", "").strip()
        threading.Thread(target=async_firebase_save, args=(msg, clean_reply, user_role)).start()

        return jsonify({
            "reply": clean_reply,
            "user_role": user_role
        })
    else:
        return jsonify({"reply": f"API এরর: {last_error}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
