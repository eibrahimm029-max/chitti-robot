import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from google import genai
from google.genai import types
import requests

try:
    from cryptography.fernet import Fernet
    FERNET_AVAILABLE = True
except Exception:
    FERNET_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

try:
    from moviepy import ColorClip, VideoFileClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except Exception:
    try:
        from moviepy.editor import ColorClip, VideoFileClip, concatenate_videoclips
        MOVIEPY_AVAILABLE = True
    except Exception:
        MOVIEPY_AVAILABLE = False

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
PIXVERSE_API_KEY = os.environ.get("PIXVERSE_API_KEY")
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
MASTER_KEY = os.environ.get("MASTER_KEY") or os.environ.get("LINK_SECRET_KEY")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

VOICE_MAP = {
    "Bengali": "bn-BD-NabanitaNeural",
    "English": "en-US-AriaNeural",
    "Hindi": "hi-IN-SwaraNeural",
}

MEDIA_VAULT_CACHE = {}
CUSTOM_ASSET_VAULT = {
    "islamic_nasheed": [],
    "science_space": [],
    "tech_cinematic": [],
}

STATE_LOCK = threading.Lock()
LIVE_MONITOR = {
    "sync_state": "IDLE",  # IDLE বা PROCESSING
    "active_task": None,
    "last_sync_at": None,
    "total_requests": 0,
    "successful_ops": 0,
    "fallback_events": 0,
    "last_error": None,
    "recent_events": [],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def push_live_event(source: str, target: str, status: str, detail: str, is_fallback: bool = False):
    with STATE_LOCK:
        LIVE_MONITOR["last_sync_at"] = _now_iso()
        if is_fallback:
            LIVE_MONITOR["fallback_events"] += 1
        if status == "OK":
            LIVE_MONITOR["successful_ops"] += 1
        elif status == "ERROR":
            LIVE_MONITOR["last_error"] = detail

        LIVE_MONITOR["recent_events"].insert(0, {
            "time": _now_iso(),
            "from": source,
            "to": target,
            "status": status,
            "detail": detail,
        })
        LIVE_MONITOR["recent_events"] = LIVE_MONITOR["recent_events"][:25]


def set_sync_state(state: str, task_name: str | None = None):
    with STATE_LOCK:
        LIVE_MONITOR["sync_state"] = state
        LIVE_MONITOR["active_task"] = task_name
        LIVE_MONITOR["last_sync_at"] = _now_iso()
        if state == "PROCESSING":
            LIVE_MONITOR["total_requests"] += 1


def _get_fernet():
    if not FERNET_AVAILABLE or not MASTER_KEY:
        return None
    try:
        key = base64.urlsafe_b64encode(hashlib.sha256(MASTER_KEY.encode("utf-8")).digest())
        return Fernet(key)
    except Exception:
        return None


def encrypt_link(url: str) -> dict:
    short_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    fernet = _get_fernet()
    if fernet:
        token = fernet.encrypt(url.encode("utf-8")).decode("utf-8")
        push_live_event("MasterBrain", "VaultLock(Fernet)", "OK", f"লিংক লক হয়েছে ({short_hash})")
        return {"id": short_hash, "encrypted": token, "mode": "fernet"}
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8")
    push_live_event("MasterBrain", "VaultLock(Fallback)", "FALLBACK", f"Base64 ফলব্যাক লক ({short_hash})", is_fallback=True)
    return {"id": short_hash, "encrypted": encoded, "mode": "base64_fallback"}


def decrypt_link(token: str, mode: str = "fernet") -> str | None:
    if mode == "fernet":
        fernet = _get_fernet()
        if not fernet:
            return None
        try:
            return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except Exception:
            return None
    try:
        return base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


class MasterBrainNeuralEngine:
    """কেন্দ্রীয় নিয়ন্ত্রক: প্রতিটি মডিউল আলাদা রেখে সিগন্যাল রাউটিং, ক্যাশ ও ফলব্যাক নিয়ন্ত্রণ করে।"""

    def __init__(self):
        self.key_map = {
            "gemini": bool(GEMINI_API_KEY),
            "youtube": bool(YOUTUBE_API_KEY),
            "pixverse": bool(PIXVERSE_API_KEY),
            "pixabay": bool(PIXABAY_API_KEY),
            "pexels": bool(PEXELS_API_KEY),
            "master_lock": bool(MASTER_KEY),
        }

    def route_category(self, niche: str, topic: str) -> str:
        text = f"{niche} {topic}".lower()
        if any(w in text for w in ["islam", "ইসলাম", "nasheed", "নাসিহ", "quran", "কোরআন"]):
            return "islamic_nasheed"
        if any(w in text for w in ["nasa", "space", "planet", "rocket", "satellite", "গ্রহ", "রকেট", "মহাকাশ"]):
            return "science_space"
        return "tech_cinematic"

    def search_nasa_library(self, query: str, media_type: str = "video", limit: int = 3) -> list:
        clean_q = (query or "saturn rocket launch").strip()
        cache_key = f"nasa:{media_type}:{clean_q.lower()}:{limit}"
        if cache_key in MEDIA_VAULT_CACHE:
            push_live_event("MasterBrain", "VaultCache(NASA)", "OK", f"ক্যাশ থেকে পাওয়া গেছে: {clean_q}")
            return MEDIA_VAULT_CACHE[cache_key]

        results = []
        try:
            push_live_event("MasterBrain", "NASA_API", "SYNCING", f"সার্চ হচ্ছে: {clean_q}")
            resp = requests.get(
                "https://images-api.nasa.gov/search",
                params={"q": clean_q, "media_type": media_type},
                timeout=12,
            )
            resp.raise_for_status()
            items = resp.json().get("collection", {}).get("items", [])[:limit]
            for item in items:
                data_list = item.get("data") or []
                links = item.get("links") or []
                title = data_list[0].get("title") if data_list else clean_q
                nasa_id = data_list[0].get("nasa_id") if data_list else None
                preview_url = links[0].get("href") if links else None
                results.append({
                    "source": "nasa",
                    "nasa_id": nasa_id,
                    "title": title,
                    "locked_preview": encrypt_link(preview_url) if preview_url else None,
                })
            push_live_event("NASA_API", "MasterBrain", "OK", f"{len(results)}টি NASA আইটেম এসেছে")
        except Exception as exc:
            push_live_event("NASA_API", "VaultFallback", "FALLBACK", f"NASA ত্রুটি: {str(exc)}", is_fallback=True)

        MEDIA_VAULT_CACHE[cache_key] = results
        return results

    def search_pixabay_videos(self, query: str, per_page: int = 3) -> list:
        if not PIXABAY_API_KEY:
            push_live_event("MasterBrain", "Pixabay_API", "FALLBACK", "Pixabay কী সেট নেই; স্কিপ করা হয়েছে", is_fallback=True)
            return []

        clean_q = (query or "technology").strip()
        cache_key = f"pixabay:{clean_q.lower()}:{per_page}"
        if cache_key in MEDIA_VAULT_CACHE:
            push_live_event("MasterBrain", "VaultCache(Pixabay)", "OK", f"ক্যাশ থেকে পাওয়া গেছে: {clean_q}")
            return MEDIA_VAULT_CACHE[cache_key]

        results = []
        try:
            push_live_event("MasterBrain", "Pixabay_API", "SYNCING", f"ভিডিও খোঁজা হচ্ছে: {clean_q}")
            resp = requests.get(
                "https://pixabay.com/api/videos/",
                params={"key": PIXABAY_API_KEY, "q": clean_q, "per_page": per_page},
                timeout=12,
            )
            resp.raise_for_status()
            for hit in resp.json().get("hits", []):
                videos = hit.get("videos", {})
                chosen = videos.get("medium") or videos.get("small") or {}
                url = chosen.get("url")
                if url:
                    results.append({
                        "source": "pixabay",
                        "id": hit.get("id"),
                        "locked_url": encrypt_link(url),
                    })
            push_live_event("Pixabay_API", "MasterBrain", "OK", f"{len(results)}টি Pixabay ভিডিও এসেছে")
        except Exception as exc:
            push_live_event("Pixabay_API", "VaultFallback", "FALLBACK", f"Pixabay ত্রুটি: {str(exc)}", is_fallback=True)

        MEDIA_VAULT_CACHE[cache_key] = results
        return results

    def monitor_snapshot(self) -> dict:
        with STATE_LOCK:
            telemetry_copy = dict(LIVE_MONITOR)
            telemetry_copy["recent_events"] = list(LIVE_MONITOR["recent_events"])

        modules = [
            {
                "id": "gemini",
                "name": "Master Brain (Gemini)",
                "online": bool(GEMINI_API_KEY),
                "model": GEMINI_MODEL,
                "connects_to": ["Pixabay_API", "NASA_API", "VaultCache"],
                "capability": "স্ক্রিপ্ট, সিন প্ল্যান ও সার্চ কিওয়ার্ড তৈরি",
                "fallback": "অস্থায়ী 503 আসলে অটো-রিট্রাই",
            },
            {
                "id": "pixabay",
                "name": "Pixabay Stock Videos",
                "online": bool(PIXABAY_API_KEY),
                "connects_to": ["MasterBrain", "VaultLock"],
                "capability": "টেক ও সাধারণ স্টক ভিডিও খোঁজা",
                "fallback": "না পেলে NASA / ক্যাশ ভল্টে যাওয়া",
            },
            {
                "id": "nasa",
                "name": "NASA Media Library",
                "online": True,
                "connects_to": ["MasterBrain", "VaultLock"],
                "capability": "গ্রহ, রকেট, স্যাটেলাইট ও মহাকাশ মিডিয়া (কী ছাড়া)",
                "fallback": "ক্যাশ ভল্ট / ডিফল্ট ক্লিপ",
            },
            {
                "id": "master_lock",
                "name": "Master Vault Lock",
                "online": bool(MASTER_KEY),
                "connects_to": ["VaultCache", "CustomAssetVault"],
                "capability": "লিংক ও ভল্ট ডেটা এনক্রিপ্ট করে রাখা",
                "fallback": "Fernet না থাকলে base64_fallback",
            },
            {
                "id": "tts",
                "name": "Edge-TTS Voice Engine",
                "online": EDGE_TTS_AVAILABLE,
                "connects_to": ["OutputsFolder"],
                "capability": "বাংলা/ইংরেজি/হিন্দি ভয়েস অডিও তৈরি (rate/pitch নিয়ন্ত্রণ)",
                "fallback": "ভাষা/টেক্সট যাচাই ও নিরাপদ এরর বার্তা",
            },
            {
                "id": "moviepy",
                "name": "MoviePy Clip Sequencer",
                "online": MOVIEPY_AVAILABLE,
                "connects_to": ["OutputsFolder"],
                "capability": "১–১৫ সেকেন্ডের ছোট ক্লিপ ধাপে ধাপে তৈরি ও যুক্ত করা",
                "fallback": "সর্বোচ্চ ১৫s সীমা ও ডাউনলোডের পর ফাইল মুছে ফেলা",
            },
            {
                "id": "youtube_pixverse",
                "name": "YouTube & PixVerse Connectors",
                "online": bool(YOUTUBE_API_KEY or PIXVERSE_API_KEY),
                "connects_to": ["MasterBrain"],
                "capability": "ইউটিউব রেফারেন্স ও AI ভিজ্যুয়াল কিউ প্রস্তুতি",
                "fallback": "কী না থাকলেও মূল প্রোডাকশন আটকায় না",
            },
        ]

        return {
            "server_time": _now_iso(),
            "secrets_exposed": False,
            "telemetry": telemetry_copy,
            "vault_stats": {
                "cached_queries": len(MEDIA_VAULT_CACHE),
                "categories": {k: len(v) for k, v in CUSTOM_ASSET_VAULT.items()},
            },
            "modules": modules,
        }


neural_brain = MasterBrainNeuralEngine()


async def _save_tts_audio(text: str, voice: str, out_path: str, rate: str = "-4%", pitch: str = "+1Hz") -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def generate_free_tts(text: str, language: str = "Bengali", rate: str = "-4%", pitch: str = "+1Hz") -> dict:
    if not EDGE_TTS_AVAILABLE:
        push_live_event("EdgeTTS", "Client", "ERROR", "edge-tts ইনস্টল নেই")
        return {"ok": False, "error": "edge-tts ইনস্টল করা নেই।"}
    if not text.strip():
        return {"ok": False, "error": "ভয়েসের জন্য কোনো টেক্সট দেওয়া হয়নি।"}

    voice = VOICE_MAP.get(language, "bn-BD-NabanitaNeural")
    filename = f"tts_{int(time.time())}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    set_sync_state("PROCESSING", "Edge-TTS Audio")
    try:
        push_live_event("MasterBrain", "EdgeTTS", "SYNCING", f"ভয়েস তৈরি হচ্ছে ({voice})")
        asyncio.run(_save_tts_audio(text.strip(), voice, filepath, rate=rate, pitch=pitch))
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            push_live_event("EdgeTTS", "Client", "ERROR", "খালি অডিও রেসপন্স এসেছে")
            return {"ok": False, "error": "অডিও তৈরি হয়নি; ভাষা ও টেক্সট যাচাই করুন।"}
        push_live_event("EdgeTTS", "OutputsFolder", "OK", f"অডিও প্রস্তুত: {filename}")
        return {
            "ok": True,
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "file": f"/{OUTPUT_DIR}/{filename}",
            "download_url": f"/api/download/{filename}",
        }
    except Exception as exc:
        push_live_event("EdgeTTS", "Client", "ERROR", str(exc))
        return {"ok": False, "error": f"TTS তৈরি করতে সমস্যা হয়েছে: {str(exc)}"}
    finally:
        set_sync_state("IDLE", None)


def build_sequential_clips(clip_seconds: int = 5, clip_count: int = 3, label: str = "fast_clip") -> dict:
    if not MOVIEPY_AVAILABLE:
        push_live_event("MoviePy", "Client", "ERROR", "MoviePy ব্যবহারযোগ্য নয়")
        return {"ok": False, "error": "MoviePy ব্যবহারযোগ্য নয়।"}

    safe_seconds = max(1, min(int(clip_seconds), 15))
    safe_count = max(1, min(int(clip_count), 6))
    created_files = []
    part_paths = []
    palette = [(20, 30, 55), (45, 25, 65), (18, 52, 58), (60, 32, 38)]

    set_sync_state("PROCESSING", f"MoviePy {safe_seconds}s x {safe_count}")
    try:
        for idx in range(safe_count):
            color = palette[idx % len(palette)]
            clip = ColorClip(size=(640, 360), color=color, duration=safe_seconds)
            trimmed = clip.subclipped(0, safe_seconds) if hasattr(clip, "subclipped") else clip.subclip(0, safe_seconds)
            fname = f"{label}_part_{idx + 1}_{int(time.time())}.mp4"
            fpath = os.path.join(OUTPUT_DIR, fname)
            trimmed.write_videofile(fpath, fps=20, codec="libx264", audio=False, logger=None)
            trimmed.close()
            clip.close()
            part_paths.append(fpath)
            created_files.append(f"/{OUTPUT_DIR}/{fname}")
            push_live_event("MoviePy", "OutputsFolder", "OK", f"ক্লিপ {idx + 1} ({safe_seconds}s) তৈরি হয়েছে")

        merged_name = f"{label}_merged_{int(time.time())}.mp4"
        merged_path = os.path.join(OUTPUT_DIR, merged_name)
        loaded = [VideoFileClip(p) for p in part_paths]
        final_clip = concatenate_videoclips(loaded)
        final_clip.write_videofile(merged_path, fps=20, codec="libx264", audio=False, logger=None)
        final_clip.close()
        for c in loaded:
            c.close()

        push_live_event("MoviePy", "OutputsFolder", "OK", f"মার্জড ভিডিও প্রস্তুত: {merged_name}")
        return {
            "ok": True,
            "mode": label,
            "clip_seconds": safe_seconds,
            "created_count": len(created_files),
            "files": created_files,
            "merged_file": f"/{OUTPUT_DIR}/{merged_name}",
            "download_url": f"/api/download/{merged_name}",
        }
    except Exception as exc:
        push_live_event("MoviePy", "Client", "ERROR", str(exc))
        return {"ok": False, "error": f"ক্লিপ তৈরিতে সমস্যা হয়েছে: {str(exc)}"}
    finally:
        set_sync_state("IDLE", None)


@app.route("/")
def serve_dashboard():
    return send_from_directory(".", "index.html")


@app.route(f"/{OUTPUT_DIR}/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ONLINE",
        "model": GEMINI_MODEL,
        "gemini_configured": bool(GEMINI_API_KEY),
        "youtube_key_configured": bool(YOUTUBE_API_KEY),
        "pixverse_configured": bool(PIXVERSE_API_KEY),
        "pixabay_configured": bool(PIXABAY_API_KEY),
        "secret_key_configured": bool(MASTER_KEY),
        "edge_tts_available": EDGE_TTS_AVAILABLE,
        "moviepy_available": MOVIEPY_AVAILABLE,
    })


