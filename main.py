from flask import Flask, request, jsonify
from flask_cors import CORS
import os, requests

app = Flask(__name__)
CORS(app)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

AI_MODELS = [
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini"
]

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Active"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    msg = data.get("message", "")
    if not msg:
        return jsonify({"reply": "মেসেজ লিখুন।"})

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    for model in AI_MODELS:
        try:
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", json={
                "model": model,
                "messages": [{"role": "user", "content": msg}]
            }, headers=headers, timeout=10)
            if res.status_code == 200:
                return jsonify({"reply": res.json()['choices'][0]['message']['content']})
        except:
            continue

    return jsonify({"reply": "সার্ভার রেসপন্স করছে না।"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
