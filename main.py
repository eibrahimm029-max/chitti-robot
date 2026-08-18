from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

# Render Environment Variable থেকে API Key নেওয়া হচ্ছে
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# একাধিক ফ্রি এআই মডেলের লিস্ট
AI_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-small-24b-instruct:free"
]

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো বার্তা লিখুন।"})

    if not OPENROUTER_API_KEY:
        return jsonify({"reply": "Render-এ OPENROUTER_API_KEY সেট করা হয়নি!"})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    system_instruction = "আপনি 'চিঠি রোবট'। ব্যবহারকারী যেকোনো ভাষায় প্রশ্ন করুক না কেন, উত্তর সবসময় স্পষ্ট ও সুন্দর বাংলায় দিন।"

    for model in AI_MODELS:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": msg}
                ]
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=15)
            
            if res.status_code == 200:
                result = res.json()
                reply_text = result['choices'][0]['message']['content']
                return jsonify({"reply": reply_text})
        except Exception:
            continue

    return jsonify({"reply": "দুঃখিত, কোনো এআই সার্ভার রেসপন্স করছে না।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
