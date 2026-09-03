import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)

# ফায়ারবেস ইনিশিয়ালাইজেশন (রেন্ডারের এনভায়রনমেন্ট ভেরিয়েবল বা ডিফল্ট ডাটাবেস URL দিয়ে)
DATABASE_URL = "https://chitti-bfa21-default-rtdb.firebaseio.com/"

try:
    if not firebase_admin._apps:
        # যদি আপনার কাছে serviceAccountKey.json ফাইল থাকে তবে সেটি ব্যবহার করতে পারেন, 
        # অথবা সরাসরি ডাটাবেস ইউআরএল দিয়ে অ্যাপ ইনিশিয়াল করতে পারেন।
        firebase_admin.initialize_app(options={
            'databaseURL': DATABASE_URL
        })
except Exception as e:
    print(f"Firebase Init Error: {e}")

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Online", "system": "Chitti AI Pro Backend Running"})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '').strip().lower()
        
        ai_reply = ""
        action_taken = "GENERAL_CHAT"

        # ১. পুরোনো বা অপ্রয়োজনীয় ডাটা ইনস্ট্যান্ট ডিলিট করার লজিক
        if any(keyword in user_message for keyword in ["ডিলিট", "delete", "মুছে", "cleardata", "clear"]):
            if any(term in user_message for term in ["সব", "পুরোনো", "পুরাতন", "প্রয়োজন নাই", "অপ্রয়োজনীয়", "old"]):
                try:
                    # ফায়ারবেসের ট্রাফিক লগ বা লাইভ ফিড ডাটা ডিলিট করা
                    db.reference('live_feed').delete()
                    ai_reply = "আপনার নির্দেশ অনুযায়ী সার্ভারের সমস্ত পুরোনো ও অপ্রয়োজনীয় ডাটা সফলভাবে ডিলিট করে দেওয়া হয়েছে।"
                    action_taken = "DATA_DELETED"
                except Exception as ex:
                    ai_reply = f"ডাটা ডিলিট করার সময় একটি ত্রুটি হয়েছে: {str(ex)}"
                    action_taken = "ERROR"
            else:
                ai_reply = "কোন ডাটাগুলো ডিলিট করব? নির্দিষ্ট করে বলুন, তাহলে ইনস্ট্যান্ট ডিলিট করে দেব।"
                action_taken = "SPECIFY_DATA_NEEDED"

        # ২. রেকর্ডিং চালু বা বন্ধ করার লজিক
        elif "রেকর্ডিং চালু" in user_message or "start recording" in user_message or "রেকর্ড চালু" in user_message:
            ai_reply = "রেকর্ডিং সিস্টেম সফলভাবে সক্রিয় করা হয়েছে। এখন থেকে সমস্ত অডিও এবং লজিক ফ্লো রেকর্ড করা হবে।"
            action_taken = "RECORDING_ON"
            # হার্ডওয়্যার বা ফায়ারবেসে স্টেট আপডেট করার জন্য
            db.reference('system_state/recording').set("ON")

        elif "রেকর্ডিং বন্ধ" in user_message or "stop recording" in user_message or "রেকর্ড বন্ধ" in user_message:
            ai_reply = "রেকর্ডিং বন্ধ করে দেওয়া হয়েছে।"
            action_taken = "RECORDING_OFF"
            db.reference('system_state/recording').set("OFF")

        # ৩. বিশেষ ঘোষণা বা সিক্রেট শোনানোর কমান্ড
        elif "ঘোষণা" in user_message or "announcement" in user_message:
            ai_reply = "বিশেষ ঘোষণা: সিস্টেমের সিকিউরিটি এবং প্যাকেট ফ্লো সম্পূর্ণ স্বাভাবিক রয়েছে। এই বার্তাটি শুধুমাত্র আপনার গোপনীয়তার জন্য।"
            action_taken = "SPECIAL_ANNOUNCEMENT"

        # ৪. সাধারণ চ্যাট এবং প্রম্পট রেসপন্স
        else:
            ai_reply = f"আপনার কমান্ডটি সিস্টেমে রেকর্ড করা হয়েছে: '{user_message}'। লক্ষ্য ঠিক রেখে এগিয়ে চলুন!"
            action_taken = "GENERAL_CHAT"

        # লাইভ ম্যাট্রিক্স ফিডে লগ সেভ করা যাতে ফ্রন্টএন্ডে রিয়েল-টাইম দেখা যায়
        try:
            db.reference('live_feed').push({
                'action': action_taken,
                'details': user_message,
                'time': db.ServerValue.TIMESTAMP
            })
        except Exception:
            pass

        return jsonify({
            "reply": ai_reply,
            "action": action_taken
        }), 200

    except Exception as e:
        return jsonify({
            "reply": "সার্ভারে প্রসেসিংয়ের সময় একটি সমস্যা হয়েছে।",
            "error": str(e)
        }), 500

@app.route('/get_live_matrix', methods=['GET'])
def get_live_matrix():
    try:
        ref = db.reference('live_feed')
        feed_data = ref.order_by_child('time').limit_to_last(15).get()
        
        feed_list = []
        if feed_data:
            for key, val in feed_data.items():
                feed_list.append({
                    "id": key,
                    "action": val.get('action', 'UNKNOWN'),
                    "details": val.get('details', ''),
                    "time": str(val.get('time', ''))
                })
        return jsonify({"live_feed": feed_list}), 200
    except Exception as e:
        return jsonify({"live_feed": [], "error": str(e)}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
