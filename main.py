
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# ফায়ারবেস কানেকশন ইনিশিয়ালাইজেশন
try:
    firebase_cred_json = os.environ.get("FIREBASE_CRED")
    firebase_db_url = os.environ.get("FIREBASE_DB_URL", "https://chitti-bfo2i-default-rtdb.firebaseio.com/")
    if not firebase_admin._apps:
        cred = credentials.Certificate(eval(firebase_cred_json))
        firebase_admin.initialize_app(cred, {
            'databaseURL': firebase_db_url
        })
    print("Firebase Connected Successfully!")
except Exception as e:
    print(f"Firebase Init Error: {e}")

# 🤖 এআই অটোনোমাস প্রজেক্ট এবং ইনকাম জেনারেটর ইঞ্জিন
@app.route('/api/ai/autonomous-engine', methods=['POST'])
def autonomous_engine():
    data = request.json or {}
    niche = data.get("niche", "ESP32 Autonomous IoT & Smart Robotics")
    
    # এআই নিজে থেকেই ট্রেন্ডিং ও হাই-পেমেন্ট টেক টপিক তৈরি করবে
    title = f"🔥 How to Build an Autonomous {niche} (Zero-Effort Guide)"
    description = (
        f"Discover the ultimate automated workflow for {niche}. "
        f"We cover hardware bridging, PCB layouts, and automated tech monetization.\n\n"
        f"💰 Monetization & Earning Sources:\n"
        f"- YouTube Partner Program (AdSense)\n"
        f"- Hardware Affiliate Links & Sponsorships\n\n"
        f"#Automation #{niche.replace(' ', '')} #IoTProjects #TechIncomes"
    )
    
    ai_generated_package = {
        "project_title": title,
        "description": description,
        "status": "Ready for Auto-Publish",
        "income_streams": ["YouTube AdSense", "Amazon/AliExpress Tech Affiliate"],
        "pcb_status": "Auto-Optimized via EasyEDA Rules"
    }
    
    # ফায়ারবেসে প্রজেক্টটি সেভ করা
    ref = db.reference("autonomous_projects")
    new_ref = ref.push(ai_generated_package)
    
    return jsonify({
        "success": True,
        "message": "AI has successfully generated autonomous project & income pipeline!",
        "package": ai_generated_package
    })

@app.route('/api/webhook/status', methods=['GET'])
def get_system_status():
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
