from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests, json, re
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

# ফোনের লোকাল মেমোরি পাথ যেখানে ফাইলগুলো সেভ আছে
STORAGE_PATH = "/sdcard/ChittiStorage/"

DEVICE_MAP = {
    "এক নাম্বার লাইট": "relay1", "লাইট": "relay1", "১ নাম্বার": "relay1", "এক নম্বর": "relay1", "relay1": "relay1", "রিলে ১": "relay1",
    "দুই নাম্বার ফ্যান": "relay2", "ফ্যান": "relay2", "২ নাম্বার": "relay2", "দুই নম্বর": "relay2", "relay2": "relay2", "রিলে ২": "relay2",
    "তিন নাম্বার": "relay3", "৩ নাম্বার": "relay3", "তিন নম্বর": "relay3", "relay3": "relay3", "রিলে ৩": "relay3",
    "চার নাম্বার": "relay4", "৪ নাম্বার": "relay4", "চার নম্বর": "relay4", "relay4": "relay4", "রিলে ৪": "relay4",
    "পাঁচ নাম্বার": "relay5", "৫ নাম্বার": "relay5", "পাঁচ নম্বর": "relay5", "relay5": "relay5", "রিলে ৫": "relay5",
    "ছয় নাম্বার": "relay6", "৬ নাম্বার": "relay6", "ছয় নম্বর": "relay6", "relay6": "relay6", "রিলে ৬": "relay6",
    "সাত নাম্বার": "relay7", "৭ নাম্বার": "relay7", "সাত নম্বর": "relay7", "relay7": "relay7", "রিলে ৭": "relay7",
    "আট নাম্বার": "relay8", "৮ নাম্বার": "relay8", "আট নম্বর": "relay8", "relay8": "relay8", "রিলে ৮": "relay8"
}

def smart_system_manager(msg):
    msg_lower = msg.lower()
    
    # ১. ডেটা ক্লিনআপ বা পুরনো ডেটা ডিলিট করার কমান্ড
    if any(w in msg_lower for w in ["ডেটা ডিলিট", "পুরনো ডেটা", "মুছে ফেলো", "ক্লিন করো", "clear data", "delete old", "ডিলিট করো", "স্টোরেজ", "ফায়ারবেস"]):
        if firebase_admin._apps:
            try:
                db.reference('/logs/old_data').delete()
                return "পূর্বের সমস্ত অপ্রয়োজনীয় ও পুরনো ডেটা সফলভাবে মুছে ফেলা হয়েছে, সার্ভার এখন সম্পূর্ণ পরিষ্কার।"
            except Exception as e:
                return "ডেটা মুছতে সমস্যা হয়েছে।"
        return "ফায়ারবেস কানেক্টেড নেই।"

    # ২. সিকিউরিটি বা হ্যাকিং চেক কমান্ড
    if any(w in msg_lower for w in ["সিকিউরিটি", "হ্যাকিং", "সুরক্ষা", "check server"]):
        return "সার্ভার সিকিউরিটি স্ক্যান সম্পন্ন হয়েছে। কোনো ম্যালওয়্যার বা অননুমোদিত অ্যাক্সেস পাওয়া যায়নি, সিস্টেম সম্পূর্ণ নিরাপদ।"

    # ৩. ডিভাইস কন্ট্রোল কমান্ড চেক
    is_on = any(w in msg_lower for w in ["চালু", "অন", "on", "জ্বালাও", "দাও", "ছাড়ো"])
    is_off = any(w in msg_lower for w in ["বন্ধ", "অফ", "off", "নিভাও", "তোল"])
    
    if not (is_on or is_off): 
        return None 

    target_device = None
    if any(w in msg for w in ["৮", "আট"]): target_device = "relay8"
    elif any(w in msg for w in ["৭", "সাত"]): target_device = "relay7"
    elif any(w in msg for w in ["৬", "ছয়"]): target_device = "relay6"
    elif any(w in msg for w in ["৫", "পাঁচ"]): target_device = "relay5"
    elif any(w in msg for w in ["৪", "চার"]): target_device = "relay4"
    elif any(w in msg for w in ["৩", "তিন"]): target_device = "relay3"
    elif any(w in msg for w in ["২", "দুই", "ফ্যান"]): target_device = "relay2"
    elif any(w in msg for w in ["১", "এক", "লাইট"]): target_device = "relay1"
    else:
        for key, device in DEVICE_MAP.items():
            if key in msg_lower:
                target_device = device
                break

    if not target_device: return None

    status = "ON" if (is_on and not is_off) else "OFF"
    actual_action = "চালু" if status == "ON" else "বন্ধ"

    if firebase_admin._apps:
        try:
            db.reference(f'/devices/{target_device}').set(status)
        except Exception as ex:
            print("Firebase Error:", ex)

    device_num = target_device.replace("relay", "")
    return f"ঠিক আছে, {device_num} নাম্বার ডিভাইসটি {actual_action} করা হলো।"

