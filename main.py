<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>চিঠি এআই প্রো সিস্টেম - ভিআইপি সাইবার ড্যাশবোর্ড</title>
    
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js"></script>
    <script src="https://www.gstatic.com/firebasejs/8.10.1/firebase-database.js"></script>

    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            background: linear-gradient(135deg, #05050e 0%, #121225 100%); 
            color: #00ffcc; 
            font-family: 'Segoe UI', Arial, sans-serif; 
            text-align: center; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 15px;
        }
        .box { 
            border: 2px solid rgba(0, 255, 204, 0.3); padding: 20px; border-radius: 20px; 
            width: 100%; max-width: 480px; box-shadow: 0 0 30px rgba(0, 255, 204, 0.15); 
            background: rgba(16, 16, 26, 0.9); backdrop-filter: blur(10px);
            max-height: 95vh; overflow-y: auto; position: relative;
        }

        /* হেডার ও নোটিফিকেশন বেল স্টাইল */
        .header-bar {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid rgba(0, 255, 204, 0.2); padding-bottom: 8px; margin-bottom: 12px;
        }
        .notif-bell-container { position: relative; cursor: pointer; font-size: 20px; }
        .notif-badge {
            position: absolute; top: -5px; right: -8px; background: #ff0055; color: #fff;
            border-radius: 50%; padding: 2px 5px; font-size: 10px; font-weight: bold;
        }
        .notif-dropdown {
            display: none; position: absolute; top: 35px; right: 0; background: #0c182b;
            border: 1px solid #00ffcc; width: 260px; max-height: 220px; overflow-y: auto;
            z-index: 1000; border-radius: 8px; text-align: left; padding: 10px; box-shadow: 0 0 15px #000;
        }
        .notif-item { font-size: 11px; padding: 6px 0; border-bottom: 1px solid rgba(0, 255, 204, 0.1); word-break: break-all; }
        .notif-item.danger { color: #ff3333; font-weight: bold; }
        .notif-item.warning { color: #ffcc00; }

        /* লকডাউন ব্যানার */
        #lockdownBanner {
            display: none; background: #ff0033; color: #fff; padding: 10px; border-radius: 8px;
            font-size: 12px; font-weight: bold; margin-bottom: 10px; animation: blink 1s infinite;
        }

        h2 { font-size: 20px; text-shadow: 0 0 10px #00ffcc; }
        #robotFace { background: #000; border: 2px solid #00ffcc; border-radius: 15px; margin: 10px auto; display: block; }
        #reply { margin: 10px 0; min-height: 45px; font-size: 14px; line-height: 1.4; color: #ffffff; background: rgba(0, 0, 0, 0.6); padding: 10px; border-radius: 10px; border-left: 3px solid #00ffcc; text-align: left; }
        
        .retro-monitor {
            background: #0b1a14; border: 2px solid #00ffcc; border-radius: 8px; padding: 8px 12px;
            margin: 10px 0; font-family: 'Courier New', Courier, monospace; text-align: left;
            box-shadow: inset 0 0 10px rgba(0, 255, 204, 0.3); position: relative;
        }
        .monitor-header { font-size: 11px; color: #00aa88; border-bottom: 1px dashed #005544; padding-bottom: 3px; margin-bottom: 5px; display: flex; justify-content: space-between; align-items: center; }
        
        .menu-btn { background: #00ffcc; color: #000; border: none; padding: 2px 6px; font-size: 10px; font-weight: bold; border-radius: 4px; cursor: pointer; }
        .menu-btn:hover { background: #ff0055; color: #fff; }

        .monitor-body { font-size: 12px; color: #00ffcc; line-height: 1.4; }
        .status-safe { color: #00ffcc; }
        .status-alert { color: #ff3333; animation: blink 1s infinite; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

        #trafficModal {
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(5, 5, 14, 0.95); z-index: 999; justify-content: center; align-items: center; padding: 20px;
        }
        .modal-content {
            background: #0b1a14; border: 2px solid #00ffcc; border-radius: 12px; width: 100%; max-width: 420px;
            padding: 15px; font-family: 'Courier New', Courier, monospace; text-align: left;
            box-shadow: 0 0 20px rgba(0, 255, 204, 0.3); max-height: 85vh; overflow-y: auto;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #005544; padding-bottom: 5px; margin-bottom: 10px; font-size: 13px; color: #00ffcc; }
        .close-btn { background: #ff0055; color: #fff; border: none; padding: 3px 8px; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .traffic-log { font-size: 11px; color: #00ffcc; background: #000; padding: 8px; border-radius: 6px; margin-top: 5px; height: 200px; overflow-y: auto; border: 1px dashed #005544; }
        .log-entry { margin-bottom: 6px; border-bottom: 1px dotted #222; padding-bottom: 3px; word-break: break-all; }

        .sensor-container { display: flex; justify-content: space-around; background: rgba(0, 0, 0, 0.5); padding: 10px; border-radius: 10px; border: 1px solid #00ffcc; margin: 10px 0; font-size: 13px; }
        
        .switches-list { display: flex; flex-direction: column; gap: 10px; margin: 15px 0; }
        .switch-card {
            background: rgba(24, 24, 42, 0.8); border: 1px solid rgba(0, 255, 204, 0.4); padding: 12px 15px;
            border-radius: 12px; display: flex; align-items: center; justify-content: space-between;
        }
        .switch-label { font-size: 14px; font-weight: bold; color: #fff; }

        .toggle-switch { position: relative; display: inline-block; width: 56px; height: 30px; }
        .toggle-switch input { opacity: 0; width: 0; height: 0; }
        .slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background-color: #33334d; transition: .3s; border-radius: 30px; border: 1px solid #555;
        }
        .slider:before {
            position: absolute; content: ""; height: 24px; width: 24px; left: 3px; bottom: 2px;
            background-color: white; transition: .3s; border-radius: 50%;
        }
        input:checked + .slider { background-color: #00ffcc; border-color: #00ffcc; box-shadow: 0 0 10px #00ffcc; }
        input:checked + .slider:before { transform: translateX(26px); background-color: #000; }

        .input-group { display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 10px; }
        input[type="text"] { background: #000; border: 1px solid #00ffcc; color: #00ffcc; padding: 10px; flex: 1; border-radius: 8px; outline: none; font-size: 14px; }
        .send-btn { background: #00ffcc; color: #000; border: none; padding: 10px 15px; font-weight: bold; cursor: pointer; border-radius: 8px; }
        .mic-btn { background: #ff0055; color: white; border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; box-shadow: 0 0 10px #ff0055; font-size: 16px; flex-shrink: 0; }
    </style>
</head>
<body>

    <div class="box">
        <!-- টপ বার নোটিফিকেশন বেলসহ -->
        <div class="header-bar">
            <h2>🤖 চিঠি এআই প্রো</h2>
            <div class="notif-bell-container" onclick="toggleNotifPanel()">
                🔔 <span id="notifBadge" class="notif-badge">0</span>
                <div id="notifDropdown" class="notif-dropdown">
                    <div style="font-weight:bold; margin-bottom:5px; border-bottom:1px solid #00ffcc;">নোটিফিকেশন প্যানেল</div>
                    <div id="notifContent">কোনো নতুন বার্তা নেই।</div>
                </div>
            </div>
        </div>

        <div id="lockdownBanner">🚨 সিকিউরিটি লকডাউন এক্টিভেটেড! সার্ভার সুরক্ষিত ও লক রাখা হয়েছে।</div>

        <canvas id="robotFace" width="260" height="80"></canvas>
        <div id="reply">সিস্টেম ও প্যাকেট ট্র্যাকিং সক্রিয় রয়েছে।</div>

        <div class="retro-monitor">
            <div class="monitor-header">
                <span>[SYS_MONITOR]</span>
                <div>
                    <span id="liveClock" style="margin-right: 5px;">00:00:00</span>
                    <button class="menu-btn" onclick="openTrafficModal()">মেনু/লগ</button>
                </div>
            </div>
            <div class="monitor-body">
                <div>🛡️ নেটওয়ার্ক: <span id="monitorSec" class="status-safe">সুরক্ষিত (HTTPS)</span></div>
                <div>📡 প্যাকেট: <span id="monitorSig" class="status-safe">রিসিভড (ওকে)</span></div>
                <div>⚠️ সিকিউরিটি: <span id="monitorThreat">কোনো বাধা নেই</span></div>
            </div>
        </div>

        <div id="trafficModal">
            <div class="modal-content">
                <div class="modal-header">
                    <span>📡 এআই থিঙ্কিং ও লাইভ ম্যাট্রিক্স ফিড</span>
                    <button class="close-btn" onclick="closeTrafficModal()">বন্ধ×</button>
                </div>
                <div style="font-size: 11px; margin-bottom: 5px; color: #00aa88;">
                    * ফায়ারবেস ও এআই থিঙ্কিং লাইভ লগ:
                </div>
                <div class="traffic-log" id="trafficLogContainer">
                    <div class="log-entry">[সিস্টেম] ম্যাট্রিক্স মনিটর ইনিশিয়ালাইজড...</div>
                </div>
            </div>
        </div>

        <div class="sensor-container">
            <div>🌡️ তাপমাত্রা: <span id="tempVal">--</span>°C</div>
            <div>🔥 গ্যাস: <span id="gasVal">স্বাভাবিক</span></div>
        </div>

        <div class="switches-list" id="switchesList"></div>

        <div class="input-group">
            <input type="text" id="userInput" placeholder="কমান্ড দিন..." onkeypress="if(event.key==='Enter') sendMsg()">
            <button class="send-btn" onclick="sendMsg()">পাঠান</button>
            <button class="mic-btn" onclick="startVoice()">🎤</button>
        </div>
    </div>

    <script>
        const firebaseConfig = { databaseURL: "https://chitti-bfa21-default-rtdb.firebaseio.com" };
        if (!firebase.apps.length) { firebase.initializeApp(firebaseConfig); }

        let notifCount = 0;
        function toggleNotifPanel() {
            const dropdown = document.getElementById('notifDropdown');
            dropdown.style.display = (dropdown.style.display === 'block') ? 'none' : 'block';
        }

        // ৩-৪ সেকেন্ডের সফট মাইল্ড অ্যালার্ম সাউন্ড প্লেয়ার
        function playMildAlarm() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();

                osc.type = 'sine';
                osc.frequency.setValueAtTime(440, audioCtx.currentTime);
                gain.gain.setValueAtTime(0.08, audioCtx.currentTime);

                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.start();
                setTimeout(() => { osc.stop(); }, 4000); // ঠিক ৪ সেকেন্ড পর অটো মিউট
            } catch(e){}
        }

        function addWebNotification(title, msg, type = "info") {
            notifCount++;
            document.getElementById('notifBadge').innerText = notifCount;
            const container = document.getElementById('notifContent');
            
            if (notifCount === 1) container.innerHTML = "";
            const item = document.createElement('div');
            item.className = `notif-item ${type}`;
            item.innerHTML = `<strong>${title}</strong>: ${msg}`;
            container.prepend(item);

            if (type === 'warning' || type === 'danger') {
                playMildAlarm();
            }
        }

        setInterval(() => {
            const now = new Date();
            document.getElementById('liveClock').innerText = now.toLocaleTimeString();
        }, 1000);

        function addTrafficLog(msg, isAlert = false) {
            const logContainer = document.getElementById('trafficLogContainer');
            if(!logContainer) return;
            const timeStr = new Date().toLocaleTimeString();
            const colorStyle = isAlert ? "color: #ff3333;" : "color: #00ffcc;";
            logContainer.innerHTML += `<div class="log-entry" style="${colorStyle}">[${timeStr}] ${msg}</div>`;
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        let matrixInterval = null;
        async function fetchLiveMatrixFeed() {
            try {
                let res = await fetch("https://chitti-robot-qh89.onrender.com/get_live_matrix");
                let data = await res.json();
                if (data.live_feed && data.live_feed.length > 0) {
                    const logContainer = document.getElementById('trafficLogContainer');
                    if(!logContainer) return;
                    logContainer.innerHTML = ""; 
                    data.live_feed.reverse().forEach(item => {
                        let badgeColor = item.action === "KNOWLEDGE_ACQUIRED" ? "color: #ff00ff;" : "color: #00ffcc;";
                        logContainer.innerHTML += `<div class="log-entry" style="${badgeColor}">[${item.time}] <b>[${item.action}]</b>: ${item.details}</div>`;
                    });
                    logContainer.scrollTop = logContainer.scrollHeight;
                }
            } catch (e) {}
        }

        function openTrafficModal() {
            document.getElementById('trafficModal').style.display = 'flex';
            addTrafficLog("মেনু ওপেন করা হয়েছে: প্যাকেট ট্র্যাকিং সক্রিয়।");
            fetchLiveMatrixFeed();
            matrixInterval = setInterval(fetchLiveMatrixFeed, 2000);
        }
        function closeTrafficModal() {
            document.getElementById('trafficModal').style.display = 'none';
            if(matrixInterval) clearInterval(matrixInterval);
        }

        // ফায়ারবেস কানেকশন ও রিলে মনিটরিং
        for (let i = 1; i <= 8; i++) {
            let key = "relay" + i;
            let ref = firebase.database().ref('devices/' + key);
            
            ref.on('value', function(snapshot) {
                let status = snapshot.val();
                let checkbox = document.getElementById('checkbox_' + key);
                if (checkbox) { 
                    checkbox.checked = (status === "ON"); 
                    document.getElementById('monitorSig').innerText = "রিসিভড (ওকে)";
                    document.getElementById('monitorSig').className = "status-safe";
                }
            }, function(error) {
                document.getElementById('monitorSig').innerText = "প্যাকেট ড্রপ!";
                document.getElementById('monitorSig').className = "status-alert";
                document.getElementById('monitorThreat').innerText = "অস্বাভাবিক ইন্টারসেপ্ট!";
                document.getElementById('monitorThreat').className = "status-alert";
                addWebNotification("সিকিউরিটি এলার্ট", "ফায়ারবেস ডাটাবেসে কানেকশন ড্রপ করেছে!", "warning");
            });
        }

        function toggleDevice(deviceKey) {
            let checkbox = document.getElementById('checkbox_' + deviceKey);
            let newStatus = checkbox.checked ? "ON" : "OFF";
            
            addTrafficLog(`কমান্ড পাঠানো হচ্ছে: ${deviceKey} -> ${newStatus}`);
            firebase.database().ref('/devices/' + deviceKey).set(newStatus)
                .then(() => {
                    addTrafficLog(`সফল: ${deviceKey} আপডেট হয়েছে ${newStatus}`);
                })
                .catch((err) => {
                    addTrafficLog(`ফেইলড: ${deviceKey} আপডেট করা যায়নি`, true);
                });
        }

        const deviceNames = {
            "relay1": "💡 ১ নাম্বার লাইট",
            "relay2": "🌀 ২ নাম্বার ফ্যান",
            "relay3": "🔌 ৩ নাম্বার রিলে",
            "relay4": "🔌 ৪ নাম্বার রিলে",
            "relay5": "🔌 ৫ নাম্বার রিলে",
            "relay6": "🔌 ৬ নাম্বার রিলে",
            "relay7": "🔌 ৭ নাম্বার রিলে",
            "relay8": "🔌 ৮ নাম্বার রিলে"
        };

        const switchesListDiv = document.getElementById('switchesList');
        for (let i = 1; i <= 8; i++) {
            let key = "relay" + i;
            switchesListDiv.innerHTML += `
                <div class="switch-card">
                    <span class="switch-label">${deviceNames[key]}</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="checkbox_${key}" onchange="toggleDevice('${key}')">
                        <span class="slider"></span>
                    </label>
                </div>
            `;
        }

        const SERVER_URL = "https://chitti-robot-qh89.onrender.com/chat";
        const canvas = document.getElementById('robotFace');
        const ctx = canvas.getContext('2d');
        let eyeState = 'idle';

        function drawFace() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = "#00ffcc";
            if (eyeState === 'listening') {
                ctx.beginPath(); ctx.arc(70, 30, 14, 0, Math.PI * 2); ctx.arc(190, 30, 14, 0, Math.PI * 2); ctx.fill();
            } else {
                ctx.fillRect(55, 20, 28, 14); ctx.fillRect(177, 20, 28, 14);
            }
            ctx.beginPath();
            ctx.lineWidth = 3; ctx.strokeStyle = (eyeState === 'speaking') ? "#ff0055" : "#00ffcc";
            ctx.moveTo(90, 55); ctx.lineTo(130, eyeState === 'speaking' ? 65 : 55); ctx.lineTo(170, 55); ctx.stroke();
        }
        setInterval(drawFace, 150);

        function startVoice() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) { alert("ব্রাউজার স্পিচ রিকগনিশন সাপোর্ট করে না।"); return; }
            const recognition = new SpeechRecognition();
            recognition.lang = 'bn-BD';
            eyeState = 'listening';
            recognition.start();
            document.getElementById('reply').innerText = "শুনছি...";

            recognition.onresult = function(event) {
                let spokenText = event.results[0][0].transcript;
                document.getElementById('userInput').value = spokenText;
                sendMsg();
            };
            recognition.onerror = () => { eyeState = 'idle'; };
            recognition.onend = () => { eyeState = 'idle'; };
        }

        function speakText(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                let utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = 'bn-BD';
                eyeState = 'speaking';
                utterance.onend = () => { eyeState = 'idle'; };
                window.speechSynthesis.speak(utterance);
            }
        }

        async function sendMsg() {
            let input = document.getElementById('userInput');
            let replyDiv = document.getElementById('reply');
            let msg = input.value.trim();
            if(!msg) return;

            replyDiv.innerText = "প্রসেস হচ্ছে...";
            input.value = "";
            addTrafficLog(`এআই প্রম্পট পাঠানো হয়েছে: "${msg}"`);

            try {
                let res = await fetch(SERVER_URL, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ message: msg, user_role: "MEMBER" }) // ডিফল্ট রোল ফ্যামিলি মেম্বার
                });

                let data = await res.json();

                if (data.status === "SERVER_TERMINATED") {
                    document.getElementById('lockdownBanner').style.display = 'block';
                    addWebNotification("🚨 সিকিউরিটি রেড থ্রেট!", "হ্যাকিং চেষ্টার অভিযোগে সার্ভার অটো কিলসুইচ ডাউন করা হয়েছে!", "danger");
                    replyDiv.innerText = "সিস্টেম লকডাউন অবস্থায় রয়েছে!";
                    return;
                }

                let aiReply = data.reply || "উত্তর পাওয়া যায়নি।";
                replyDiv.innerText = aiReply;
                
                if (data.alert_type) {
                    addWebNotification("সিস্টেম নোটিফিকেশন", aiReply, data.alert_type);
                }

                addTrafficLog(`এআই রেসপন্স সফল: "${aiReply.substring(0, 30)}..."`);
                speakText(aiReply);
            } catch (err) {
                replyDiv.innerText = "সংযোগের সমস্যা হয়েছে!";
                addTrafficLog("সার্ভার কানেকশন এরর!", true);
                addWebNotification("কানেকশন এরর", "সার্ভারে রেসপন্স পাওয়া যাচ্ছে না", "warning");
                eyeState = 'idle';
            }
        }
    </script>
</body>
</html>
