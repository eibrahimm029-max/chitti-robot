import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

DATABASE_URL = "https://chitti-bfa21-default-rtdb.firebaseio.com/"

# ফায়ারবেস ইনিশিয়ালাইজেশন
try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={
            'databaseURL': DATABASE_URL
        })
except Exception as e:
    print(f"Firebase Init Warning: {e}")

SYSTEM_STATE = {
    "is_locked_down": False
}

# ডিফল্ট কাস্টম নলেজ
LOCAL_KNOWLEDGE = {
    "কে তৈরি করেছে": "আমাকে ইএসপি ৩২ এবং পাইথন ব্যাকএন্ডের মাধ্যমে তৈরি করা হয়েছে।",
    "কবিতা শোনাও": "আকাশে হেলান দিয়ে পাহাড় ঘুমায়, নদীর বুকে নীল সীমানা জাগে।",
    "তুমি কি করতে পারো": "আমি আপনার বাড়ির সুইচ সামলাতে পারি, সিকিউরিটি থ্রেট আটকাতে পারি এবং নতুন তথ্য মনে রাখতে পারি।"
}

# রিলে নাম ও ফায়ারবেস কি (Key) ম্যাপিং
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

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "Online",
        "system": "Chitti AI Pro Running",
        "lockdown": SYSTEM_STATE["is_locked_down"]
    })

