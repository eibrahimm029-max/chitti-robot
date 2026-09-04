import os
import re
import json
import time
import hashlib
import datetime
from threading import Thread
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

# ==================== Firebase Setup ====================
DATABASE_URL = os.environ.get('FIREBASE_DB_URL', "https://chitti-bfa21-default-rtdb.firebaseio.com/")
cred_json_str = os.environ.get('FIREBASE_CREDENTIALS')

try:
    if not firebase_admin._apps:
        if cred_json_str:
            cred_dict = json.loads(cred_json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
            print("Firebase initialized with environment credentials.")
        else:
            firebase_admin.initialize_app(options={'databaseURL': DATABASE_URL})
            print("Firebase initialized with default URL.")
except Exception as e:
    print(f"Firebase Init Warning: {e}")

# সিস্টেমে সিকিউরিটি ও ব্যাকগ্রাউন্ড সেটিংস
SYSTEM_STATE = {
    "is_locked_down": False,
    "auto_delete_enabled": True,
    "cleanup_interval_hours": 6
}

PRIMARY_OWNER_TOKEN = "VERIFIED_PRIMARY_OWNER_BIOMETRIC_TOKEN"

LOCAL_KNOWLEDGE = {
    "কে তৈরি করেছে": "আমাকে ইএসপি ৩২ এবং পাইথন ব্যাকএন্ডের মাধ্যমে তৈরি করা হয়েছে।",
    "কবিতা শোনাও": "আকাশে হেলান দিয়ে পাহাড় ঘুমায়, নদীর বুকে নীল সীমানা জাগে।",
    "তুমি কি করতে পারো": "আমি আপনার বাড়ির সুইচ সামলাতে পারি, সিকিউরিটি থ্রেট আটকাতে পারি এবং নতুন তথ্য মনে রাখতে পারি।"
}

RELAY_MAP = {
    "১": "relay1", "1": "relay1", "এক": "relay1", "লাইট": "relay1",
    "২": "relay2", "2": "relay2", "দুই": "relay2", "ফ্যান": "relay2",
    "৩": "relay3", "3": "relay3", "তিন": "relay3",
    "৪": "relay4", "4": "relay4", "চার": "relay4",
    "৫": "relay5", "5": "relay5", "পাঁচ": "relay5",
    "৬": "relay6", "6": "relay6", "ছয়": "relay6",
    "৭": "relay7", "7": "relay7", "সাত": "relay7",
    "৮": "relay8", "8": "relay8", "আট": "relay8"
}

def safe_eval_math(expression):
    try:
        cleaned = re.sub(r'[^0-9\+\-\*\/\.\(\)]', '', expression)
        if cleaned and len(cleaned) >= 3:
            result = eval(cleaned, {"__builtins__": None}, {})
            return f"গাণিতিক হিসাবের ফল: {result}"
    except Exception:
        return None
    return None

# ==================== ব্যাকগ্রাউন্ড স্মার্ট ডিলিট টাইমার ====================
def smart_data_cleanup():
    try:
        print("🧹 [SMART CLEANUP] ৬ ঘণ্টার ব্যাকগ্রাউন্ড ফিল্টারিং শুরু হচ্ছে...")
        ref = db.reference('live_feed')
        all_logs = ref.get() or {}
        current_time = time.time()
        deletion_limit = SYSTEM_STATE["cleanup_interval_hours"] * 3600

        for log_id, data in all_logs.items():
            log_time = data.get('time', 0)
            action = str(data.get('action', ''))
            
            # গুরুত্বপূর্ণ সিকিউরিটি/অ্যাডমিন লগ বাদ দিয়ে সাধারণ কথা মুছে ফেলা
            if (current_time - (log_time / 1000 if log_time > 1e11 else log_time)) > deletion_limit:
                if not any(w in action for w in ['SECURITY', 'MASTER', 'FAMILY_ADDED', 'VIP']):
                    db.reference(f'live_feed/{log_id}').delete()
    except Exception as e:
        print(f"Cleanup Error: {e}")

def background_timer():
    while True:
        time.sleep(SYSTEM_STATE["cleanup_interval_hours"] * 3600)
        if SYSTEM_STATE["auto_delete_enabled"]:
            smart_data_cleanup()

Thread(target=background_timer, daemon=True).start()

# ==================== এন্ডপয়েন্টস ====================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "Online",
        "system": "Chitti AI Pro Running",
        "lockdown": SYSTEM_STATE["is_locked_down"]
    })

