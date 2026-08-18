from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Chitti Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "").strip()
    
    if not msg:
        return jsonify({"reply": "অনুগ্রহ করে কোনো বার্তা লিখুন।"})

    if not OPENROUTER_KEY:
        return jsonify({"reply": "Render-এ OPENROUTER_API_KEY সেট করা হয়নি!"})

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "https://ahimm029-max.github.io",
                "X-Title": "Chitti Robot",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": [
                    {"role": "system", "content": "আপনি 'চিঠি রোবট'। সবসময় সহজ ও সুন্দর বাংলায় উত্তর দিন।"},
                    {"role": "user", "content": msg}
                ]
            }
        )
        
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            reply = result["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"OpenRouter Error: {result}"})

    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    
