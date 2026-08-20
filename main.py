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
            "timestamp": timestamp
        })

        if ui_action:
            action_type = ui_action.get("action")
            feature_id = ui_action.get("feature_id", "feature_" + timestamp)

            db.reference(f'/commands/{timestamp}').set({
                "command_type": action_type,
                "target_id": feature_id,
                "details": ui_action
            })

            if action_type == "ADD":
                db.reference(f'/active_features/{feature_id}').set(ui_action)
            elif action_type == "DELETE":
                if feature_id:
                    db.reference(f'/active_features/{feature_id}').delete()
            elif action_type == "CLEAR_ALL":
                db.reference('/active_features').delete()

            if "bg_color" in ui_action:
                db.reference('/ui_config/bg_color').set(ui_action["bg_color"])
            if "app_title" in ui_action:
                db.reference('/ui_config/app_title').set(ui_action["app_title"])

    except Exception as fb_err:
        print("Async Firebase Save Error:", fb_err)

def get_current_app_context():
    """ফায়ারবেস থেকে একটিভ ফিচার এবং ব্যাকগ্রাউন্ড ডাটা পড়ে এআইকে জানানোর জন্য"""
    context_info = ""
    if firebase_admin._apps:
        try:
            active_feats = db.reference('/active_features').get()
            if active_feats:
                context_info += f"\nবর্তমানে স্ক্রিনে থাকা একটিভ ফিচারসমূহ: {json.dumps(active_feats, ensure_ascii=False)}"
            else:
                context_info += "\nবর্তমানে স্ক্রিনে কোনো বাড়তি ফিচার বা বাটন নেই।"
        except Exception as e:
            print("Context Read Error:", e)
    return context_info

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti Fully Integrated Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "API Key পাওয়া যায়নি! Render-এ OPENROUTER_API_KEY সেট করুন।"})

    # ফায়ারবেস থেকে বর্তমান স্টেট নিয়ে প্রম্পটে যুক্ত করা হচ্ছে
    app_context = get_current_app_context()

    system_prompt = f"""
    আপনি 'চিঠি অটোমেটেড রোবট'। আপনি ইউজারের স্ক্রিন ও ফায়ারবেস ডেটাবেজ সরাসরি পর্যবেক্ষণ করছেন।

    বর্তমান সিস্টেম স্টেট:{app_context}

    আচরণের নিয়মাবলী:
    ১. ইউজার যখনই স্ক্রিনের কোনো কিছু মোছার কথা বলবে, আপনি কখনো বলবেন না যে "আমি ডাটাবেস দেখতে পারি না"।
    ২. কোনো ফিচার বা ভিডিও মুছতে বললে সাথে সাথে JSON ফরম্যাটে 'DELETE' বা 'CLEAR_ALL' একশন পাঠাবেন।
    ৩. উত্তর সবসময় সহজ প্রমিত বাংলায় দিবেন। কোনো প্রকার স্টার (*) বা বিশেষ চিহ্ন ব্যবহার করবেন না।

    JSON ফরম্যাট:
    [[UI_ACTION: {{
        "action": "DELETE",
        "feature_id": "video_player"
    }}]]
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
            
