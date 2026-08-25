from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests, json, time, random
import firebase_admin
from firebase_admin import credentials, db, firestore

app = Flask(__name__)
CORS(app)

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
FIREBASE_URL = os.environ.get("FIREBASE_DB_URL", "").strip()
FIREBASE_CREDS = (os.environ.get("FIREBASE_CREDENTIALS_JSON") or os.environ.get("FIREBASE_CRED") or "").strip()

# ফায়ারবেস ও ফায়ারস্টোর ইনিশিয়ালাইজেশন
db_firestore = None
if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        db_firestore = firestore.client()
        print("Firebase & Firestore Connected Successfully!")
    except Exception as e:
        print("Firebase Init Error:", e)

pending_challenges = {}
is_voice_recording_active = False

def save_voice_to_firestore(user_id, raw_audio_data):
    if not is_voice_recording_active or not raw_audio_data or not db_firestore:
        return
    try:
        current_time = time.strftime("%Y-%m-%d_%H-%M-%S")
        doc_ref = db_firestore.collection('voice_recordings').document(f"{user_id}_{current_time}")
        doc_ref.set({
            "speaker_id": user_id,
            "timestamp": current_time,
            "audio_file_data": raw_audio_data,
            "format": "audio/wav"
        })
    except Exception as e:
        print("Firestore Save Error:", e)

# ----------------- ৮টি রিলে ও ডিভাইস ম্যাপ -----------------
DEVICE_MAP = {
    "লাইট": "relay1", "relay1": "relay1", "রিলে ১": "relay1",
    "ফ্যান": "relay2", "relay2": "relay2", "রিলে ২": "relay2",
    "রিলে ৩": "relay3", "relay3": "relay3",
    "রিলে ৪": "relay4", "relay4": "relay4",
    "রিলে ৫": "relay5", "relay5": "relay5",
    "রিলে ৬": "relay6", "relay6": "relay6",
    "রিলে ৭": "relay7", "relay7": "relay7",
    "রিলে ৮": "relay8", "relay8": "relay8"
}

def quick_device_control(msg, user_role):
    msg_lower = msg.lower()
    is_on = any(w in msg_lower for w in ["চালু", "অন", "on", "জ্বালাও"])
    is_off = any(w in msg_lower for w in ["বন্ধ", "অফ", "off", "নিভাও"])
    if not (is_on or is_off): return None

    target_device = None
    for key, device in DEVICE_MAP.items():
        if key in msg_lower:
            target_device = device
            break

    if not target_device: return None

    status = "ON" if is_on else "OFF"
    if firebase_admin._apps:
        db.reference(f'/devices/{target_device}').set(status)

    return f"ঠিক আছে, {target_device.upper()} {status} করা হলো।"

@app.route('/chat', methods=['POST'])
def chat():
    global is_voice_recording_active
    data = request.json or {}
    msg = data.get("message", "").strip()
    user_id = data.get("user_id", "owner")
    raw_audio_data = data.get("audio_data", "")

    if raw_audio_data:
        save_voice_to_firestore(user_id, raw_audio_data)

    if "সারাদিনের কথা রেকর্ড করো" in msg or "রেকর্ড অন করো" in msg:
        is_voice_recording_active = True
        return jsonify({"reply": "সারাদিনের সরাসরি অরিজিনাল ভয়েস রেকর্ড মোড চালু হলো। ফায়ারস্টোরে ডাটা জমা হচ্ছে।"})
    
    if "রেকর্ড বন্ধ করো" in msg or "রেকর্ড অফ করো" in msg:
        is_voice_recording_active = False
        return jsonify({"reply": "ভয়েস রেকর্ড মোড বন্ধ করা হয়েছে।"})

    fast_device_reply = quick_device_control(msg, "Owner")
    if fast_device_reply:
        return jsonify({"reply": fast_device_reply})

    if user_id in pending_challenges:
        if pending_challenges[user_id] in msg:
            del pending_challenges[user_id]
            if firebase_admin._apps: db.reference('/chat_history').delete()
            return jsonify({"reply": "ওনার ভেরিফিকেশন সফল! চ্যাট হিস্ট্রি মুছে ফেলা হয়েছে।"})
        else:
            return jsonify({"reply": "ভুল পিন কোড!"})

    if any(word in msg.lower() for word in ["ডিলিট", "মুছে", "সাফ", "কাটো"]):
        if any(w in msg.lower() for w in ["হিসাব", "সিস্টেম", "ডাটাবেজ"]):
            return jsonify({"reply": "সিস্টেম বা হিসাবের ডাটা মোছা যাবে না."})

        if any(w in msg.lower() for w in ["চ্যাট", "মেসেজ", "কথা"]):
            random_pin = str(random.randint(1000, 9999))
            pending_challenges[user_id] = random_pin
            return jsonify({"reply": f"প্রাইভেসি পিন কোডটি বলুন: {random_pin}", "challenge_code": random_pin})

    if not OPENROUTER_KEY: return jsonify({"reply": "API Key নেই!"})

    system_prompt = "আপনি 'চিঠি'। সর্বোচ্চ ১০ শব্দে সংক্ষেপে প্রমিত বাংলায় উত্তর দিন।"
    headers = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json", "HTTP-Referer": "https://github.com"}
    payload = {"model": "openrouter/free", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": msg}], "max_tokens": 50}

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=5)
        result = response.json()
        reply_text = result["choices"][0]["message"]["content"] if "choices" in result else "বুঝতে পারিনি."
        clean_reply = reply_text.replace("*", "").replace("#", "").strip()
        return jsonify({"reply": clean_reply})
    except Exception:
        return jsonify({"reply": "সংযোগের সমস্যা হয়েছে."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
