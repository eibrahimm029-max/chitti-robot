from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db, firestore

app = Flask(__name__)
CORS(app)

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

DEVICE_MAP = {
    "এক নাম্বার লাইট": "relay1", "লাইট": "relay1", "১ নাম্বার": "relay1", "relay1": "relay1",
    "দুই নাম্বার ফ্যান": "relay2", "ফ্যান": "relay2", "২ নাম্বার": "relay2", "relay2": "relay2",
    "তিন নাম্বার": "relay3", "৩ নাম্বার": "relay3", "relay3": "relay3",
    "চার নাম্বার": "relay4", "৪ নাম্বার": "relay4", "relay4": "relay4",
    "পাঁচ নাম্বার": "relay5", "৫ নাম্বার": "relay5", "relay5": "relay5",
    "ছয় নাম্বার": "relay6", "৬ নাম্বার": "relay6", "relay6": "relay6",
    "সাত নাম্বার": "relay7", "৭ নাম্বার": "relay7", "relay7": "relay7",
    "আট নাম্বার": "relay8", "৮ নাম্বার": "relay8", "relay8": "relay8"
}

def log_live_activity(action_type, details):
    if db_firestore:
        try:
            db_firestore.collection('live_matrix_monitor').add({
                "time": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
                "action": action_type,
                "details": details,
                "status": "ACTIVE_STREAM"
            })
        except Exception as e:
            print("Live Log Error:", e)

def smart_system_manager(msg):
    msg_lower = msg.lower()
    
    is_on = any(w in msg_lower for w in ["চালু", "অন", "on", "জ্বালাও", "দাও", "ছাড়ো"])
    is_off = any(w in msg_lower for w in ["বন্ধ", "অফ", "off", "নিভাও", "তোল"])
    
    if not (is_on or is_off): 
        return None 

    target_device = None
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
    log_live_activity("DEVICE_CONTROL", f"{device_num} নাম্বার ডিভাইস {actual_action} করা হয়েছে।")
    return f"নির্দেশ সফল: {device_num} নাম্বার ডিভাইসটি এখন {actual_action} করা হয়েছে।"

def autonomous_local_brain(query):
    query_lower = query.lower()
    log_live_activity("LOCAL_THINKING", f"ইনপুট প্রসেসিং: {query[:30]}...")

    # নির্দিষ্ট প্রশ্নোত্তর ডাটাবেস
    knowledge_base = {
        "কেমন আছো": "আলহামদুলিল্লাহ, আমি সম্পূর্ণ সচল এবং আপনার সিস্টেম নিয়ন্ত্রণে প্রস্তুত আছি। আপনি কেমন আছেন?",
        "তোমার নাম কি": "আমি আপনার নিজস্ব তৈরি করা স্মার্ট অটোনমাস সিস্টেম বা রোবট সহকারী।",
        "সাহায্য": "বলুন, আপনার কোন বিষয়ে সাহায্য প্রয়োজন? আমি ডিভাইস কন্ট্রোল এবং বিভিন্ন পরামর্শ দিয়ে সহায়তা করতে পারি।",
        "سلام": "ওয়ালাইকুমুসসালাম ওয়া রাহমাতুল্লাহ। বলুন কীভাবে সাহায্য করতে পারি?",
        "hi": "Hello! How can I assist you with your smart system today?"
    }

    response_text = None
    for key, val in knowledge_base.items():
        if key in query_lower:
            response_text = val
            break

    if not response_text:
        fallback_replies = [
            f"আপনার জিজ্ঞাসিত '{query}' বিষয়টি নোট করা হয়েছে। লক্ষ্য ঠিক রেখে ধাপে ধাপে কাজ করলে এতে নিশ্চিত সফলতা পাবেন।",
            f"('{query}') সম্পর্কিত পরিস্থিতিতে সিস্টেমের কানেকশন ও লজিক ফ্লো ঠিক রাখাই সবচেয়ে ভালো সিদ্ধান্ত।",
            f"আপনার এই সুন্দর ভাবনাটি সিস্টেমের পার্মানেন্ট মেমোরিতে যুক্ত করা হলো।"
        ]
        response_text = random.choice(fallback_replies)

    if db_firestore:
        try:
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": response_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
            log_live_activity("MEMORY_SAVED", "উত্তরটি সুরক্ষিত মেমোরিতে সেভ করা হয়েছে।")
        except Exception as e:
            print("Firestore Error:", e)

    return response_text

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg in ["ping_server_keep_alive", "ping_system_check"]:
        return jsonify({"reply": "server_active"})

    system_reply = smart_system_manager(msg)
    if system_reply:
        return jsonify({"reply": system_reply})

    ai_reply = autonomous_local_brain(msg)
    return jsonify({"reply": ai_reply})

@app.route('/get_live_matrix', methods=['GET'])
def get_live_matrix():
    activities = []
    if db_firestore:
        try:
            docs = db_firestore.collection('live_matrix_monitor').order_by('time', direction=firestore.Query.DESCENDING).limit(10).stream()
            for doc in docs:
                activities.append(doc.to_dict())
        except Exception as e:
            print("Matrix Fetch Error:", e)
    return jsonify({"live_feed": activities})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
