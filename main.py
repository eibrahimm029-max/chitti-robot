from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, random, difflib
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
    return f"নির্দেশ সফল: {device_num} নাম্বার ডিভাইসটি এখন ঠিকঠাকভাবে {actual_action} করা হয়েছে।"

# নিজস্ব বুদ্ধিমান নলেজ ও প্যাটার্ন ম্যাচিং ইঞ্জিন (কোনো এপিআই লাগবে না)
def advanced_autonomous_processing(query):
    query_lower = query.lower().strip()
    log_live_activity("LOCAL_NLP_PROCESS", f"ইনপুট বিশ্লেষণ করা হচ্ছে: {query[:30]}...")

    # আপনার বিশাল নলেজ বেজ যেখানে নানা ক্যাটাগরির বুদ্ধি ও পরামর্শ রাখা থাকবে
    knowledge_database = {
        "কেমন আছো": "আলহামদুলিল্লাহ, আমি আপনার নিজস্ব সিক্রেট সার্ভার সিস্টেম। সম্পূর্ণ সচল আছি এবং আপনার কমান্ডের অপেক্ষায় আছি।",
        "তোমার নাম কি": "আমি আপনার অ্যাপস দ্বারা চালিত একটি স্বাধীন ও স্বয়ংক্রিয় স্মার্ট অ্যাসিস্ট্যান্ট।",
        "কী করতে পারো": "আমি আপনার ঘরের ডিভাইস (লাইট, ফ্যান ইত্যাদি) রিমোট কন্ট্রোল করতে পারি, লাইভ মনিটরিং দেখাতে পারি এবং আপনার যেকোনো প্রশ্নের বুদ্ধিদীপ্ত সমাধান দিতে পারি।",
        "সালাম": "ওয়ালাইকুমুসসালাম ওয়া রাহমাতুল্লাহ। আশা করি আপনি ভালো আছেন, বলুন কীভাবে সাহায্য করতে পারি?",
        "প্রোগ্রামিং": "প্রোগ্রামিং বা কোডিংয়ের ক্ষেত্রে সবসময় লজিক পরিষ্কার রাখা এবং ছোট ছোট মডিউলে কাজ ভাগ করে নেওয়া বুদ্ধিমানের কাজ।",
        "সাফল্য": "সঠিক পরিকল্পনা, নিয়মিত ফোকাস এবং হাল না ছাড়ার মানসিকতাই সফলতার মূল চাবিকাঠি।"
    }

    # প্যাটার্ন ম্যাচিং বা মিল খোঁজার জন্য নিজস্ব অ্যালগরিদম
    best_match = None
    highest_ratio = 0.0
    
    for key, val in knowledge_database.items():
        ratio = difflib.SequenceMatcher(None, query_lower, key.lower()).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_match = val

    # যদি কাছাকাছি কোনো ম্যাচ পাওয়া যায় অথবা নির্দিষ্ট শব্দ থাকে
    if highest_ratio > 0.35 and best_match:
        response_text = best_match
    else:
        # যদি একদম নতুন প্রশ্ন হয়, তবে নিজস্ব লজিক থেকে ডাইনামিক পরামর্শ তৈরি করা
        dynamic_advice_pool = [
            f"আপনার জিজ্ঞাসित '{query}' বিষয়টি অত্যন্ত চমৎকার। সিস্টেমের অ্যানালাইসিস বলছে—ধৈর্য এবং সঠিক কর্মপরিকল্পনা নিয়ে এগিয়ে গেলে এতে দারুণ সাফল্য আসবে।",
            f"('{query}') এর সমাধান হিসেবে আপনার সার্কিট ফ্লো এবং ডেটা লজিকগুলো আরেকবার যাচাই করে নেওয়া উচিত।",
            f"এই পরিস্থিতির ওপর ভিত্তি করে বলব, সুনির্দিষ্ট লক্ষ্য ঠিক করে কাজ চালিয়ে যান। সিস্টেম সবসময় আপনার সাথে আছে।"
        ]
        response_text = random.choice(dynamic_advice_pool)

    # ফায়ারস্টোরের সুরক্ষিত মেমোরিতে এটি পার্মানেন্ট সেভ করা
    if db_firestore:
        try:
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": response_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
            log_live_activity("MEMORY_SAVED", "ইনপুট এবং উত্তর সুরক্ষিত মেমোরিতে সফলভাবে রেকর্ড হয়েছে।")
        except Exception as e:
            print("Firestore Error:", e)

    return response_text

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if msg in ["ping_server_keep_alive", "ping_system_check"]:
        return jsonify({"reply": "server_active"})

    # ১. ডিভাইস কন্ট্রোল কমান্ড চেক করা
    system_reply = smart_system_manager(msg)
    if system_reply:
        return jsonify({"reply": system_reply})

    # ২. নিজস্ব ইন্ডিপেন্ডেন্ট প্রসেসিং ইঞ্জিন থেকে উত্তর নেওয়া
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
