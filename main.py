from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import json
import base64
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
FIREBASE_URL = os.environ.get("FIREBASE_DB_URL", "").strip()
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "chitti-robot").strip()
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "eibrahimm029-max").strip()

# Firebase Initialisation
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
    return jsonify({
        "status": "Chitti Robot Dynamic Control & AI Brain Active",
        "firebase_connected": bool(firebase_admin._apps),
        "github_auto_coder": bool(GITHUB_TOKEN)
    })

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    history = data.get("history", [])

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "Render-এ OPENROUTER_API_KEY সেট করা নেই!"})

    robot_memory = {}
    if firebase_admin._apps:
        try:
            robot_memory = db.reference('/').get() or {}
        except Exception as e:
            robot_memory = {"error": str(e)}

    system_prompt = f"""
    আপনি 'চিঠি রোবট'—একটি স্বয়ংক্রিয় বুদ্ধিমান এআই এবং ওনারের নির্দেশ পালনকারী সহকারী। 
    আপনার বর্তমান ডাটাবেজ মেমোরি:
    {json.dumps(robot_memory, ensure_ascii=False)}

    আপনার একটি বিশেষ ক্ষমতা রয়েছে:
    ওনার (ইউজার) যদি অ্যাপের কোনো ডিজাইন, বাটন অন/অফ, কালার, টাইটেল বা লজিক পরিবর্তন করার কথা বলে, তবে আপনি আপনার উত্তরের শেষে একটি JSON আপডেট ব্লক যুক্ত করবেন।
    
    JSON ফরম্যাটটি অবশ্যই এইরকম হতে হবে:
    [[UI_UPDATE: {{"bg_color": "red", "show_camera": false, "app_title": "নতুন নাম", "night_mode": true}}]]

    কথা বলার নিয়মাবলী:
    ১. একদম সহজ, সুন্দর, প্রাঞ্জল ও মানুষের মতো প্রমিত বাংলায় উত্তর দিন। 
    ২. বাংলা উত্তরের অংশে কোনো প্রকার স্টার (*), হ্যাশ (#) বা কোনো প্রকার স্যাম্বল বা কোডিং চিহ্ন রাখবেন না, কারণ এগুলো স্পিকারে পড়া হবে।
    ৩. আপনি নিজেই ফায়ারবেস এবং গিটহাব কন্ট্রোল করতে সক্ষম।
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

            # ডাইনামিক UI কন্ট্রোল চেক (JSON Extract)
            ui_updates = {}
            if "[[UI_UPDATE:" in reply and "]]" in reply:
                try:
                    start_idx = reply.find("[[UI_UPDATE:") + len("[[UI_UPDATE:")
                    end_idx = reply.find("]]", start_idx)
                    json_str = reply[start_idx:end_idx].strip()
                    ui_updates = json.loads(json_str)
                    # আসল উত্তর থেকে কমান্ড অংশটুকু সরিয়ে ফেলা
                    reply = reply[:reply.find("[[UI_UPDATE:")].strip()
                except Exception as json_err:
                    print("JSON Parse Error:", json_err)

            # মানুষের মতো কথা বলার জন্য হ্যাশ ও স্টার ফিল্টার
            clean_reply = reply.replace("*", "").replace("#", "").strip()

            if firebase_admin._apps:
                try:
                    # চ্যাট হিস্ট্রি জমা রাখা
                    db.reference('/chats').push({"user": msg, "robot": clean_reply})
                    
                    # ১. ক্যামেরা স্ট্যাটাস লজিক
                    if "ক্যামেরা" in msg and ("অন" in msg or "চালু" in msg):
                        db.reference('/robot_status/camera').set("ON")
                    elif "ক্যামেরা" in msg and ("অফ" in msg or "বন্ধ" in msg):
                        db.reference('/robot_status/camera').set("OFF")

                    # ২. এআই কর্তৃক পাওয়া ডাইনামিক UI/লজিক আপডেট ফায়ারবেসে সেভ করা
                    if ui_updates:
                        for key, val in ui_updates.items():
                            db.reference(f'/ui_config/{key}').set(val)

                    # ৩. ম্যানুয়াল ভয়েস কমান্ড ফিল্টার (অতিরিক্ত সুরক্ষার জন্য)
                    if "রং" in msg or "কালার" in msg:
                        if "লাল" in msg:
                            db.reference('/ui_config/bg_color').set("red")
                        elif "সবুজ" in msg:
                            db.reference('/ui_config/bg_color').set("green")
                        elif "কালো" in msg or "ডার্ক" in msg:
                            db.reference('/ui_config/bg_color').set("#121212")
                        elif "সাদা" in msg:
                            db.reference('/ui_config/bg_color').set("#ffffff")

                    if "বাটন" in msg:
                        if "বন্ধ" in msg or "লুকিয়ে" in msg or "হাইড" in msg:
                            db.reference('/ui_config/show_buttons').set(False)
                        elif "দেখা" in msg or "অন" in msg or "চালু" in msg:
                            db.reference('/ui_config/show_buttons').set(True)

                except Exception as fb_err:
                    print("Firebase Write Error:", fb_err)

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "আমি বুঝতে পারিনি, আবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
