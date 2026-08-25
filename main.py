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

db_firestore = None
if FIREBASE_CREDS and FIREBASE_URL and not firebase_admin._apps:
    try:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        db_firestore = firestore.client()
    except Exception as e:
        print("Firebase Init Error:", e)

# সুনির্দিষ্ট ডিভাইস ম্যাপিং
DEVICE_MAP = {
    "লাইট": "relay1", "relay1": "relay1", "রিলে ১": "relay1", "১ নাম্বার": "relay1", "এক নম্বর": "relay1",
    "ফ্যান": "relay2", "relay2": "relay2", "রিলে ২": "relay2", "২ নাম্বার": "relay2", "দুই নম্বর": "relay2",
    "রিলে ৩": "relay3", "relay3": "relay3", "৩ নাম্বার": "relay3", "তিন নম্বর": "relay3",
    "রিলে ৪": "relay4", "relay4": "relay4", "৪ নাম্বার": "relay4", "চার নম্বর": "relay4",
    "রিলে ৫": "relay5", "relay5": "relay5", "৫ নাম্বার": "relay5", "পাঁচ নম্বর": "relay5",
    "রিলে ৬": "relay6", "relay6": "relay6", "৬ নাম্বার": "relay6", "ছয় নম্বর": "relay6",
    "রিলে ৭": "relay7", "relay7": "relay7", "৭ নাম্বার": "relay7", "সাত নম্বর": "relay7",
    "রিলে ৮": "relay8", "relay8": "relay8", "৮ নাম্বার": "relay8", "আট নম্বর": "relay8"
}

def quick_device_control(msg):
    msg_lower = msg.lower()
    
    # শুধুমাত্র তখনই ডিভাইস কন্ট্রোল হিসেবে ধরবে যখন অন বা অফ জাতীয় শব্দ থাকবে
    is_on = any(w in msg_lower for w in ["চালু", "অন", "on", "জ্বালাও", "দাও", "ছাড়ো"])
    is_off = any(w in msg_lower for w in ["বন্ধ", "অফ", "off", "নিভাও", "তোল"])
    
    if not (is_on or is_off): 
        return None # ডিভাইস কমান্ড না হলে এটি নান (None) রিটার্ন করবে, তখন এআই চ্যাটে চলে যাবে

    target_device = None
    
    # সংখ্যা বা নাম দিয়ে টার্গেট রিলে খোঁজা
    if any(w in msg for w in ["৮", "আট"]):
        target_device = "relay8"
    elif any(w in msg for w in ["৭", "সাত"]):
        target_device = "relay7"
    elif any(w in msg for w in ["৬", "ছয়"]):
        target_device = "relay6"
    elif any(w in msg for w in ["৫", "পাঁচ"]):
        target_device = "relay5"
    elif any(w in msg for w in ["৪", "চার"]):
        target_device = "relay4"
    elif any(w in msg for w in ["৩", "তিন"]):
        target_device = "relay3"
    elif any(w in msg for w in ["২", "দুই"]):
        target_device = "relay2"
    elif any(w in msg for w in ["১", "এক", "লাইট"]):
        target_device = "relay1"
    else:
        for key, device in DEVICE_MAP.items():
            if key in msg_lower:
                target_device = device
                break

    if not target_device: 
        return None

    # অন নাকি অফ তা নিশ্চিত করা
    status = "ON" if (is_on and not is_off) else "OFF"
    
    # ইনস্ট্যান্ট ফায়ারবেসে ডাটা পাঠানো যাতে সফটওয়ারে টগল সুইচ এনেবল/ডিসএবল হয়ে যায়
    if firebase_admin._apps:
        try:
            db.reference(f'/devices/{target_device}').set(status)
        except Exception as ex:
            print("Firebase Write Error:", ex)

    device_num = target_device.replace("relay", "")
    action_name = "চালু" if status == "ON" else "বন্ধ"
    return f"ঠিক আছে, রিলে {device_num} {action_name} করা হলো।"

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg == "ping":
        return jsonify({"reply": "active"})

    # ১. প্রথমে চেক করবে এটি কোনো রিলে বা সুইচ অন-অফ করার কমান্ড কি না
    fast_device_reply = quick_device_control(msg)
    if fast_device_reply:
        return jsonify({"reply": fast_device_reply})

    # ২. যদি ডিভাইস কমান্ড না হয়, তবে এটি সাধারণ প্রশ্ন হিসেবে গণ্য হবে এবং এআই-এর কাছে যাবে
    if not OPENROUTER_KEY: 
        return jsonify({"reply": "এপিআই কি কনফিগার করা নেই!"})

    system_prompt = "You are 'Chitti', an AI robot assistant. Answer the user's question in pure Bengali, strictly 1 or 2 concise sentences. Do not generate any English words or thinking process."
    
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
        "max_tokens": 100
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply_text = result["choices"][0]["message"]["content"]
            
            # এআই মডেলের থিংকিং টেক্সট বা ট্যাগ ফিল্টার করে বাদ দেওয়া
            if "</think>" in reply_text:
                reply_text = reply_text.split("</think>")[-1]
            if "<think>" in reply_text:
                reply_text = reply_text.split("<think>")[0]
            
            clean_reply = reply_text.replace("*", "").replace("#", "").strip()
            
            # যদি এআই ভুলবশত পুরো ইংরেজি আউটপুট দেয়, তবে সুন্দর বাংলা মেসেজ দেওয়া
            if any(ord(c) < 128 for c in clean_reply[:5]) and not any(('\u0980' <= c <= '\u09ff') for c in clean_reply):
                clean_reply = "আপনার কথাটি বুঝতে পেরেছি, বিস্তারিত বলুন।"

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "বুঝতে পারিনি, আবার বলুন।"})
            
    except Exception:
        return jsonify({"reply": "সার্ভার ব্যস্ত আছে, আবার চেষ্টা করুন।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
