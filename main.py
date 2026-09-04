import os
import time
import json
from threading import Thread
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# ==================== Firebase Setup ====================
DATABASE_URL = os.environ.get('FIREBASE_DB_URL', "https://chitti-bfa21-default-rtdb.firebaseio.com/")
cred_json_str = os.environ.get('FIREBASE_CREDENTIALS')

try:
    if not firebase_admin._apps:
        if cred_json_str:
            cred_dict = json.loads(cred_json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
        else:
            firebase_admin.initialize_app(options={'databaseURL': DATABASE_URL})
except Exception as e:
    print(f"Firebase Init Error: {e}")

PRIMARY_OWNER_TOKEN = "VERIFIED_PRIMARY_OWNER_BIOMETRIC_TOKEN"

# ==================== ফায়ারবেস মনিটরিং ও পুরোনো ডাটা চেকিং ====================
def monitor_and_clean_firebase():
    """সবসময় ফায়ারবেসের পুরানো ডাটা চেক করবে এবং নির্দিষ্ট সময় পর রিমুভ করবে"""
    while True:
        try:
            current_time = time.time()
            cutoff_seconds = 6 * 3600  # ৬ ঘণ্টার পুরোনো ডাটা মুছে যাবে

            # লাইভ ফিড বা পুরোনো ইভেন্ট লগ চেকিং
            logs_ref = db.reference('live_feed')
            logs = logs_ref.get() or {}
            if isinstance(logs, dict):
                for log_id, data in logs.items():
                    if isinstance(data, dict):
                        log_time = data.get('time', 0)
                        # মিলি সেকেন্ড হলে সেকেন্ডে রূপান্তর
                        if log_time > 1e11: log_time /= 1000
                        if (current_time - log_time) > cutoff_seconds:
                            db.reference(f'live_feed/{log_id}').delete()

            # পুরোনো কমান্ড স্ট্যাটাস ফিল্টারিং
            cmd_ref = db.reference('esp32_commands')
            cmds = cmd_ref.get() or {}
            if isinstance(cmds, dict):
                for cmd_id, data in cmds.items():
                    if isinstance(data, dict) and data.get('status') == 'EXECUTED':
                        db.reference(f'esp32_commands/{cmd_id}').delete()

        except Exception as e:
            print(f"Firebase Monitor Engine Warning: {e}")
            
        time.sleep(300) # প্রতি ৫ মিনিট পর পর ব্যাকগ্রাউন্ড স্ক্যান সম্পন্ন হবে

# ব্যাকগ্রাউন্ড ট্রেড চালু রাখা
Thread(target=monitor_and_clean_firebase, daemon=True).start()

# ==================== মূল কমান্ড হ্যান্ডলার ====================
@app.route('/chat', methods=['POST', 'OPTIONS'])
def process_command():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200

    data = request.get_json(silent=True) or {}
    cmd = str(data.get('message', '')).strip().lower()
    source = data.get('source', 'WEB') # WEB/MOBILE অথবা ESP32
    user_token = data.get('owner_token', '')

    if not cmd:
        return jsonify({"reply": "কোনো নির্দেশ পাওয়া যায়নি।"}), 200

    reply_text = ""
    action_type = "UNKNOWN"
    is_owner = (user_token == PRIMARY_OWNER_TOKEN)

    # ১. মোবাইল ও ওয়েব রেকর্ডিং কমান্ড
    if "মোবাইল" in cmd or "ওয়েব" in cmd or "web" in cmd or "mobile" in cmd:
        if "রেকর্ড" in cmd or "rec" in cmd:
            if "চালু" in cmd or "অন" in cmd or "start" in cmd:
                reply_text = "🎙️ মোবাইলের/ওয়েব পেজের রেকর্ডিং চালু করা হচ্ছে..."
                action_type = "START_WEB_RECORDING"
            elif "বন্ধ" in cmd or "অফ" in cmd or "stop" in cmd:
                reply_text = "⏹️ মোবাইলের/ওয়েব পেজের রেকর্ডিং বন্ধ করা হলো।"
                action_type = "STOP_WEB_RECORDING"

    # ২. ইএসপি৩২ (ESP32) হার্ডওয়্যার রেকর্ডিং কমান্ড
    elif "ইএসপি" in cmd or "esp" in cmd or "বোর্ড" in cmd or source == "ESP32":
        if "রেকর্ড" in cmd or "rec" in cmd:
            if "চালু" in cmd or "অন" in cmd or "start" in cmd:
                db.reference('esp32_control/recording').set("START")
                reply_text = "🎙️ ESP32 বোর্ডের সিক্রেট রেকর্ডিং চালু করা হলো।"
                action_type = "ESP_REC_ON"
            elif "বন্ধ" in cmd or "অফ" in cmd or "stop" in cmd:
                db.reference('esp32_control/recording').set("STOP")
                reply_text = "⏹️ ESP32 বোর্ডের রেকর্ডিং বন্ধ করা হলো।"
                action_type = "ESP_REC_OFF"

    # ৩. জেনেরিক রেকর্ডিং কমান্ড (সোর্স ধরে সিদ্ধান্ত নেবে)
    elif "রেকর্ড" in cmd or "রেকর্ডিং" in cmd:
        if "চালু" in cmd or "অন" in cmd or "start" in cmd:
            if source == "ESP32":
                db.reference('esp32_control/recording').set("START")
                reply_text = "🎙️ ESP32 মাইক দিয়ে রেকর্ডিং শুরু করা হলো।"
                action_type = "ESP_REC_ON"
            else:
                reply_text = "🎙️ মোবাইলের মাইক্রোফোন দিয়ে রেকর্ডিং শুরু করা হচ্ছে।"
                action_type = "START_WEB_RECORDING"
        elif "বন্ধ" in cmd or "অফ" in cmd or "stop" in cmd:
            if source == "ESP32":
                db.reference('esp32_control/recording').set("STOP")
                reply_text = "⏹️ ESP32 বোর্ডের রেকর্ডিং থামানো হলো।"
                action_type = "ESP_REC_OFF"
            else:
                reply_text = "⏹️ মোবাইলের রেকর্ডিং বন্ধ করা হলো।"
                action_type = "STOP_WEB_RECORDING"

    # ৪. রিলে ও সুইচ কন্ট্রোল
    elif any(w in cmd for w in ["চালু", "অন", "বন্ধ", "অফ", "on", "off"]):
        status = "ON" if any(w in cmd for w in ["চালু", "অন", "on"]) else "OFF"
        for i in range(1, 9):
            if str(i) in cmd or f"রিলে {i}" in cmd:
                db.reference(f'devices/relay{i}').set(status)
                reply_text = f"✅ ডিভাইস {i} {('চালু' if status=='ON' else 'বন্ধ')} করা হলো।"
                action_type = "DEVICE_CONTROL"
                break

    # কমান্ড নিশ্চিত না হলে
    if not reply_text:
        reply_text = f"কমান্ড বুঝতে পারিনি: '{cmd}'"

    # ফায়ারবেসে তথ্য যুক্ত করা
    try:
        db.reference('live_feed').push({
            'action': action_type,
            'command': cmd,
            'source': source,
            'time': db.ServerValue.TIMESTAMP
        })
    except Exception:
        pass

    return jsonify({"reply": reply_text, "action": action_type}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
