from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# Groq-এর বর্তমানে চালু ও এক্টিভ মডেলগুলোর তালিকা
ACTIVE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama3-8b-8192",
    "llama3-70b-8192",
    "gemma2-9b-it"
]

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো বার্তা লিখুন।"})

    if not GROQ_KEY:
        return jsonify({"reply": "Render-এ GROQ_API_KEY সেট করা হয়নি!"})

    try:
        client = Groq(api_key=GROQ_KEY)
        
        # ব্যাকআপ সিস্টেম: প্রথম মডেল না পেলে পরেরটিতে চেষ্টা করবে
        for model_name in ACTIVE_MODELS:
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "আপনি 'চিঠি রোবট'। ব্যবহারকারীর প্রশ্নের উত্তর সবসময় সহজ ও সুন্দর বাংলায় দিন।"},
                        {"role": "user", "content": msg}
                    ],
                    temperature=0.7,
                    max_tokens=1024
                )
                reply = completion.choices[0].message.content
                if reply:
                    return jsonify({"reply": reply})
            except Exception:
                continue

        return jsonify({"reply": "কোনো মডেল সাড়া দিচ্ছে না, কিছুক্ষণ পর চেষ্টা করুন।"})

    except Exception as e:
        return jsonify({"reply": f"Groq Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
