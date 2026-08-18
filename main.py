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

# Firebase Config (Environment Variables)
FIREBASE_URL = os.environ.get("FIREBASE_DB_URL", "").strip()
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS_JSON", "").strip()

# Firebase Init
if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_URL
        })
    except Exception as e:
        print("Firebase Init Error:", e)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Robot AI + Firebase Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    history = data.get("history", [])

    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো নির্দেশ বা বার্তা দিন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "Render-এ OPENROUTER_API_KEY সেট করা হয়নি!"})

    # ১. ফায়ারবেস থেকে বর্তমান ডাটা পড়া
    robot_memory = {}
    if firebase_admin._apps:
        try:
            ref = db.reference('/')
            robot_memory = ref.get() or {}
        except Exception as e:
            robot_memory = {"status": "Error reading Firebase"}

    # ২. সিস্টেম প্রম্পট (AI-কে মেমোরি ও নিয়ম শিখিয়ে দেওয়া)
    system_prompt = f"""
    আপনি 'চিঠি রোবট'—একটি স্মার্ট এআই এজেন্ট ও রোবটের মেধা।
    
    বর্তমান ফায়ারবেস মেমোরি ও সেন্সর ডাটা:
    {json.dumps(robot_memory, ensure_ascii=False)}

    আপনার দায়িত্ব ও নিয়মাবলী:
    ১. ব্যবহারকারী আপনার সাথে মুখে কথা বলছে বা লিখছে। তার কথা গভীরভাবে বুঝে উত্তর দিন।
    ২. ব্যবহারকারীর নির্দেশ অনুযায়ী কাজ করুন (যেমন: ক্যামেরা চালুর অনুরোধ, ওনার নাম সেভ রাখা, কিংবা সেন্সরের অবস্থা জানানো)।
    ৩. উত্তর সবসময় সহজ, স্পষ্ট ও সুন্দর বাংলায় দিন।
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
                "HTTP-Referer": "https://ahimm029-max.github.io",
                "X-Title": "Chitti Firebase Robot",
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

            # ৩. ডাইনামিক ফায়ারবেস আপডেট লজিক
            if firebase_admin._apps:
                try:
                    ref = db.reference('/robot_logs')
                    ref.push({
                        "user_msg": msg,
                        "bot_reply": reply
                    })

                    # কমান্ড চিহ্নিত করে ফায়ারবেসে ফ্ল্যাগ আপডেট
                    if "ক্যামেরা" in msg and ("অন" in msg or "চালু" in msg):
                        db.reference('/controls/camera').set("ON")
                    elif "ক্যামেরা" in msg and ("অফ" in msg or "বন্ধ" in msg):
                        db.reference('/controls/camera').set("OFF")
                except Exception as fb_err:
                    print("Firebase Write Error:", fb_err)

            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": "আমি বুঝতে পারিনি, আবার বলবেন?"})

    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
        
