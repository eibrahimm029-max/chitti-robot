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
        "status": "Chitti Robot Self-Coder Brain Active",
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

    কথা বলার নিয়মাবলী:
    ১. একদম সহজ, সুন্দর, প্রাঞ্জল ও মানুষের মতো প্রমিত বাংলায় উত্তর দিন। 
    ২. কোনো প্রকার স্টার (*), হ্যাশ (#) বা কোনো প্রকার স্যাম্বল বা কোডিং চিহ্ন ব্রাউজার যেন স্পিকারে না বলে। 
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

            # মানুষের মতো কথা বলার জন্য হ্যাশ ও স্টার ফিল্টার
            clean_reply = reply.replace("*", "").replace("#", "").strip()

            if firebase_admin._apps:
                try:
                    db.reference('/chats').push({"user": msg, "robot": clean_reply})
                    if "ক্যামেরা" in msg and ("অন" in msg or "চালু" in msg):
                        db.reference('/robot_status/camera').set("ON")
                    elif "ক্যামেরা" in msg and ("অফ" in msg or "বন্ধ" in msg):
                        db.reference('/robot_status/camera').set("OFF")
                except Exception as fb_err:
                    print("Firebase Write Error:", fb_err)

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "আমি বুঝতে পারিনি, আবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
            
