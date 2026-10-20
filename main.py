import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

# রেন্ডার এনভায়রনমেন্ট থেকে সিক্রেট ইউটিউব এপিআই কি রিড করা
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# ফায়ারবেস ইনিশিয়ালাইজেশন (Render এনভায়রনমেন্ট থেকে ডাটা নিয়ে)
try:
  firebase_cred_json = os.environ.get("FIREBASE_CRED")
  firebase_db_url = os.environ.get(
      "FIREBASE_DB_URL", "https://chitti-bfo2i-default-rtdb.firebaseio.com/"
  )
  if not firebase_admin._apps:
    cred = credentials.Certificate(eval(firebase_cred_json))
    firebase_admin.initialize_app(cred, {"databaseURL": firebase_db_url})
  print("Firebase Connected Successfully!")
except Exception as e:
  print(f"Firebase Init Error: {e}")


@app.route("/", methods=["GET"])
def home():
  return jsonify(
      {
          "status": "Online",
          "message": "Chitti Robot YouTube & Hardware Automation Active",
      }
  )


# ESP32 হার্ডওয়্যার স্ট্যাটাস চেক এন্ডপয়েন্ট
@app.route("/api/webhook/status", methods=["GET"])
def get_hardware_status():
  try:
    ref = db.reference("pending_tasks")
    tasks = ref.get() or []
    pending_count = len(tasks) if isinstance(tasks, list) else len(tasks.keys())

    return jsonify({"status": "online", "pending_tasks": pending_count})
  except Exception as e:
    return jsonify({"status": "online", "pending_tasks": 0, "error": str(e)})


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