# ১ নম্বর মালিকের বায়োমেট্রিক ভেরিফিকেশন
@app.route('/api/verify-owner', methods=['POST'])
def verify_owner():
    data = request.get_json(silent=True) or {}
    bio_signature = data.get('biometric_signature')
    
    if bio_signature == "SUCCESS_BIOMETRIC":
        return jsonify({
            "status": "SUCCESS",
            "owner_token": PRIMARY_OWNER_TOKEN,
            "message": "🔓 ১ নম্বর মালিকের বায়োমেট্রিক ভেরিফাইড! গোপন প্যানেল আনলক করা হয়েছে।"
        }), 200
    return jsonify({"status": "FAILED", "message": "🚨 বায়োমেট্রিক ভেরিফিকেশন ব্যর্থ হয়েছে!"}), 403

# ফ্যামিলি মেম্বার যুক্ত করা (শুধু মালিক)
@app.route('/api/family/add', methods=['POST'])
def add_family():
    data = request.get_json(silent=True) or {}
    if data.get('owner_token') != PRIMARY_OWNER_TOKEN:
        return jsonify({"message": "🚨 অনুমতি নেই! শুধু ১ নম্বর মালিক মেম্বার যোগ করতে পারবেন।"}), 403

    name = data.get('name')
    pin = data.get('pin')
    access = data.get('access')

    new_ref = db.reference('secret_vault/family_members').push()
    new_ref.set({'name': name, 'pin': pin, 'access': access, 'created_at': db.ServerValue.TIMESTAMP})
    
    return jsonify({"message": f"✅ {name}-কে ফ্যামিলি ব্যাকআপে সেভ করা হলো।"}), 200

# ফ্যামিলি মেম্বার তালিকা আনা
@app.route('/api/family/list', methods=['POST'])
def list_family():
    data = request.get_json(silent=True) or {}
    if data.get('owner_token') != PRIMARY_OWNER_TOKEN:
        return jsonify({"message": "🚨 এক্সেস ডিনাইড!"}), 403

    members = db.reference('secret_vault/family_members').get() or {}
    return jsonify({"members": members}), 200

# ফ্যামিলি মেম্বার ডিলিট
@app.route('/api/family/delete/<member_id>', methods=['POST'])
def delete_family(member_id):
    data = request.get_json(silent=True) or {}
    if data.get('owner_token') != PRIMARY_OWNER_TOKEN:
        return jsonify({"message": "🚨 অনুমতি নেই!"}), 403

    db.reference(f'secret_vault/family_members/{member_id}').delete()
    return jsonify({"message": "🗑️ সদস্যকে সফলভাবে মুছে ফেলা হয়েছে।"}), 200

# মেটা প্রুফ জেনারেটর
@app.route('/generate-proof', methods=['POST'])
def generate_proof():
    if SYSTEM_STATE["is_locked_down"]:
        return jsonify({"error": "🚨 সিস্টেম লকডাউনে রয়েছে।", "status": "SERVER_TERMINATED"}), 403

    try:
        if 'file' not in request.files:
            return jsonify({"error": "কোনো ফাইল আপলোড করা হয়নি।"}), 400
        
        file = request.files['file']
        file_bytes = file.read()
        
        if len(file_bytes) == 0:
            return jsonify({"error": "ফাইলটি খালি।"}), 400

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        proof_data = {
            "fileName": file.filename,
            "fileSize": f"{len(file_bytes)} bytes",
            "timestamp": timestamp,
            "metaProofHash": file_hash,
            "status": "VERIFIED_AUTHENTIC"
        }

        try:
            db.reference('meta_proofs').push(proof_data)
        except Exception:
            pass

        return jsonify(proof_data), 200
    except Exception as e:
        return jsonify({"error": "মেটা প্রুফ তৈরি করা যায়নি।", "details": str(e)}), 500