@app.route('/chat', methods=['POST'])
def chat():
    # সিকিউরিটি চেক (লকডাউন থাকলে কমান্ড প্রসেস করবে না)
    data = request.get_json(silent=True) or {}
    user_message = str(data.get('message', '')).strip().lower()
    user_role = data.get('user_role', 'MEMBER')

    # লকডাউন আনলক প্রোটোকল
    if SYSTEM_STATE["is_locked_down"]:
        if "আনলক" in user_message or "unlock" in user_message or "restore" in user_message:
            SYSTEM_STATE["is_locked_down"] = False
            return jsonify({
                "reply": "🔓 সিকিউরিটি লকডাউন রিমুভ করা হয়েছে। সিস্টেম এখন স্বাভাবিকভাবে কাজ করছে।",
                "action": "SYSTEM_RESTORED"
            }), 200
        return jsonify({
            "reply": "🚨 সিস্টেম নিরাপত্তার স্বার্থে লকডাউন রয়েছে! আনলক করতে অ্যাডমিন কমান্ড দিন।",
            "status": "SERVER_TERMINATED"
        }), 403

    try:
        ai_reply = ""
        action_taken = "GENERAL_CHAT"
        alert_type = None

        # ১. সাইবার সিকিউরিটি থ্রেট ডিটেকশন (লকডাউন ট্রিগার)
        if any(hack_word in user_message for hack_word in ["hack", "exploit", "bypass_admin", "injection"]):
            SYSTEM_STATE["is_locked_down"] = True
            return jsonify({
                "reply": "🚨 হ্যাকিং চেষ্টার উপস্থিতি ধরা পড়েছে! সিস্টেম সাথে সাথে লকডাউন করা হলো!",
                "status": "SERVER_TERMINATED",
                "alert_type": "danger"
            }), 200

        # ২. ভিআইপি প্রোটেকশন
        vip_keywords = ["রেকর্ডিং শোনাও", "ক্যামেরার ছবি", "সারাদিনের কথা", "গোপন ফাইল"]
        if any(word in user_message for word in vip_keywords):
            if user_role != "ADMIN":
                return jsonify({
                    "reply": "অ্যালাইড সিকিউরিটি অ্যাক্সেস: এই ভিআইপি তথ্য দেখার জন্য এডমিন পারমিশন প্রয়োজন।",
                    "action": "VIP_ACCESS_DENIED",
                    "alert_type": "warning"
                }), 200

        # ৩. স্মার্ট রিলে/সুইচ কন্ট্রোল (ভয়েস বা টেক্সট)
        if "চালু" in user_message or "অন" in user_message or "on" in user_message or "বন্ধ" in user_message or "অফ" in user_message or "off" in user_message:
            target_status = "ON" if any(w in user_message for w in ["চালু", "অন", "on"]) else "OFF"
            
            # সব সুইচ একসাথে বন্ধ/চালু
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
                    status_text = "চালু" if target_status == "ON" else "বন্ধ"
                    ai_reply = f"ঠিক আছে, {matched_relay.replace('relay', '')} নাম্বার ডিভাইসটি {status_text} করা হলো।"
                    action_taken = "DEVICE_CONTROLLED"

        # ৪. নতুন নলেজ শেখা (Dynamic Memory Acquisition)
        if not ai_reply and any(w in user_message for w in ["মনে রাখো", "শিখে নাও", "স্মরণে রাখো"]):
            try:
                parts = re.split(r'মনে রাখো|শিখে নাও|স্মরণে রাখো', user_message)
                if len(parts) > 1 and "=" in parts[1]:
                    q, a = parts[1].split("=", 1)
                    q, a = q.strip(), a.strip()
                    db.reference(f'memory/{q}').set(a)
                    ai_reply = f"ধন্যবাদ! আমি মনে রাখলাম যে: '{q}' মানে হলো '{a}'।"
                    action_taken = "KNOWLEDGE_ACQUIRED"
                else:
                    ai_reply = "মেমোরিতে সেভ করতে এভাবে বলুন: 'মনে রাখো আমার নাম = রানা'"
            except Exception:
                ai_reply = "তথ্যটি মেমোরিতে সেভ করতে সমস্যা হয়েছে।"

        # ৫. অ্যালার্ম প্রোটোকল
        if not ai_reply and any(word in user_message for word in ["জরুরি", "বিপদ", "এলার্ম"]):
            ai_reply = "জরুরি সংকেত গ্রহণ করা হয়েছে। ৪ সেকেন্ডের হালকা অ্যালার্ম ট্রিগার করা হলো।"
            action_taken = "MILD_ALARM_TRIGGERED"
            alert_type = "warning"

        # ৬. ডাটা ডিলিট প্রোটোকল
        elif not ai_reply and ("ডিলিট" in user_message or "delete" in user_message):
            if "সব" in user_message or "পুরোনো" in user_message:
                try:
                    db.reference('live_feed').delete()
                    ai_reply = "সার্ভারের সমস্ত পুরোনো ম্যাট্রিক্স ডাটা সফলভাবে মুছে ফেলা হয়েছে।"
                    action_taken = "DATA_DELETED"
                except Exception:
                    ai_reply = "ডাটা মুছে ফেলতে সমস্যা হয়েছে।"
            else:
                ai_reply = "নির্দিষ্ট করে বলুন কোন ডাটা ডিলিট করবেন।"

        # ৭. অংক সমাধান
        elif not ai_reply and safe_eval_math(user_message):
            ai_reply = safe_eval_math(user_message)
            action_taken = "MATH_SOLVED"

        # ৮. মেমোরি ও লোকাল কাস্টম নলেজ ম্যাচিং
        elif not ai_reply:
            # আগে ফায়ারবেস মেমোরি চেক করবে
            learned_memory = db.reference('memory').get() or {}
            found_in_memory = False
            for k, v in learned_memory.items():
                if k in user_message:
                    ai_reply = str(v)
                    action_taken = "LEARNED_MEMORY_MATCH"
                    found_in_memory = True
                    break
            
            # মেমোরিতে না পেলে লোকাল ফিক্সড উত্তর চেক করবে
            if not found_in_memory:
                for k in LOCAL_KNOWLEDGE:
                    if k in user_message:
                        ai_reply = LOCAL_KNOWLEDGE[k]
                        action_taken = "LOCAL_KNOWLEDGE_MATCH"
                        break

        # ৯. সাধারণ কনভার্সেশন (ডিফল্ট)
        if not ai_reply:
            ai_reply = f"আপনার নির্দেশ প্রাপ্ত হয়েছে: '{user_message}'।"
            action_taken = "GENERAL_CHAT"

        # ফায়ারবেসে লাইভ লগ পেস্ট করা
        try:
            db.reference('live_feed').push({
                'action': action_taken,
                'details': user_message,
                'time': db.ServerValue.TIMESTAMP
            })
        except Exception:
            pass

        return jsonify({
            "reply": ai_reply,
            "action": action_taken,
            "alert_type": alert_type
        }), 200

    except Exception as e:
        return jsonify({
            "reply": "সার্ভারে রেসপন্স প্রসেস করতে সমস্যা হয়েছে।",
            "error": str(e)
        }), 500

# সেন্সর আপডেট এন্ডপয়েন্ট (ESP32 এর জন্য)
@app.route('/update_sensors', methods=['POST'])
def update_sensors():
    try:
        data = request.get_json(silent=True) or {}
        temp = data.get('temp')
        gas = data.get('gas')
        
        if temp is not None:
            db.reference('sensors/temperature').set(temp)
        if gas is not None:
            db.reference('sensors/gas').set(gas)
            
        return jsonify({"status": "SUCCESS"}), 200
    except Exception as e:
        return jsonify({"status": "FAILED", "error": str(e)}), 500

# লাইভ ম্যাট্রিক্স ফিড এন্ডপয়েন্ট (HTML ফ্রন্টএন্ডের জন্য)
@app.route('/get_live_matrix', methods=['GET'])
def get_live_matrix():
    try:
        ref = db.reference('live_feed')
        feed_data = ref.order_by_child('time').limit_to_last(15).get()
        feed_list = []
        if feed_data:
            for key, val in feed_data.items():
                feed_list.append({
                    "id": key,
                    "action": val.get('action', 'UNKNOWN'),
                    "details": val.get('details', ''),
                    "time": str(val.get('time', ''))
                })
        return jsonify({"live_feed": feed_list}), 200
    except Exception as e:
        return jsonify({"live_feed": [], "error": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
