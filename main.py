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
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()

if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print("Firebase Connected Successfully!")
    except Exception as e:
        print("Firebase Init Error:", e)

# ব্যাকগ্রাউন্ডে ফায়ারবেসে ডাটা জমা করার ফাংশন (যাতে ১-২ সেকেন্ডে দ্রুত রেসপন্স পাওয়া যায়)
def async_firebase_save(ui_action, user_msg, ai_reply):
    if not firebase_admin._apps:
        return
    try:
        # ১. সারাদিনের কথোপকথন আলাদা ফোল্ডারে সেভ রাখা
        timestamp = str(int(time.time()))
        db.reference(f'/chat_history/{timestamp}').set({
            "user": user_msg,
            "bot": ai_reply,
            "time": timestamp
        })

        # ২. ডাইনামিক UI ও বাটন হ্যান্ডলিং
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
    return jsonify({"status": "Chitti Super Fast AI Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    history = data.get("history", [])

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "OpenRouter API Key পাওয়া যায়নি!"})

    system_prompt = """
    আপনি 'চিঠি রোবট'—একটি অত্যন্ত চতুর ও দ্রুতগতির স্মার্ট এআই। 
    
    আপনার আচরণের নিয়মাবলী:
    ১. ইউজার সাধারণ কথা বা গল্প করলে সাধারণ মানুষের মতো প্রমিত বাংলায় উত্তর দিন। তখন কোনো বাটন বা ফিচার বানাবেন না।
    ২. ইউজার যদি স্পষ্ট কোনো ফিচার/বাটন/ইনপুট/ক্যামেরা/প্লাস আইকন যোগ করতে বলে বা কোনো বাটন ডিলিট করতে বলে, কেবল তখনই উত্তরের সাথে নিচে দেওয়া JSON অ্যাকশন যুক্ত করবেন।

    JSON ফরম্যাট:
    [[UI_ACTION: {
        "action": "ADD" (অথবা "DELETE" বা "CLEAR_ALL"),
        "feature_id": "unique_id",
        "bg_color": "red" (যদি কালার বদলাতে বলে),
        "app_title": "নতুন টাইটেল" (যদি নাম বদলাতে বলে),
        "html_code": "<button onclick='alert(\"চালু হয়েছে\")'>বাটন</button>",
        "js_code": "console.log('Active');"
    }]]

    কথাবার্তার নিয়ম:
    - সম্পূর্ণ সহজ ও স্বাভাবিক বাংলায় উত্তর দিন।
    - বাংলা টেক্সটের ভেতর কোনো স্টার (*), হ্যাশ (#) ব্যবহার করবেন না।
    """

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-6:]:  # কথোপকথন দ্রুত রাখার জন্য শেষ ৬টি মেসেজ পাঠানো হচ্ছে
        messages.append(h)
    messages.append({"role": "user", "content": msg})

    try:
        # সুপার-ফাস্ট গুগল জেমিনি প্রসেসর ব্যবহার
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": messages,
                "temperature": 0.7
            },
            timeout=8
        )

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            reply = result["choices"][0]["message"]["content"]
            ui_action = {}

            if "[[UI_ACTION:" in reply and "]]" in reply:
                try:
                    start_idx = reply.find("[[UI_ACTION:") + len("[[UI_ACTION:")
                    end_idx = reply.find("]]", start_idx)
                    json_str = reply[start_idx:end_idx].strip()
                    ui_action = json.loads(json_str)
                    reply = reply[:reply.find("[[UI_ACTION:")].strip()
                except Exception as json_err:
                    print("JSON Extraction Error:", json_err)

            clean_reply = reply.replace("*", "").replace("#", "").strip()

            # ফায়ারবেসে তথ্য জমানো ব্যাকগ্রাউন্ড থ্রেডে পাঠিয়ে সাথে সাথে ইউজারকে রেসপন্স পাঠানো
            threading.Thread(target=async_firebase_save, args=(ui_action, msg, clean_reply)).start()

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "আমি বুঝতে পারিনি, আবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": "দুঃখিত, উত্তর প্রসেস করতে কিছুটা সমস্যা হয়েছে।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
