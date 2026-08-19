from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
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
        print("Firebase Connected!")
    except Exception as e:
        print("Firebase Init Error:", e)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti Dynamic Self-Building AI Active"})

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
    আপনি 'চিঠি রোবট'—একটি সম্পূর্ণ ডায়নামিক ও স্বয়ংক্রিয় এআই সিস্টেম। 
    ইউজার যদি অ্যাপে কোনো নতুন ফিচার, নতুন বাটন, ফাইল আপলোড, স্লাইডার, ক্যামেরা বা যেকোনো এলিমেন্ট যুক্ত করতে বলে, তবে আপনি আপনার উত্তরের শেষে একটি JSON কোড ব্লক যুক্ত করবেন যা দিয়ে স্ক্রিনে নতুন HTML বা লজিক রেন্ডার হবে।

    JSON ফরম্যাটটি অবশ্যই এই রকম হতে হবে:
    [[UI_UPDATE: {
        "bg_color": "red",
        "app_title": "নতুন নাম",
        "custom_html": "<button class='dynamic-btn' onclick='alert(\\\"হ্যালো\\\")'>নতুন ফিচার</button>",
        "custom_js": "console.log('Custom Logic Active');"
    }]]

    কথা বলার নিয়মাবলী:
    ১. একদম সহজ, প্রমিত বাংলায় কথা বলুন।
    ২. বাংলা উত্তরের অংশে কোনো স্টার (*), হ্যাশ (#) বা কোডিং সিম্বল রাখবেন না।
    """

    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": msg})

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openrouter/auto",
                "messages": messages
            }
        )

        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            reply = result["choices"][0]["message"]["content"]
            ui_updates = {}

            if "[[UI_UPDATE:" in reply and "]]" in reply:
                try:
                    start_idx = reply.find("[[UI_UPDATE:") + len("[[UI_UPDATE:")
                    end_idx = reply.find("]]", start_idx)
                    json_str = reply[start_idx:end_idx].strip()
                    ui_updates = json.loads(json_str)
                    reply = reply[:reply.find("[[UI_UPDATE:")].strip()
                except Exception as json_err:
                    print("JSON Extraction Error:", json_err)

            clean_reply = reply.replace("*", "").replace("#", "").strip()

            if firebase_admin._apps and ui_updates:
                try:
                    for key, val in ui_updates.items():
                        db.reference(f'/ui_config/{key}').set(val)
                except Exception as fb_err:
                    print("Firebase Write Error:", fb_err)

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "আমি বুঝতে পারিনি, আবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
