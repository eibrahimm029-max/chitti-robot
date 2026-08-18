from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

# Render Environment Variable থেকে Groq API Key লোড করা হচ্ছে
GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো বার্তা লিখুন।"})

    if not GROQ_KEY:
        return jsonify({"reply": "Render-এ GROQ_API_KEY সেট করা হয়নি!"})

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "আপনি 'চিঠি রোবট'। ব্যবহারকারী যেকোনো ভাষায় প্রশ্ন করুক না কেন, উত্তর সবসময় স্পষ্ট ও সুন্দর বাংলায় দিন।"},
            {"role": "user", "content": msg}
        ]
    }

    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10)
        
        if res.status_code == 200:
            result = res.json()
            reply_text = result['choices'][0]['message']['content']
            return jsonify({"reply": reply_text})
        else:
            return jsonify({"reply": f"Groq Error: {res.status_code}"})
    except Exception as e:
        return jsonify({"reply": "সার্ভার রেসপন্স করতে সমস্যা হচ্ছে, আবার চেষ্টা করুন।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
