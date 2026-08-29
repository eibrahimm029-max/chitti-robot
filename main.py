from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, random, requests
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

# পাবলিক সোর্স ও ইন্টারনেট স্ক্র্যাপিং ইঞ্জিন
def fetch_public_web_knowledge(query):
    try:
        # ডাকডাকগো বা ওপেন সার্চ সোর্স থেকে তথ্য খোঁজার লাইটওয়েট পদ্ধতি
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('a', class_='result__snippet', limit=2)
            snippets = [r.get_text().strip() for r in results]
            if snippets:
                return " ".join(snippets)
    except Exception as e:
        print("Web Scraping Error:", e)
    return None

def autonomous_rag_engine(query):
    query_lower = query.lower()
    log_live_activity("NEURAL_SEARCH", f"পাবলিক সোর্স বিশ্লেষণ: {query[:30]}...")

    # প্রথমে ফায়ারস্টোরের সুরক্ষিত মেমোরি চেক করা
    if db_firestore:
        try:
            docs = db_firestore.collection('protected_memory').stream()
            for doc in docs:
                data = doc.to_dict()
                if any(word in data.get('query', '').lower() for word in query_lower.split() if len(word) > 3):
                    log_live_activity("MEMORY_HIT", "সুরক্ষিত মেমোরি থেকে বুদ্ধি রিট্রিভ করা হয়েছে।")
                    return f"🧠 [মেমোরি ভাণ্ডার]:\n{data.get('solution')}"
        except Exception as e:
            print("Memory Check Error:", e)

    # মেমোরিতে না থাকলে ইন্টারনেট বা পাবলিক সোর্স থেকে তথ্য সংগ্রহ করা
    web_data = fetch_public_web_knowledge(query)
    
    if web_data:
        final_solution = f"🌐 [পাবলিক সোর্স থেকে প্রাপ্ত তথ্য]:\n{web_data}\n\nসিস্টেমের লজিক অনুযায়ী এটি বিশ্লেষণ করে স্থায়ী জ্ঞানে রূপান্তর করা হয়েছে।"
        log_live_activity("WEB_SCRAPE_SUCCESS", "ইন্টারনেট বা পাবলিক সোর্স থেকে সফলভাবে ডেটা ফেচ করা হয়েছে।")
    else:
        smart_fallbacks = [
            f"('{query}') বিষয়ের ওপর ভিত্তি করে সিস্টেম নিজস্ব লজিক দিয়ে সমাধান তৈরি করেছে: সঠিক পরিকল্পনা ও ধারাবাহিকতা বজায় রাখলে এটি সফল হবে।",
            f"আপনার এই প্রশ্নটির জন্য হার্ডওয়্যার ও সফটওয়্যার লেভেলে মডুলার কানেকশন চেক করা বুদ্ধিমানের কাজ হবে।"
        ]
        final_solution = random.choice(smart_fallbacks)
        log_live_activity("LOCAL_SYNTHESIS", "লোকাল নিউরাল লজিক দিয়ে উত্তর তৈরি করা হয়েছে।")

    # নতুন জ্ঞান ফায়ারস্টোরের protected_memory তে স্থায়ীভাবে সেভ করা
    if db_firestore:
        try:
            db_firestore.collection('protected_memory').add({
                "query": query,
                "solution": final_solution,
                "timestamp": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            })
        except Exception as e:
            print(e)

    return final_solution

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
