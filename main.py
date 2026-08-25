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

# সব ধরনের রিলের নাম এবং বাংলা উচ্চারণ ম্যাপিং যাতে ভুল না হয়
DEVICE_MAP = {
    "লাইট": "relay1", "relay1": "relay1", "রিলে ১": "relay1", "১ নাম্বার": "relay1",
    "ফ্যান": "relay2", "relay2": "relay2", "রিলে ২": "relay2", "২ নাম্বার": "relay2",
    "রিলে ৩": "relay3", "relay3": "relay3", "৩ নাম্বার": "relay3",
    "রিলে ৪": "relay4", "relay4": "relay4", "৪ নাম্বার": "relay4",
    "রিলে ৫": "relay5", "relay5": "relay5", "৫ নাম্বার": "relay5",
    "রিলে ৬": "relay6", "relay6": "relay6", "৬ নাম্বার": "relay6",
    "রিলে ৭": "relay7", "relay7": "relay7", "৭ নাম্বার": "relay7",
    "রিলে ৮": "relay8", "relay8": "relay8", "৮ নাম্বার": "relay8"
}

def quick_device_control(msg):
    msg_lower = msg.lower()
    
    # অন বা অফ স্টেট নির্ধারণ
    is_on = any(w in msg_lower for w in ["চালু", "অন", "on", "জ্বালাও", "দাও"])
    is_off = any(w in msg_lower for w in ["বন্ধ", "অফ", "off", "নিভাও", "তোল"])
    
    if not (is_on or is_off): 
        return None

    target_device = None
    
    # বিশেষ শব্দ চেক (যেমন: রিলে ৮ বা আট নম্বর)
    if "৮" in msg or "আট" in msg:
        target_device = "relay8"
    elif "৭" in msg or "সাত" in msg:
        target_device = "relay7"
    elif "৬" in msg or "ছয়" in msg:
        target_device = "relay6"
    elif "৫" in msg or "পাঁচ" in msg:
        target_device = "relay5"
    elif "৪" in msg or "চার" in msg:
        target_device = "relay4"
    elif "৩" in msg or "তিন" in msg:
        target_device = "relay3"
    elif "২" in msg or "দুই" in msg:
        target_device = "relay2"
    elif "১" in msg or "এক" in msg or "লাইট" in msg:
        target_device = "relay1"
    else:
        for key, device in DEVICE_MAP.items():
            if key in msg_lower:
                target_device = device
                break

    if not target_device: 
        return None

    status = "ON" if (is_on and not is_off) else "OFF"
    
    # ফায়ারবেসে সরাসরি ডাটা পাঠানো
    if firebase_admin._apps:
        try:
            db.reference(f'/devices/{target_device}').set(status)
        except Exception as ex:
            print("Firebase Write Error:", ex)

    device_num = target_device.replace("relay", "")
    return f"ঠিক আছে, রিলে {device_num} {status} করা হলো।"

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg == "ping":
        return jsonify({"reply": "active"})

    # প্রথমে চেক করবে এটি কোনো রিলে বা ডিভাইস কন্ট্রোল কমান্ড কি না
    fast_device_reply = quick_device_control(msg)
    if fast_device_reply:
        return jsonify({"reply": fast_device_reply})

    if not OPENROUTER_KEY: 
        return jsonify({"reply": "এপিআই কি কনফিগার করা নেই!"})

    system_prompt = "আপনি 'চিঠি' নামক একটি এআই রোবট। শুধু প্রমিত বাংলায় ১ বাক্যে উত্তর দিন। কোনোভাবেই কোনো ইংরেজি শব্দ, থিংকিং প্রসেস বা ব্যাখ্যা দেওয়া যাবে না।"
    
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
        "max_tokens": 60
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply_text = result["choices"][0]["message"]["content"]
            
            # ইংরেজি থিংকিং ট্যাগ বা অপ্রয়োজনীয় টেক্সট কেটে ফেলা
            if "</think>" in reply_text:
                reply_text = reply_text.split("</think>")[-1]
            if "<think>" in reply_text:
                reply_text = reply_text.split("<think>")[0]
            
            clean_reply = reply_text.replace("*", "").replace("#", "").strip()
            
            # যদি এআই ভুল করে সম্পূর্ণ ইংরেজি উত্তর দেয়, তবে ডিফল্ট বাংলা মেসেজ দেওয়া
            if any(ord(c) < 128 for c in clean_reply[:5]) and not any(('\u0980' <= c <= '\u09ff') for c in clean_reply):
                clean_reply = "বুঝেছি, কিন্তু এই মুহূর্তে এটি কার্যকর করা যাচ্ছে না।"

            return jsonify({"reply": clean_reply})
        else:
            return jsonify({"reply": "বুঝতে পারিনি, আবার বলুন।"})
            
    except Exception:
        return jsonify({"reply": "সার্ভার ব্যস্ত আছে, আবার চেষ্টা করুন।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
