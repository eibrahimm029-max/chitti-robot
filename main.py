import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ফায়ারবেস কানেকশন ইনিশিয়ালাইজেশন
try:
    firebase_cred_json = os.environ.get("FIREBASE_CRED")
    firebase_db_url = os.environ.get("FIREBASE_DB_URL", "https://chitti-bfo2i-default-rtdb.firebaseio.com/")
    if not firebase_admin._apps and firebase_cred_json:
        cred = credentials.Certificate(eval(firebase_cred_json))
        firebase_admin.initialize_app(cred, {
            'databaseURL': firebase_db_url
        })
        print("Firebase Connected Successfully!")
except Exception as e:
    print(f"Firebase Init Error: {e}")

# ১. হোম পেজ রুট (যাতে ব্রাউজারে 'Not Found' না এসে সার্ভার স্ট্যাটাস দেখায়)
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "system": "Chitti AI Autonomous Ecosystem",
        "status": "Online & Active 24/7",
        "message": "Backend server is running successfully. Connect via GitHub Dashboard or ESP32."
    })

# ২. এআই অটোনোমাস প্রজেক্ট ও পিসিবি জেনারেটর এপিআই
@app.route('/api/ai/autonomous-engine', methods=['POST', 'OPTIONS'])
def autonomous_engine():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    data = request.json or {}
    niche = data.get("niche", "ESP32 Autonomous IoT & PCB Design")
    
    title = f"🔥 How to Build an Autonomous {niche} (Zero-Effort Guide)"
    description = (
        f"Discover the ultimate automated workflow for {niche}.\n\n"
        f"💰 Monetization & Earning Sources:\n"
        f"- YouTube Partner Program (AdSense)\n"
        f"- Hardware Affiliate Links & Sponsorships\n\n"
        f"#Automation #{niche.replace(' ', '')} #IoT #TechIncomes"
    )
    
    ai_generated_package = {
        "project_title": title,
        "description": description,
        "status": "Ready for Auto-Publish",
        "income_streams": ["YouTube AdSense", "Tech Affiliates"],
        "pcb_routing": "Auto-routed via ERC/DRC Rules (EasyEDA compatible)"
    }
    
    try:
        ref = db.reference("autonomous_projects")
        ref.push(ai_generated_package)
    except Exception as e:
        print("Firebase Push Warning:", e)
    
    return jsonify({
        "success": True,
        "message": "AI Generated Autonomous Package Successfully!",
        "package": ai_generated_package
    })

# ৩. সিস্টেম স্ট্যাটাস এন্ডপয়েন্ট
@app.route('/api/webhook/status', methods=['GET', 'OPTIONS'])
def get_system_status():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        ref = db.reference("autonomous_projects")
        tasks = ref.get() or []
        count = len(tasks) if isinstance(tasks, list) else len(tasks.keys())
        return jsonify({
            "status": "online",
            "autonomous_mode": "Active 24/7",
            "active_projects": count
        })
    except Exception as e:
        return jsonify({"status": "online", "active_projects": 0, "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
