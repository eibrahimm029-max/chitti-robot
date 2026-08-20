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
    return jsonify({"status": "Chitti OpenRouter AI Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "API Key পাওয়া যায়নি! Render-এ OPENROUTER_API_KEY সেট করুন।"})

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
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
        "X-Title": "Chitti Robot"
    }

    # OpenRouter-এর স্থায়ী ফ্রি অটো-রাউটিং এবং ১০০% সচল ফ্রি মডেলসমূহ
    free_models = [
        "openrouter/auto",
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
        "qwen/qwen-2.5-7b-instruct:free"
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
                url="https://openrouter.ai/api/v1/chat/completions",
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
    else:
        return jsonify({"reply": f"API এরর: {last_error}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