@app.route("/api/brain-monitor", methods=["GET"])
def api_brain_monitor():
    return jsonify(neural_brain.monitor_snapshot())


@app.route("/api/encrypt-link", methods=["POST"])
def api_encrypt_link():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    category = neural_brain.route_category(data.get("niche") or "", data.get("topic") or "")
    if not url:
        return jsonify({"ok": False, "error": "লিংক দেওয়া হয়নি।"}), 400
    record = encrypt_link(url)
    CUSTOM_ASSET_VAULT.setdefault(category, []).append(record)
    return jsonify({"ok": True, "category": category, "record": record})


@app.route("/api/generate-plan", methods=["POST"])
def generate_plan():
    if not client:
        push_live_event("MasterBrain", "Gemini", "ERROR", "GEMINI_API_KEY সেট করা নেই")
        return jsonify({"error": "GEMINI_API_KEY সেট করা নেই।"}), 500

    data = request.get_json(silent=True) or {}
    niche = (data.get("niche") or "Tech & AI").strip()
    topic = (data.get("topic") or "বিজ্ঞান ও প্রযুক্তি").strip()
    language = (data.get("language") or "Bengali").strip()
    category = neural_brain.route_category(niche, topic)

    prompt = f"""
Create a short video production plan in {language}.
Niche: {niche}
Topic: {topic}
Keep scenes concise (up to 15s each). Provide simple English search keywords for stock/space media.

Return ONLY valid JSON:
{{
  "title": "",
  "hook": "",
  "media_search_query": "",
  "voiceover_script": "",
  "scenes": [
    {{
      "scene_number": 1,
      "duration": "5s",
      "visual_prompt": "",
      "narration": ""
    }}
  ]
}}
"""
    set_sync_state("PROCESSING", f"Plan: {topic[:30]}")
    last_err = None
    try:
        for attempt in range(2):
            try:
                push_live_event("MasterBrain", "Gemini", "SYNCING", f"প্ল্যান তৈরি হচ্ছে (চেষ্টা {attempt + 1})")
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
                plan = json.loads(response.text)
                query = plan.get("media_search_query") or topic
                push_live_event("Gemini", "MasterBrain", "OK", f"প্ল্যান তৈরি সম্পন্ন; কিওয়ার্ড: {query}")

                return jsonify({
                    "status": "SUCCESS",
                    "model": GEMINI_MODEL,
                    "category": category,
                    "plan": plan,
                    "media_sources": {
                        "nasa": neural_brain.search_nasa_library(query, media_type="video", limit=3),
                        "pixabay": neural_brain.search_pixabay_videos(query, per_page=3),
                        "vault_count": len(CUSTOM_ASSET_VAULT.get(category, [])),
                    },
                })
            except Exception as exc:
                last_err = str(exc)
                push_live_event("Gemini", "RetryLoop", "FALLBACK", f"চেষ্টা {attempt + 1} ব্যর্থ: {last_err}", is_fallback=True)
                time.sleep(1.5 * (attempt + 1))

        push_live_event("Gemini", "Client", "ERROR", last_err or "প্ল্যান তৈরি ব্যর্থ")
        return jsonify({"error": f"প্ল্যান তৈরি করতে সমস্যা হয়েছে: {last_err}"}), 503
    finally:
        set_sync_state("IDLE", None)


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    language = data.get("language") or "Bengali"
    rate = data.get("rate") or "-4%"
    pitch = data.get("pitch") or "+1Hz"
    result = generate_free_tts(text, language, rate=rate, pitch=pitch)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/build-clips", methods=["POST"])
def api_build_clips():
    data = request.get_json(silent=True) or {}
    clip_seconds = data.get("clip_seconds", 5)
    clip_count = data.get("clip_count", 3)
    label = data.get("label", "fast_clip")
    result = build_sequential_clips(clip_seconds=clip_seconds, clip_count=clip_count, label=label)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/download/<path:filename>", methods=["GET"])
def api_download_and_cleanup(filename):
    safe_name = os.path.basename(filename)
    filepath = os.path.join(OUTPUT_DIR, safe_name)
    if not os.path.exists(filepath):
        return jsonify({"error": "ফাইলটি পাওয়া যায়নি অথবা ইতিমধ্যে ডাউনলোড হয়ে মুছে গেছে।"}), 404

    response = send_file(filepath, as_attachment=True, download_name=safe_name)

    @response.call_on_close
    def _delete_after_download():
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                push_live_event("OutputsFolder", "Cleanup", "OK", f"ফাইল মুছে ফেলা হয়েছে: {safe_name}")
        except Exception:
            pass

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
