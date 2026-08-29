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
    "এক নাম্বার লাইট": "relay1", "লাইট": "relay1", "১ নাম্বার": "relay1", "relay1": "relay1", "রিলে ১": "relay1",
    "দুই নাম্বার ফ্যান": "relay2", "ফ্যান": "relay2", "২ নাম্বার": "relay2", "relay2": "relay2", "রিলে ২": "relay2",
    "তিন নাম্বার": "relay3", "৩ নাম্বার": "relay3", "relay3": "relay3", "রিলে ৩": "relay3",
    "চার নাম্বার": "relay4", "৪ নাম্বার": "relay4", "relay4": "relay4", "রিলে ৪": "relay4",
    "পাঁচ নাম্বার": "relay5", "৫ নাম্বার": "relay5", "relay5": "relay5", "রিলে ৫": "relay5",
    "ছয় নাম্বার": "relay6", "৬ নাম্বার": "relay6", "relay6": "relay6", "রিলে ৬": "relay6",
    "সাত নাম্বার": "relay7", "৭ নাম্বার": "relay7", "relay7": "relay7", "রিলে ৭": "relay7",
    "আট নাম্বার": "relay8", "৮ নাম্বার": "relay8", "relay8": "relay8", "রিলে ৮": "relay8"
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
    
    if any(w in msg_lower for w in ["ডিলিট করো", "ক্লিন করো", "clear old data"]):
        if db_firestore:
            try:
                docs = db_firestore.collection('temporary_logs').stream()
                count = sum(1 for _ in docs)
                for doc in docs:
                    doc.reference.delete()
                log_live_activity("DATA_PURGE", f"অস্থায়ী {count}টি লগ মুছে ফেলা হয়েছে।")
                return f"আপনার অনুমতিক্রমে পূর্বের সমস্ত অস্থায়ী ডেটা সফলভাবে মুছে ফেলা হয়েছে।"
            except Exception as e:
                return "ডেটা মুছতে সমস্যা হয়েছে।"
        return "ফায়ারবেস কানেক্টেড নেই।"

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

# ডাইনামিক ও বুদ্ধিমান রেসপন্স জেনারেটর ইঞ্জিন
def autonomous_rag_engine(query):
    query_lower = query.lower()
    log_live_activity("NEURAL_SEARCH", f"ইনপুট বিশ্লেষণ: {query[:30]}...")

    # কিছু সৃজনশীল ও ডাইনামিক বুদ্ধিমত্তার টেমপ্লেট
    smart_advice_pool = [
        f"আপনার এই বিষয়টির ওপর ভিত্তি করে সিস্টেম বিশ্লেষণ করেছে যে, সুনির্দিষ্ট লক্ষ্য ও সঠিক পরিকল্পনা নিয়ে এগিয়ে গেলে এটি সফল করা সম্ভব।",
        f"('{query}') সম্পর্কিত সমস্যাটির সমাধানে রিলে এবং সেন্সর মডিউলের কানেকশনগুলো আরেকবার যাচাই করে নেওয়া বুদ্ধিমানের কাজ হবে।",
        f"নিউরাল লজিক বলছে, এই পরিস্থিতিতে একটু বিরতি নিয়ে সার্কিট ফ্লো এবং ডেটা প্যাকেট মনিটর করা উচিত।",
        f"আপনার এই চিন্তাধারাটি সিস্টেমের কার্যক্ষমতা বাড়াতে দারুণ ভূমিকা রাখবে। এটি দীর্ঘস্থায়ী মেমোরিতে যুক্ত করা হলো।"
    ]

    selected_solution = random.choice(smart_advice_pool)

    if db_firestore:
        try:
            # আগে থেকে সেভ থাকা মেমোরি চেক করা
            docs = db_firestore.collection('protected_memory').stream()
            for doc in docs:
                data = doc.to_dict()
                if any(word in data.get('query', '').lower() for word in query_lower.split() if len(word) > 3):
                    log_live_activity("MEMORY_HIT", "সুরক্ষিত ভাণ্ডার থেকে বুদ্ধি রিকভার করা হয়েছে।")
                    return f"🧠 [স্মৃতি ভাণ্ডার থেকে]:\n{data.get('solution')}"

            # নতুন বুদ্ধি পার্মানেন্ট মেমোরিতে সেভ করা
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": selected_solution,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
            
            log_live_activity("KNOWLEDGE_ACQUIRED", "নতুন বুদ্ধি পার্মানেন্ট মেমোরিতে রেজিস্টার হয়েছে।")
            return selected_solution

        except Exception as e:
            print("Firestore RAG Error:", e)

    return selected_solution

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
