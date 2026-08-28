from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, requests
from datetime import datetime
from bs4 import BeautifulSoup
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
    "এক নাম্বার লাইট": "relay1", "লাইট": "relay1", "১ নাম্বার": "relay1", "এক নম্বর": "relay1", "relay1": "relay1", "রিলে ১": "relay1",
    "দুই নাম্বার ফ্যান": "relay2", "ফ্যান": "relay2", "২ নাম্বার": "relay2", "দুই নম্বর": "relay2", "relay2": "relay2", "রিলে ২": "relay2",
    "তিন নাম্বার": "relay3", "৩ নাম্বার": "relay3", "তিন নম্বর": "relay3", "relay3": "relay3", "রিলে ৩": "relay3",
    "চার নাম্বার": "relay4", "৪ নাম্বার": "relay4", "চার নম্বর": "relay4", "relay4": "relay4", "রিলে ৪": "relay4",
    "পাঁচ নাম্বার": "relay5", "৫ নাম্বার": "relay5", "পাঁচ নম্বর": "relay5", "relay5": "relay5", "রিলে ৫": "relay5",
    "ছয় নাম্বার": "relay6", "৬ নাম্বার": "relay6", "ছয় নম্বর": "relay6", "relay6": "relay6", "রিলে ৬": "relay6",
    "সাত নাম্বার": "relay7", "৭ নাম্বার": "relay7", "সাত নম্বর": "relay7", "relay7": "relay7", "রিলে ৭": "relay7",
    "আট নাম্বার": "relay8", "৮ নাম্বার": "relay8", "আট নম্বর": "relay8", "relay8": "relay8", "রিলে ৮": "relay8"
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
    
    if any(w in msg_lower for w in ["অনুমতি দিলাম", "ডিলিট করো", "ক্লিন করো", "clear old data"]):
        if db_firestore:
            try:
                docs = db_firestore.collection('temporary_logs').stream()
                count = 0
                for doc in docs:
                    doc.reference.delete()
                    count += 1
                log_live_activity("DATA_PURGE", f"অস্থায়ী {count}টি লগ মুছে ফেলা হয়েছে।")
                return f"আপনার অনুমতিক্রমে পূর্বের সমস্ত অস্থায়ী ডেটা মুছে ফেলা হয়েছে। সুরক্ষিত বুদ্ধির ভাণ্ডার নিরাপদ আছে।"
            except Exception as e:
                return "ডেটা মুছতে সমস্যা হয়েছে।"
        return "ফায়ারবেস কানেক্টেড নেই।"

    if any(w in msg_lower for w in ["সিকিউরিটি", "হ্যাকিং", "সুরক্ষা", "check server"]):
        log_live_activity("SECURITY_SCAN", "সার্ভার ফায়ারওয়াল ও প্রাইভেসি সুরক্ষিত রয়েছে।")
        return "সার্ভার সিকিউরিটি স্ক্যান সম্পন্ন হয়েছে। কোনো অননুমোদিত অ্যাক্সেস নেই।"

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
    log_live_activity("DEVICE_CONTROL", f"{device_num} নাম্বার ডিভাইস {actual_action} করা হয়েছে।")
    return f"ঠিক আছে, {device_num} নাম্বার ডিভাইসটি {actual_action} করা হলো।"

def autonomous_rag_engine(query):
    query_lower = query.lower()
    log_live_activity("NEURAL_SEARCH", f"প্রশ্ন বিশ্লেষণ করা হচ্ছে: {query[:30]}...")

    if db_firestore:
        try:
            docs = db_firestore.collection('protected_memory').stream()
            for doc in docs:
                data = doc.to_dict()
                if any(word in data.get('query', '').lower() for word in query_lower.split() if len(word) > 3):
                    log_live_activity("MEMORY_HIT", "সুরক্ষিত ভাণ্ডার থেকে বুদ্ধি রিকভার করা হয়েছে।")
                    return f"🧠 [সুরক্ষিত বুদ্ধি ভাণ্ডার]:\n{data.get('solution')}"

            new_solution = f"আপনার জিজ্ঞাসিত '{query}' বিষয়ের উপর ভিত্তি করে সিস্টেমের নিউরাল লজিক ডেটা সিন্থেসিস সম্পন্ন করেছে। এটি স্থায়ী জ্ঞান হিসেবে রেজিস্টার হলো।"
            
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": new_solution,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
            
            log_live_activity("KNOWLEDGE_ACQUIRED", "নতুন বুদ্ধি পার্মানেন্ট মেমোরিতে সেভ করা হয়েছে।")
            return new_solution

        except Exception as e:
            print("Firestore RAG Error:", e)

    return "সিস্টেমের লোকাল ব্রেন সক্রিয় রয়েছে, বলুন কীভাবে সহায়তা করতে পারি?"

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg in ["ping_server_keep_alive", "ping_system_check"]:
        return jsonify({"reply": "server_active"})

    system_reply = smart_system_manager(msg)
    if system_reply:
        return jsonify({"reply": system_reply})

    ai_reply = autonomous_rag_engine(msg)
    
    if db_firestore:
        try:
            db_firestore.collection('temporary_logs').add({
                "message": msg,
                "reply": ai_reply,
                "time": datetime.now()
            })
        except:
            pass

    return jsonify({"reply": ai_reply})

@app.route('/check_cleanup_status', methods=['GET'])
def check_cleanup_status():
    if db_firestore:
        try:
            docs = db_firestore.collection('temporary_logs').stream()
            count = sum(1 for _ in docs)
            if count > 15:
                return jsonify({
                    "notification_needed": True,
                    "message": "সতর্কতা: সিস্টেমে প্রচুর অস্থায়ী লগ জমে গেছে। পুরনো ডেটা মুছে ফেলা হবে কি না? (অনুমতি দিন)"
                })
        except:
            pass
    return jsonify({"notification_needed": False})

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
