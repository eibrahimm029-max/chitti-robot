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

# ----------------- ৮টি রিলে ও ডিভাইস ম্যাপ (ইনস্ট্যান্ট কন্ট্রোল) -----------------
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

def quick_device_control(msg):
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
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    # রেন্ডার সার্ভার সজাগ রাখার কিপ-অ্যালাইভ পিং
    if msg == "ping":
        return jsonify({"reply": "active"})

    # হার্ডওয়্যার বা রিলে কমান্ড তাৎক্ষণিকভাবে এক্সিকিউট করা (বিনা ল্যাগে)
    fast_device_reply = quick_device_control(msg)
    if fast_device_reply:
        return jsonify({"reply": fast_device_reply})

    if not OPENROUTER_KEY: 
        return jsonify({"reply": "এপিআই কি (API Key) কনফিগার করা নেই!"})

    # এআই প্রম্পট: যেকোনো বড় বা ছোট প্রশ্নের সাবলীল উত্তর দেওয়ার জন্য
    system_prompt = "আপনি 'চিঠি', একটি এআই রোবট। যেকোনো জটিল বা সাধারণ প্রশ্নের বুদ্ধিদীপ্ত ও সুন্দর বাংলা উত্তর দেবেন।"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}", 
        "Content-Type": "application/json", 
        "HTTP-Referer": "https://github.com"
    }
    payload = {
        "model": "openrouter/free", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": msg}
        ], 
        "max_tokens": 150
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply_text = result["choices"][0]["message"]["content"]
            clean_reply = reply_text.replace("*", "").replace("#", "").strip()
            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "দুঃখিত, এই মুহূর্তে আমি বুঝতে পারিনি। আবার বলুন।"})
            
    except Exception as e:
        return jsonify({"reply": "সার্ভার এই মুহূর্তে ব্যস্ত আছে, অনুগ্রহ করে আবার চেষ্টা করুন।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
