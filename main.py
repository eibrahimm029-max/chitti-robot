import asyncio
import base64
import hashlib
import json
import os
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
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")
MASTER_KEY = os.environ.get("MASTER_KEY") or os.environ.get("LINK_SECRET_KEY")

# যেকোনো সময় মডেল বদলাতে চাইলে শুধু এখানে (অথবা Render Env Var GEMINI_MODEL-এ) নাম বদলালেই হবে
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

VOICE_MAP = {
    "Bengali": "bn-BD-NabanitaNeural",
    "English": "en-US-AriaNeural",
    "Hindi": "hi-IN-SwaraNeural",
}


class MasterBrainNeuralEngine:
    """একাধিক API কী ও সিস্টেম রিসোর্স পর্যবেক্ষণ করে সিদ্ধান্ত নেয় ও ফলব্যাক সামলায়।"""

    def __init__(self):
        self.key_map = {
            "gemini": bool(GEMINI_API_KEY),
            "youtube": bool(YOUTUBE_API_KEY),
            "pixverse": bool(PIXVERSE_API_KEY),
            "pexels": bool(PEXELS_API_KEY),
            "master_lock": bool(MASTER_KEY),
        }

    def status_report(self) -> dict:
        active = [k for k, v in self.key_map.items() if v]
        missing = [k for k, v in self.key_map.items() if not v]
        return {
            "brain_mode": "NEURAL_ADAPTIVE",
            "model": GEMINI_MODEL,
            "active_capabilities": active,
            "pending_keys": missing,
        }

    def decide_production_strategy(self, format_type: str, duration_hint: str = "") -> dict:
        is_long = "long" in (format_type or "").lower() or "2 min" in (duration_hint or "").lower()
        target_seconds = 120 if is_long else 60
        clip_seconds = 15
        total_clips = target_seconds // clip_seconds
        return {
            "is_long": is_long,
            "target_seconds": target_seconds,
            "clip_seconds": clip_seconds,
            "total_clips": total_clips,
            "sequential_mode": True,
            "short_highlight_included": True,
        }

    def fetch_pexels_preview(self, query: str) -> dict:
        if not PEXELS_API_KEY:
            return {"configured": False, "videos": [], "note": "PEXELS_API_KEY সেট করা নেই"}
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": 2},
                timeout=12,
            )
            resp.raise_for_status()
            items = resp.json().get("videos", [])
            results = []
            for v in items:
                files = v.get("video_files", [])
                link = files[0].get("link") if files else None
                if link:
                    results.append({"id": v.get("id"), "encrypted_ref": encrypt_link(link)})
            return {"configured": True, "videos": results}
        except Exception as exc:
            return {"configured": True, "videos": [], "error": str(exc)}

    def prepare_pixverse_task(self, visual_prompt: str) -> dict:
        if not PIXVERSE_API_KEY:
            return {"configured": False, "status": "QUEUED_NO_KEY", "prompt": visual_prompt}
        return {"configured": True, "status": "READY", "prompt_locked": encrypt_link(visual_prompt)}


neural_brain = MasterBrainNeuralEngine()


def _get_fernet():
    if not FERNET_AVAILABLE or not MASTER_KEY:
        return None
    try:
        raw = MASTER_KEY.encode("utf-8")
        key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return Fernet(key)
    except Exception:
        return None


def encrypt_link(url: str) -> dict:
    """লিংক বা ডেটাকে Master Key দিয়ে হাবিজাবি এনক্রিপ্টেড/এনকোডেড স্ট্রিং ও শর্ট হ্যাশ ID-তে রূপান্তর করে।"""
    short_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    fernet = _get_fernet()
    if fernet:
        token = fernet.encrypt(url.encode("utf-8")).decode("utf-8")
        return {"id": short_hash, "encrypted": token, "mode": "fernet"}
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8")
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


async def _save_tts_audio(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)


def generate_free_tts(text: str, language: str = "Bengali") -> dict:
    if not EDGE_TTS_AVAILABLE:
        return {"ok": False, "error": "edge-tts ইনস্টল করা নেই।"}
    if not text.strip():
        return {"ok": False, "error": "ভয়েসের জন্য কোনো টেক্সট দেওয়া হয়নি।"}

    voice = VOICE_MAP.get(language, "bn-BD-NabanitaNeural")
    filename = f"tts_{int(time.time())}.mp3"
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        asyncio.run(_save_tts_audio(text.strip(), voice, filepath))
        return {
            "ok": True,
            "voice": voice,
            "file": f"/{OUTPUT_DIR}/{filename}",
            "download_url": f"/api/download/{filename}",
        }
    except Exception as exc:
        return {"ok": False, "error": f"TTS তৈরি করতে সমস্যা হয়েছে: {str(exc)}"}


