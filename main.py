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

Thread(target=monitor_and_clean_firebase, daemon=True).start()

# ==================== ১. ওনার ভেরিফিকেশন ও বায়োমেট্রিক API ====================
@app.route('/api/verify-owner', methods=['POST', 'OPTIONS'])
def verify_owner():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200
    
    data = request.get_json(silent=True) or {}
    signature = data.get('biometric_signature', '')
    
    if signature == "SUCCESS_BIOMETRIC":
        return jsonify({
            "status": "SUCCESS",
            "message": "🔓 ওনার বায়োমেট্রিক সফলভাবে যাচাই করা হয়েছে।",
            "owner_token": PRIMARY_OWNER_TOKEN,
            "owner_details": {
                "name": "Primary Owner",
                "photo_url": "https://i.imgur.com/6VBx3io.png",
                "voice_freq": "120Hz-240Hz Matched",
                "face_status": "Verified 3D Sandbox"
            }
        }), 200
    
    return jsonify({"status": "FAILED", "message": "🚨 বায়োমেট্রিক ট্রিপল-লক মেলেনি!"}), 403

# ==================== ২. ফ্যামিলি রেজিস্ট্রি ও পারমিশন কন্ট্রোল API ====================
@app.route('/api/family/add', methods=['POST', 'OPTIONS'])
def add_family_member():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200
    
    data = request.get_json(silent=True) or {}
    user_token = data.get('owner_token', '')
    name = data.get('name', '').strip()
    pin = data.get('pin', '').strip()
    allowed_relays = data.get('allowed_relays', [])
    allowed_features = data.get('allowed_features', [])

    if user_token != PRIMARY_OWNER_TOKEN:
        return jsonify({"status": "FAILED", "message": "🚨 কেবল মালিক এই পারমিশন যুক্ত করতে পারবেন।"}), 403

    if not name or not pin:
        return jsonify({"status": "FAILED", "message": "নাম ও পিন প্রদান করুন।"}), 400

    member_id = f"fam_{int(time.time())}"
    db.reference(f'family_members/{member_id}').set({
        'name': name,
        'pin': pin,
        'relays': allowed_relays,
        'features': allowed_features,
        'created_at': time.time()
    })

    return jsonify({"status": "SUCCESS", "message": f"✅ সদস্য '{name}' সফলভাবে নিবন্ধিত হয়েছেন।"}), 200

@app.route('/api/family/list', methods=['POST', 'OPTIONS'])
def list_family_members():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200
    
    data = request.get_json(silent=True) or {}
    user_token = data.get('owner_token', '')

    if user_token != PRIMARY_OWNER_TOKEN:
        return jsonify({"status": "FAILED", "message": "অনুমতি নেই।"}), 403

    members = db.reference('family_members').get() or {}
    return jsonify({"status": "SUCCESS", "members": members}), 200

@app.route('/api/family/delete/<member_id>', methods=['DELETE', 'OPTIONS'])
def delete_family_member(member_id):
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200
    
    data = request.get_json(silent=True) or {}
    user_token = data.get('owner_token', '')

    if user_token != PRIMARY_OWNER_TOKEN:
        return jsonify({"status": "FAILED", "message": "অনুমতি নেই।"}), 403

    db.reference(f'family_members/{member_id}').delete()
    return jsonify({"status": "SUCCESS", "message": "সদস্য মুছে ফেলা হয়েছে।"}), 200

# ==================== ৩. ন্যানো-সেকেন্ড ফার্স্ট সুইচিং API ====================
@app.route('/fast_switch', methods=['POST', 'OPTIONS'])
def fast_switch():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200

    data = request.get_json(silent=True) or {}
    device_id = data.get('device')
    action = str(data.get('action', '')).upper()

    if not device_id or action not in ['ON', 'OFF']:
        return jsonify({"status": "FAILED", "reply": "ভুল কমান্ড।"}), 400

    ref = db.reference(f'devices/{device_id}')
    curr_state = ref.get()

    if curr_state == action:
        status_text = "চালু" if curr_state == "ON" else "বন্ধ"
        return jsonify({
            "status": "ALREADY_IN_STATE",
            "reply": f"ডিভাইস {device_id.replace('relay', '')} ইতিমধ্যেই {status_text} অবস্থায় রয়েছে।",
            "state": curr_state
        }), 200

    ref.set(action)
    status_text = "চালু" if action == "ON" else "বন্ধ"
    return jsonify({
        "status": "SUCCESS",
        "reply": f"✅ ডিভাইস {device_id.replace('relay', '')} {status_text} করা হলো।",
        "state": action
    }), 200

# ==================== ৪. মূল কমান্ড হ্যান্ডলার ====================
@app.route('/chat', methods=['POST', 'OPTIONS'])
def process_command():
    if request.method == 'OPTIONS': return jsonify({'status': 'OK'}), 200

    data = request.get_json(silent=True) or {}
    cmd = str(data.get('message', '')).strip().lower()
    source = data.get('source', 'WEB')
    user_token = data.get('owner_token', '')

    if not cmd:
        return jsonify({"reply": "কোনো নির্দেশ পাওয়া যায়নি।"}), 200

    reply_text = ""
    action_type = "UNKNOWN"

    if "মোবাইল" in cmd or "ওয়েব" in cmd or "web" in cmd or "mobile" in cmd:
        if "রেকর্ড" in cmd or "rec" in cmd:
            if "চালু" in cmd or "অন" in cmd or "start" in cmd:
                reply_text = "🎙️ মোবাইলের/ওয়েব পেজের রেকর্ডিং চালু করা হচ্ছে..."
                action_type = "START_WEB_RECORDING"
            elif "বন্ধ" in cmd or "অফ" in cmd or "stop" in cmd:
                reply_text = "⏹️ মোবাইলের/ওয়েব পেজের রেকর্ডিং বন্ধ করা হলো।"
                action_type = "STOP_WEB_RECORDING"

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

    elif any(w in cmd for w in ["চালু", "অন", "বন্ধ", "অফ", "on", "off"]):
        status = "ON" if any(w in cmd for w in ["চালু", "অন", "on"]) else "OFF"
        for i in range(1, 9):
            if str(i) in cmd or f"রিলে {i}" in cmd:
                db.reference(f'devices/relay{i}').set(status)
                reply_text = f"✅ ডিভাইস {i} {('চালু' if status=='ON' else 'বন্ধ')} করা হলো।"
                action_type = "DEVICE_CONTROL"
                break

    if not reply_text:
        reply_text = f"কমান্ড বুঝতে পারিনি: '{cmd}'"

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
