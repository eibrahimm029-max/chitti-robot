from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, random, difflib
from datetime import datetime, timedelta
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

# রিলের তালিকা ও ডিভাইস ম্যাপিং
DEVICE_MAP = {
    "এক নাম্বার রিল": "relay1", "১ নাম্বার": "relay1", "relay1": "relay1", "রিলে ১": "relay1",
    "দুই নাম্বার রিল": "relay2", "২ নাম্বার": "relay2", "relay2": "relay2", "রিলে ২": "relay2",
    "তিন নাম্বার রিল": "relay3", "৩ নাম্বার": "relay3", "relay3": "relay3", "রিলে ৩": "relay3",
    "চার নাম্বার রিল": "relay4", "৪ নাম্বার": "relay4", "relay4": "relay4", "রিলে ৪": "relay4",
    "পাঁচ নাম্বার রিল": "relay5", "৫ নাম্বার": "relay5", "relay5": "relay5", "রিলে ৫": "relay5",
    "ছয় নাম্বার রিল": "relay6", "৬ নাম্বার": "relay6", "relay6": "relay6", "রিলে ৬": "relay6",
    "সাত নাম্বার রিল": "relay7", "৭ নাম্বার": "relay7", "relay7": "relay7", "রিলে ৭": "relay7",
    "আট নাম্বার রিল": "relay8", "৮ নাম্বার": "relay8", "relay8": "relay8", "রিলে ৮": "relay8"
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

def intelligent_data_manager():
    if not db_firestore:
        return
    try:
        docs = db_firestore.collection('temporary_logs').stream()
        now = datetime.now()
        purge_candidates = 0
        for doc in docs:
            data = doc.to_dict()
            time_str = data.get('timestamp') or data.get('time')
            if time_str:
                try:
                    log_time = datetime.strptime(time_str, "%Y-%m-%d %I:%M:%S %p")
                    if now - log_time > timedelta(hours=6):
                        purge_candidates += 1
                except:
                    pass

        if purge_candidates > 0:
            db_firestore.collection('system_notifications').add({
                "time": now.strftime("%Y-%m-%d %I:%M:%S %p"),
                "title": "ডেটা ক্লিনআপ অনুমতি",
                "message": f"{purge_candidates}টি পুরনো লগ জমে আছে। মুছে ফেলতে অনুমতি দিন।",
                "status": "PENDING_APPROVAL"
            })
    except Exception as e:
        print("Manager Error:", e)

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
    log_live_activity("DEVICE_CONTROL", f"{device_num} নাম্বার রিল {actual_action} করা হয়েছে।")
    return f"নির্দেশ সফল: {device_num} নাম্বার রিলটি এখন {actual_action} করা হয়েছে।"

def advanced_autonomous_processing(query):
    query_lower = query.lower().strip()
    log_live_activity("LOCAL_NLP_PROCESS", f"ইনপুট প্রসেস হচ্ছে: {query[:30]}...")
    intelligent_data_manager()

    knowledge_database = {
        "কেমন আছো": "আলহামদুলিল্লাহ, আপনার সিস্টেম সম্পূর্ণ সচল ও সুরক্ষিত রয়েছে।",
        "তোমার নাম কি": "আমি আপনার সিক্রেট রোবট সহকারী ও স্মার্ট কন্ট্রোল সিস্টেম।",
        "মেনু": "মেনু অপশন থেকে আপনি রিলের সমস্ত সুইচগুলো একসাথে দেখতে ও নিয়ন্ত্রণ করতে পারবেন।"
    }

    best_match = None
    highest_ratio = 0.0
    for key, val in knowledge_database.items():
        ratio = difflib.SequenceMatcher(None, query_lower, key.lower()).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = val

    if highest_ratio > 0.35 and best_match:
        response_text = best_match
    else:
        dynamic_advice = [
            f"আপনার ইনপুট '{query}' সিস্টেমে রেকর্ড করা হয়েছে। লক্ষ্য ঠিক রেখে এগিয়ে চলুন!",
            f"('{query}') এর জন্য সিস্টেমের কানেকশন ও লজিক ফ্লো যাচাই করা হচ্ছে।"
        ]
        response_text = random.choice(dynamic_advice)

    if db_firestore:
        try:
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": response_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
        except Exception as e:
            print(e)

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

    ai_reply = advanced_autonomous_processing(msg)
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