def build_sequential_clips(clip_seconds: int = 15, clip_count: int = 4, label: str = "short") -> dict:
    """একটির পর একটি ছোট ক্লিপ তৈরি করে outputs ফোল্ডারে জমা রাখে এবং জোড়া লাগায়।"""
    if not MOVIEPY_AVAILABLE:
        return {"ok": False, "error": "MoviePy ব্যবহারযোগ্য নয়।"}

    safe_seconds = max(5, min(int(clip_seconds), 20))
    safe_count = max(1, min(int(clip_count), 8))
    created_files = []
    part_paths = []
    palette = [
        (20, 30, 55),
        (45, 25, 65),
        (18, 52, 58),
        (60, 32, 38),
    ]

    try:
        for idx in range(safe_count):
            color = palette[idx % len(palette)]
            clip = ColorClip(size=(640, 360), color=color, duration=safe_seconds)
            trimmed = clip.subclipped(0, safe_seconds) if hasattr(clip, "subclipped") else clip.subclip(0, safe_seconds)
            fname = f"{label}_part_{idx + 1}_{int(time.time())}.mp4"
            fpath = os.path.join(OUTPUT_DIR, fname)
            trimmed.write_videofile(fpath, fps=24, codec="libx264", audio=False, logger=None)
            trimmed.close()
            clip.close()
            part_paths.append(fpath)
            created_files.append(f"/{OUTPUT_DIR}/{fname}")

        merged_name = f"{label}_merged_{int(time.time())}.mp4"
        merged_path = os.path.join(OUTPUT_DIR, merged_name)
        loaded = [VideoFileClip(p) for p in part_paths]
        final_clip = concatenate_videoclips(loaded)
        final_clip.write_videofile(merged_path, fps=24, codec="libx264", audio=False, logger=None)
        final_clip.close()
        for c in loaded:
            c.close()

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
        return {"ok": False, "error": f"ক্লিপ তৈরিতে সমস্যা হয়েছে: {str(exc)}"}


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
        "pexels_configured": bool(PEXELS_API_KEY),
        "secret_key_configured": bool(MASTER_KEY),
        "edge_tts_available": EDGE_TTS_AVAILABLE,
        "moviepy_available": MOVIEPY_AVAILABLE,
        "neural_brain": neural_brain.status_report(),
    })


@app.route("/api/encrypt-link", methods=["POST"])
def api_encrypt_link():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "লিংক দেওয়া হয়নি।"}), 400
    return jsonify({"ok": True, "record": encrypt_link(url)})


@app.route("/api/generate-plan", methods=["POST"])
def generate_plan():
    if not client:
        return jsonify({"error": "GEMINI_API_KEY সেট করা নেই।"}), 500

    data = request.get_json(silent=True) or {}
    niche = (data.get("niche") or "Tech & AI").strip()
    topic = (data.get("topic") or "বাংলায় নতুন প্রযুক্তি").strip()
    language = (data.get("language") or "Bengali").strip()
    format_type = (data.get("format_type") or "YouTube Shorts").strip()
    strategy = neural_brain.decide_production_strategy(format_type, data.get("duration") or "")
    target_seconds = strategy["target_seconds"]
    clip_seconds = strategy["clip_seconds"]
    total_clips = strategy["total_clips"]
    visual_style = (data.get("visual_style") or "Cinematic Dark AI").strip()

    prompt = f"""
Create a video production plan in {language} (Bengali title, hook, narration, and scene text).
Niche: {niche}
Topic: {topic}
Format: {"Long Video (2 minutes = 8 clips x 15s)" if strategy["is_long"] else "Short Video (1 minute = 4 clips x 15s)"}
Visual Style: {visual_style}
Create {total_clips} sequential scenes of {clip_seconds} seconds each, plus 1 catchy short clip highlight for Shorts.

Return ONLY valid JSON:
{{
  "title": "",
  "hook": "",
  "short_highlight_title": "",
  "voiceover_script": "",
  "thumbnail_prompt": "",
  "scenes": [
    {{
      "scene_number": 1,
      "duration": "15s",
      "visual_prompt": "",
      "narration": "",
      "on_screen_text": ""
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        plan = json.loads(response.text)
        return jsonify({
            "status": "SUCCESS",
            "model": GEMINI_MODEL,
            "target_seconds": target_seconds,
            "clip_seconds": clip_seconds,
            "total_clips": total_clips,
            "plan": plan,
            "neural_sources": {
                "pexels": neural_brain.fetch_pexels_preview(topic),
                "pixverse": neural_brain.prepare_pixverse_task(plan.get("thumbnail_prompt") or topic),
            },
        })
    except Exception as exc:
        return jsonify({"error": f"প্ল্যান তৈরি করতে সমস্যা হয়েছে: {str(exc)}"}), 500


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    language = data.get("language") or "Bengali"
    result = generate_free_tts(text, language)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/build-clips", methods=["POST"])
def api_build_clips():
    data = request.get_json(silent=True) or {}
    clip_seconds = data.get("clip_seconds", 15)
    clip_count = data.get("clip_count", 4)
    label = data.get("label", "short")
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
        except Exception:
            pass

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
