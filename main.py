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

GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()
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

def async_firebase_save(ui_action, user_msg, ai_reply):
    if not firebase_admin._apps:
        return
    try:
        timestamp = str(int(time.time()))
        db.reference(f'/chat_history/{timestamp}').set({
            "user": user_msg,
            "bot": ai_reply,
            "time": timestamp
        })

        if ui_action:
            action_type = ui_action.get("action")
            
            if action_type == "ADD":
                f_id = ui_action.get("feature_id", "feat_" + timestamp)
                db.reference(f'/features/{f_id}').set(ui_action)
            elif action_type == "DELETE":
                f_id = ui_action.get("feature_id")
                if f_id:
                    db.reference(f'/features/{f_id}').delete()
            elif action_type == "CLEAR_ALL":
                db.reference('/features').delete()

            if "bg_color" in ui_action:
                db.reference('/ui_config/bg_color').set(ui_action["bg_color"])
            if "app_title" in ui_action:
                db.reference('/ui_config/app_title').set(ui_action["app_title"])

    except Exception as fb_err:
        print("Async Firebase Save Error:", fb_err)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti Smooth AI Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not GROQ_KEY:
        return jsonify({"reply": "Groq API Key পাওয়া যায়নি! Render-এ GROQ_API_KEY সেট করুন।"})

    system_prompt = """
    আপনি 'চিঠি রোবট'—একটি অতি চতুর ও ডাইনামিক এআই। 
    
    আচরণের নিয়মাবলী:
    ১. ইউজার সাধারণ কথা বা গল্প করলে মানুষের মতো প্রমিত বাংলায় সহজ উত্তর দিন।
    ২. ইউজার কোনো বাটন, ইনপুট বা স্ক্রিনের ডাইনামিক পরিবর্তন করতে বললে উত্তরের সাথে JSON অ্যাকশন যুক্ত করবেন।

    JSON ফরম্যাট:
    [[UI_ACTION: {
        "action": "ADD",
        "feature_id": "unique_id",
        "bg_color": "red",
        "app_title": "নতুন নাম",
        "html_code": "<button onclick='alert(\"চালু হয়েছে\")'>বাটন</button>",
        "js_code": "console.log('Active');"
    }]]

    কথাবার্তার নিয়ম:
    - সম্পূর্ণ সহজ বাংলায় উত্তর দিন। কোনো স্টার (*), হ্যাশ (#) ব্যবহার করবেন না।
    """

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    # স্থায়ী একক মডেল - কোনো পরিবর্তন বা এরর আসবে না
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": msg}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            reply_text = result["choices"][0]["message"]["content"]
            ui_action = {}

            if "[[UI_ACTION:" in reply_text and "]]" in reply_text:
                try:
                    start_idx = reply_text.find("[[UI_ACTION:") + len("[[UI_ACTION:")
                    end_idx = reply_text.find("]]", start_idx)
                    json_str = reply_text[start_idx:end_idx].strip()
                    ui_action = json.loads(json_str)
                    reply_text = reply_text[:reply_text.find("[[UI_ACTION:")].strip()
                except Exception as json_err:
                    print("JSON extraction error:", json_err)

            clean_reply = reply_text.replace("*", "").replace("#", "").strip()

            threading.Thread(target=async_firebase_save, args=(ui_action, msg, clean_reply)).start()

            return jsonify({"reply": clean_reply})
        elif "error" in result:
            return jsonify({"reply": f"API এরর: {result['error'].get('message', 'অজানা সমস্যা')}"})
        else:
            return jsonify({"reply": "আমি কথাটি বুঝতে পারিনি, আরেকবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": f"সার্ভার এরর: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
                