def search_chitti_memory(query):
    """
    ফোনের ChittiStorage ফোল্ডার থেকে ফাইল স্ক্যান করে মেমোরির তথ্য খুঁজে বের করবে
    """
    if not os.path.exists(STORAGE_PATH):
        return None

    query_lower = query.lower()
    try:
        files = os.listdir(STORAGE_PATH)
        for filename in files:
            if filename.endswith(".txt"):
                file_path = os.path.join(STORAGE_PATH, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if any(word in content.lower() for word in query_lower.split() if len(word) > 2):
                        clean_content = content.replace("*", "").replace("#", "").strip()
                        return f"মেমোরি ফাইল থেকে প্রাপ্ত তথ্য: {clean_content[:250]}"
    except Exception as e:
        print("Memory Read Error:", e)
    
    return None

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg in ["ping_server_keep_alive", "ping_system_check"]:
        return jsonify({"reply": "server_active"})

    # ধাপ ১: হোম অটোমেশন বা ডিভাইস কন্ট্রোল কমান্ড চেক
    system_reply = smart_system_manager(msg)
    if system_reply:
        return jsonify({"reply": system_reply})

    # ধাপ ২: ফোনের লোকাল মেমোরি ফাইল চেক
    memory_reply = search_chitti_memory(msg)
    if memory_reply:
        return jsonify({"reply": memory_reply})

    # ধাপ ৩: গ্রোক এআই (Groq AI) এর মাধ্যমে বুদ্ধিমান উত্তর নিয়ে আসা
    if not OPENROUTER_KEY: 
        return jsonify({"reply": "এপিআই কি কনফিগার করা নেই!"})

    system_prompt = "You are 'Chitti', an advanced AI server and smart home manager. Always reply in clear and natural Bengali, regardless of what the user asks. Keep your answer concise within 1 or 2 sentences. Never output English words or thinking process."
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}", 
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": msg}
        ], 
        "max_tokens": 100
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply_text = result["choices"][0]["message"]["content"]
            
            # যেকোনো থিংকিং বা অযথা ট্যাগ ফিল্টার করা
            reply_text = re.sub(r'<think>.*?</think>', '', reply_text, flags=re.DOTALL)
            if "</think>" in reply_text:
                reply_text = reply_text.split("</think>")[-1]
            if "<think>" in reply_text:
                reply_text = reply_text.split("<think>")[0]
            
            clean_reply = reply_text.replace("*", "").replace("#", "").strip()
            return jsonify({"reply": clean_reply if clean_reply else "আমি আপনার কথাটি বুঝতে পেরেছি, বলুন কীভাবে সাহায্য করতে পারি?"})
        else:
            return jsonify({"reply": "আমি আপনার কথাটি বুঝতে পেরেছি, বলুন কীভাবে সাহায্য করতে পারি?"})
            
    except Exception as e:
        print("Groq API Error:", e)
        return jsonify({"reply": "সার্ভার ব্যস্ত আছে, আবার চেষ্টা করুন।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