# মূল চ্যাট ব্যাকএন্ড
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message', '')).strip().lower()
    user_role = data.get('user_role', 'MEMBER')

    if SYSTEM_STATE["is_locked_down"]:
        if "আনলক" in user_message or "unlock" in user_message:
            SYSTEM_STATE["is_locked_down"] = False
            return jsonify({"reply": "🔓 লকডাউন রিমুভ করা হয়েছে।", "action": "SYSTEM_RESTORED"}), 200
        return jsonify({"reply": "🚨 সিস্টেম নিরাপত্তার স্বার্থে লকডাউন রয়েছে!", "status": "SERVER_TERMINATED"}), 403

    try:
        ai_reply = ""
        action_taken = "GENERAL_CHAT"
        alert_type = None

        if any(h in user_message for h in ["hack", "exploit", "bypass_admin"]):
            SYSTEM_STATE["is_locked_down"] = True
            return jsonify({"reply": "🚨 সাইবার থ্রেট ধরা পড়েছে! অটো কিলসুইচ ট্রিগার করা হলো!", "status": "SERVER_TERMINATED", "alert_type": "danger"}), 200

        vip_keywords = ["রেকর্ডিং শোনাও", "ক্যামেরার ছবি", "সারাদিনের কথা", "গোপন ফাইল"]
        if any(w in user_message for w in vip_keywords) and user_role != "ADMIN":
            return jsonify({"reply": "অ্যালাইড সিকিউরিটি অ্যাক্সেস: এই ভিআইপি তথ্য দেখার জন্য এডমিন পারমিশন প্রয়োজন।", "action": "VIP_ACCESS_DENIED", "alert_type": "warning"}), 200

        if "চালু" in user_message or "অন" in user_message or "on" in user_message or "বন্ধ" in user_message or "অফ" in user_message or "off" in user_message:
            target_status = "ON" if any(w in user_message for w in ["চালু", "অন", "on"]) else "OFF"
            if "সব" in user_message or "all" in user_message:
                for i in range(1, 9):
                    db.reference(f'devices/relay{i}').set(target_status)
                ai_reply = f"সবগুলো সুইচ একসাথে {target_status} করা হয়েছে।"
                action_taken = "ALL_SWITCHES_UPDATED"
            else:
                matched_relay = None
                for key, relay_id in RELAY_MAP.items():
                    if key in user_message:
                        matched_relay = relay_id
                        break
                if matched_relay:
                    db.reference(f'devices/{matched_relay}').set(target_status)
                    st_txt = "চালু" if target_status == "ON" else "বন্ধ"
                    ai_reply = f"ঠিক আছে, {matched_relay.replace('relay', '')} নাম্বার ডিভাইসটি {st_txt} করা হলো।"
                    action_taken = "DEVICE_CONTROLLED"

        if not ai_reply and any(w in user_message for w in ["মনে রাখো", "শিখে নাও"]):
            try:
                parts = re.split(r'মনে রাখো|শিখে নাও', user_message)
                if len(parts) > 1 and "=" in parts[1]:
                    q, a = parts[1].split("=", 1)
                    db.reference(f'memory/{q.strip()}').set(a.strip())
                    ai_reply = f"ধন্যবাদ! আমি মনে রাখলাম যে: '{q.strip()}' মানে হলো '{a.strip()}'।"
                    action_taken = "KNOWLEDGE_ACQUIRED"
            except Exception:
                ai_reply = "মেমোরিতে সেভ করতে ব্যর্থ।"

        if not ai_reply and safe_eval_math(user_message):
            ai_reply = safe_eval_math(user_message)
            action_taken = "MATH_SOLVED"

        if not ai_reply:
            learned_memory = db.reference('memory').get() or {}
            for k, v in learned_memory.items():
                if k in user_message:
                    ai_reply = str(v)
                    action_taken = "LEARNED_MEMORY_MATCH"
                    break
            if not ai_reply:
                for k in LOCAL_KNOWLEDGE:
                    if k in user_message:
                        ai_reply = LOCAL_KNOWLEDGE[k]
                        action_taken = "LOCAL_KNOWLEDGE_MATCH"
                        break

        if not ai_reply:
            ai_reply = f"আপনার নির্দেশ প্রাপ্ত হয়েছে: '{user_message}'।"

        try:
            db.reference('live_feed').push({'action': action_taken, 'details': user_message, 'time': db.ServerValue.TIMESTAMP})
        except Exception:
            pass

        return jsonify({"reply": ai_reply, "action": action_taken, "alert_type": alert_type}), 200
    except Exception as e:
        return jsonify({"reply": "সার্ভারে রেসপন্স প্রসেস করতে সমস্যা হয়েছে।", "error": str(e)}), 500

@app.route('/get_live_matrix', methods=['GET'])
def get_live_matrix():
    try:
        feed_data = db.reference('live_feed').order_by_child('time').limit_to_last(15).get()
        feed_list = []
        if feed_data:
            for key, val in feed_data.items():
                feed_list.append({"id": key, "action": val.get('action', 'UNKNOWN'), "details": val.get('details', ''), "time": str(val.get('time', ''))})
        return jsonify({"live_feed": feed_list}), 200
    except Exception as e:
        return jsonify({"live_feed": [], "error": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
