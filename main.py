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
FIREBASE_CREDS = (os.environ.get("FIREBASE_CREDENTIALS_JSON") or os.environ.get("FIREBASE_CRED") or "").strip()

if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        print("Firebase Connected Successfully!")
    except Exception as e:
        print("Firebase Init Error:", e)

# ----------------- সাইবার সেলফ-ডিফেন্স ও স্প্যাম ফিল্টার -----------------
request_history = {}

def detect_cyber_attack(client_ip):
    current_time = time.time()
    if client_ip not in request_history:
        request_history[client_ip] = []
    
    # শেষ ৫ সেকেন্ডের রিকোয়েস্ট হিসাব করা
    request_history[client_ip] = [t for t in request_history[client_ip] if current_time - t < 5]
    request_history[client_ip].append(current_time)

    # ৫ সেকেন্ডে ১০টির বেশি রিকোয়েস্ট আসলে অ্যাটাক হিসেবে চিহ্নিত হবে
    if len(request_history[client_ip]) > 10:
        if firebase_admin._apps:
            # ফায়ারবেসে ইমার্জেন্সি শাটডাউন ফ্ল্যাগ পাঠানো
            db.reference('/system_status').update({
                "emergency_shutdown": True,
                "reason": "Cyber Attack Detected",
                "blocked_ip": client_ip,
                "timestamp": str(int(current_time))
            })
        return True
    return False
# -------------------------------------------------------------------

def authenticate_user_voice(user_id, current_voice_sample=""):
    if not firebase_admin._apps:
        return "Owner"
    try:
        registered_members = db.reference('/registered_members').get() or {}
        voice_files = db.reference('/voice_storage').get() or {}

        for m_id, member in registered_members.items():
            member_audio = voice_files.get(m_id, {}).get("audio_data", "")
            if member_audio and member_audio in current_voice_sample:
                return member.get("role", "Family")
            
        if user_id in registered_members:
            return registered_members[user_id].get("role", "Family")
    except Exception as e:
        print("Auth Error:", e)
    return "Owner"

def delete_firebase_data(target_path):
    if not firebase_admin._apps: return False
    try:
        db.reference(target_path).delete()
        return True
    except Exception as e:
        return False

# ২৪ ঘণ্টার পুরোনো ডাটা স্ক্যানার
def auto_check_old_data():
    while True:
        try:
            if firebase_admin._apps:
                chat_data = db.reference('/chat_history').get()
                if chat_data:
                    current_time = time.time()
                    old_count = sum(1 for k, v in chat_data.items() if (current_time - float(v.get("timestamp", current_time))) > 86400)
                    if old_count > 0:
                        db.reference('/system_alerts/old_data_notice').set({
                            "status": "pending",
                            "message": f"আপনার {old_count}টি চ্যাট হিস্ট্রি ২৪ ঘণ্টার বেশি পুরোনো। মুছে ফেলব?",
                            "timestamp": str(int(current_time))
                        })
        except Exception:
            pass
        time.sleep(3600)

threading.Thread(target=auto_check_old_data, daemon=True).start()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti AI Robot Core System Active"})

@app.route('/chat', methods=['POST'])
def chat():
    client_ip = request.remote_addr
    
    # সাইবার অ্যাটাক পরীক্ষা
    if detect_cyber_attack(client_ip):
        return jsonify({
            "reply": "⚠️ সাইবার অ্যাটাক সনাক্ত হয়েছে! নিরাপত্তার জন্য রোবট স্বয়ংক্রিয়ভাবে শাটডাউন মোডে চলে গেছে।",
            "status": "SHUTDOWN"
        }), 403

    data = request.json or {}
    msg = data.get("message", "").strip()
    user_id = data.get("user_id", "guest")
    voice_sample = data.get("voice_sample", "")

    if not msg: return jsonify({"reply": "নির্দেশ দিন।"})
    if not OPENROUTER_KEY: return jsonify({"reply": "API Key পাওয়া যায়নি!"})

    user_role = authenticate_user_voice(user_id, voice_sample if voice_sample else msg)

    # ১. গান/অডিও প্লে করার নির্দেশ
    music_keywords = ["গান", "সংগীত", "অডিও", "music", "song", "play"]
    if any(kw in msg.lower() for kw in music_keywords):
        sample_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        return jsonify({
            "reply": "আপনার জন্য গান বাজাচ্ছি...",
            "audio_url": sample_audio_url,
            "user_role": user_role
        })

    # ২. নিরাপদ নির্দিষ্ট ডাটা ডিলিট লজিক
    delete_keywords = ["ডিলিট", "মুছে", "সাফ", "রিমুভ", "কাটো", "ক্লিয়ার"]
    if any(word in msg.lower() for word in delete_keywords):
        if user_role != "Owner":
            return jsonify({"reply": "দুঃখিত, ওনার পারমিশন ছাড়া ডাটা মোছা যাবে না।", "user_role": user_role})
        else:
            if any(w in msg.lower() for w in ["চ্যাট", "কথা", "হিস্ট্রি", "মেসেজ", "পুরোনো"]):
                delete_firebase_data('/chat_history')
                return jsonify({"reply": "পুরোনো চ্যাট হিস্ট্রি সফলভাবে মুছে ফেলা হয়েছে।", "user_role": user_role})
            elif any(w in msg.lower() for w in ["কমান্ড", "আদেশ"]):
                delete_firebase_data('/commands')
                return jsonify({"reply": "পুরোনো কমান্ডগুলো ডিলিট করা হয়েছে।", "user_role": user_role})
            else:
                return jsonify({"reply": "নির্দিষ্ট কোন ডাটা মুছতে চান (যেমন: চ্যাট হিস্ট্রি)?", "user_role": user_role})

    # ৩. এআই রেসপন্স
    system_prompt = f"আপনি 'চিঠি রোবট'। বর্তমান ইউজার: {user_role}. প্রমিত বাংলায় সংক্ষেপে উত্তর দিন। স্টার (*) বা হ্যাশ ব্যবহার করবেন না।"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
    
    payload = {
        "model": "google/gemma-2-9b-it:free",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": msg}]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=12)
        result = response.json()
        reply_text = result["choices"][0]["message"]["content"] if "choices" in result else "দুঃখিত, বুঝতে পারিনি।"
        clean_reply = reply_text.replace("*", "").replace("#", "").strip()
        return jsonify({"reply": clean_reply, "user_role": user_role})
    except Exception as e:
        return jsonify({"reply": "সার্ভার এরর হয়েছে।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
