import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
import shutil
import subprocess
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
    from moviepy import AudioFileClip, ColorClip, CompositeAudioClip, VideoFileClip, concatenate_videoclips
    MOVIEPY_AVAILABLE = True
except Exception:
    try:
        from moviepy.editor import AudioFileClip, ColorClip, CompositeAudioClip, VideoFileClip, concatenate_videoclips
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
    "Bengali Female": "bn-BD-NabanitaNeural",
    "Bengali Male": "bn-BD-PradeepNeural",
    "English": "en-US-AriaNeural",
    "Hindi": "hi-IN-SwaraNeural",
}

MEDIA_VAULT_CACHE = {}
CUSTOM_ASSET_VAULT = {
    "islamic_nasheed": [],
    "science_space": [],
    "tech_cinematic": [],
}
LATEST_STOCK_LOCKED_URLS = []

STATE_LOCK = threading.Lock()
LIVE_MONITOR = {
    "sync_state": "IDLE",  # IDLE বা PROCESSING
    "current_stage": "IDLE",
    "stage_label_bn": "প্রস্তুত (IDLE)",
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


def set_live_stage(stage_code: str, stage_label_bn: str, task_name: str | None = None, count_request: bool = False):
    with STATE_LOCK:
        LIVE_MONITOR["current_stage"] = stage_code
        LIVE_MONITOR["stage_label_bn"] = stage_label_bn
        LIVE_MONITOR["sync_state"] = "IDLE" if stage_code == "IDLE" else "PROCESSING"
        LIVE_MONITOR["active_task"] = task_name
        LIVE_MONITOR["last_sync_at"] = _now_iso()
        if count_request:
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
                "fallback": "429 কোটা হলে অপেক্ষার বার্তা ও অস্থায়ী ত্রুটিতে রিট্রাই",
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
                "name": "Edge-TTS & Voice Refiner",
                "online": EDGE_TTS_AVAILABLE,
                "connects_to": ["FFmpegRefiner", "OutputsFolder"],
                "capability": "টেক্সট ছাঁটাই, ছেলে/মেয়ে ভয়েস তৈরি ও কণ্ঠ স্পষ্ট/সমান করা",
                "fallback": "ffmpeg না থাকলে নিরাপদ অডিও আউটপুট ও ত্রুটি বার্তা",
            },
            {
                "id": "moviepy",
                "name": "MoviePy Clip Sequencer",
                "online": MOVIEPY_AVAILABLE,
                "connects_to": ["StockVault", "OutputsFolder"],
                "capability": "১–১০s ধাপে শর্ট/লং সাইজ ক্লিপ তৈরি, মার্জ ও হালকা মিউজিক ব্লেন্ড",
                "fallback": "সর্বোচ্চ ১০s সীমা, ColorClip ফলব্যাক ও ডাউনলোডের পর ফাইল মুছে ফেলা",
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


def _clean_tts_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _refine_audio_with_ffmpeg(raw_path: str, final_path: str) -> bool:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return False
    audio_filter = "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        raw_path,
        "-af",
        audio_filter,
        "-ar",
        "44100",
        "-ac",
        "1",
        "-b:a",
        "128k",
        final_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return proc.returncode == 0 and os.path.exists(final_path) and os.path.getsize(final_path) > 0
    except Exception:
        return False


async def _save_tts_audio(text: str, voice: str, out_path: str, rate: str = "-4%", pitch: str = "+1Hz") -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def generate_free_tts(text: str, language: str = "Bengali Female", rate: str = "-4%", pitch: str = "+1Hz") -> dict:
    if not EDGE_TTS_AVAILABLE:
        push_live_event("EdgeTTS", "Client", "ERROR", "edge-tts ইনস্টল নেই")
        return {"ok": False, "error": "edge-tts ইনস্টল করা নেই।"}

    cleaned_text = _clean_tts_text(text)
    if not cleaned_text:
        return {"ok": False, "error": "ভয়েসের জন্য কোনো টেক্সট দেওয়া হয়নি।"}

    voice = VOICE_MAP.get(language, "bn-BD-NabanitaNeural")
    ts = int(time.time())
    raw_filename = f"tts_raw_{ts}.mp3"
    final_filename = f"tts_clean_{ts}.mp3"
    raw_path = os.path.join(OUTPUT_DIR, raw_filename)
    final_path = os.path.join(OUTPUT_DIR, final_filename)

    set_live_stage("TTS_SYNTHESIS", "ধাপ ১/২: টেক্সট ছাঁটাই ও ভয়েস তৈরি হচ্ছে...", f"Edge-TTS ({voice})", count_request=True)
    try:
        push_live_event("MasterBrain", "EdgeTTS", "SYNCING", f"ভয়েস তৈরি হচ্ছে ({voice})")
        asyncio.run(_save_tts_audio(cleaned_text, voice, raw_path, rate=rate, pitch=pitch))
        if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            push_live_event("EdgeTTS", "Client", "ERROR", "খালি অডিও রেসপন্স এসেছে")
            return {"ok": False, "error": "অডিও তৈরি হয়নি; ভাষা ও টেক্সট যাচাই করুন।"}

        set_live_stage("TTS_REFINING", "ধাপ ২/২: কণ্ঠ স্পষ্ট ও সমান করা হচ্ছে...", "Audio Refiner", count_request=False)
        refined_ok = _refine_audio_with_ffmpeg(raw_path, final_path)

        if refined_ok:
            if os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                except Exception:
                    pass
            push_live_event("AudioRefiner", "OutputsFolder", "OK", f"পরিশোধিত অডিও প্রস্তুত: {final_filename}")
            return {
                "ok": True,
                "voice": voice,
                "rate": rate,
                "pitch": pitch,
                "refined": True,
                "file": f"/{OUTPUT_DIR}/{final_filename}",
                "download_url": f"/api/download/{final_filename}",
            }

        fallback_filename = f"tts_{ts}.mp3"
        fallback_path = os.path.join(OUTPUT_DIR, fallback_filename)
        os.replace(raw_path, fallback_path)
        push_live_event("AudioRefiner", "Fallback", "FALLBACK", f"ফিল্টার ছাড়াই অডিও প্রস্তুত: {fallback_filename}", is_fallback=True)
        return {
            "ok": True,
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "refined": False,
            "file": f"/{OUTPUT_DIR}/{fallback_filename}",
            "download_url": f"/api/download/{fallback_filename}",
        }
    except Exception as exc:
        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except Exception:
                pass
        push_live_event("EdgeTTS", "Client", "ERROR", str(exc))
        return {"ok": False, "error": f"TTS তৈরি করতে সমস্যা হয়েছে: {str(exc)}"}
    finally:
        set_live_stage("IDLE", "প্রস্তুত (IDLE)", None, count_request=False)


def _resolve_video_size(format_type: str | None) -> tuple[int, int]:
    fmt = (format_type or "").lower()
    if "short" in fmt or "9:16" in fmt or "reel" in fmt:
        return (360, 640)
    return (640, 360)


def _collect_candidate_locked_urls(category: str | None = None) -> list[dict]:
    candidates = []
    for item in reversed(LATEST_STOCK_LOCKED_URLS):
        if isinstance(item, dict) and item.get("encrypted"):
            candidates.append(item)

    if category and category in CUSTOM_ASSET_VAULT:
        for item in reversed(CUSTOM_ASSET_VAULT[category]):
            if isinstance(item, dict) and item.get("encrypted"):
                candidates.append(item)
    else:
        for cat_items in CUSTOM_ASSET_VAULT.values():
            for item in reversed(cat_items):
                if isinstance(item, dict) and item.get("encrypted"):
                    candidates.append(item)

    for cache_val in reversed(list(MEDIA_VAULT_CACHE.values())):
        if isinstance(cache_val, list):
            for entry in cache_val:
                if isinstance(entry, dict):
                    locked = entry.get("locked_url") or entry.get("locked_preview")
                    if isinstance(locked, dict) and locked.get("encrypted"):
                        candidates.append(locked)

    seen_ids = set()
    unique = []
    for c in candidates:
        cid = c.get("id") or c.get("encrypted")[:20]
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(c)
    return unique


def _download_stock_clip(locked_obj: dict, dest_path: str) -> bool:
    token = locked_obj.get("encrypted")
    mode = locked_obj.get("mode") or "fernet"
    url = decrypt_link(token, mode=mode)
    if not url or not url.startswith(("http://", "https://")):
        return False

    try:
        push_live_event("StockVault", "Downloader", "SYNCING", f"ক্লিপ ডাউনলোড হচ্ছে ({locked_obj.get('id', 'link')})")
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            content_type = (r.headers.get("content-type") or "").lower()
            if "text/html" in content_type or "image/" in content_type:
                return False

            max_bytes = 25 * 1024 * 1024
            written = 0
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        written += len(chunk)
                        if written > max_bytes:
                            break
                        f.write(chunk)

        ok = os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024
        if ok:
            push_live_event("Downloader", "MoviePy", "OK", "স্টক ক্লিপ ডাউনলোড সম্পন্ন")
        return ok
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return False


def _trim_and_resize_clip(src_video_path: str, target_seconds: int, size: tuple[int, int]):
    clip = VideoFileClip(src_video_path)
    try:
        dur = float(clip.duration or 0)
        if dur <= 0:
            raise ValueError("ভিডিওর দৈর্ঘ্য পাওয়া যায়নি")
        end_t = min(float(target_seconds), dur)
        sub = clip.subclipped(0.0, end_t) if hasattr(clip, "subclipped") else clip.subclip(0.0, end_t)
        if hasattr(sub, "resized"):
            sub = sub.resized(size)
        elif hasattr(sub, "resize"):
            sub = sub.resize(size)
        return sub, clip
    except Exception:
        clip.close()
        raise


def _render_clip_sequence(
    durations: list[int],
    label: str = "fast_clip",
    bg_music_path: str | None = None,
    category: str | None = None,
    format_type: str | None = None,
) -> dict:
    if not MOVIEPY_AVAILABLE:
        push_live_event("MoviePy", "Client", "ERROR", "MoviePy ব্যবহারযোগ্য নয়")
        return {"ok": False, "error": "MoviePy ব্যবহারযোগ্য নয়।"}

    safe_steps = [max(1, min(int(d), 10)) for d in durations[:6]]
    target_size = _resolve_video_size(format_type)
    created_files = []
    part_paths = []
    temp_downloads = []
    palette = [(20, 30, 55), (45, 25, 65), (18, 52, 58), (60, 32, 38), (28, 48, 42), (52, 40, 24)]
    candidates = _collect_candidate_locked_urls(category=category)

    set_live_stage("CLIP_RENDERING", f"ক্লিপ তৈরি হচ্ছে ({safe_steps}s · {target_size[0]}x{target_size[1]})...", f"MoviePy {label}", count_request=True)
    try:
        for idx, sec in enumerate(safe_steps):
            fname = f"{label}_part_{idx + 1}_{sec}s_{int(time.time())}.mp4"
            fpath = os.path.join(OUTPUT_DIR, fname)
            used_stock = False

            for c_idx in range(len(candidates)):
                cand = candidates[(idx + c_idx) % len(candidates)]
                tmp_src = os.path.join(OUTPUT_DIR, f"tmp_src_{idx}_{c_idx}_{int(time.time())}.mp4")
                if _download_stock_clip(cand, tmp_src):
                    temp_downloads.append(tmp_src)
                    source_clip = None
                    sub_clip = None
                    try:
                        sub_clip, source_clip = _trim_and_resize_clip(tmp_src, sec, target_size)
                        sub_clip.write_videofile(
                            fpath,
                            fps=20,
                            codec="libx264",
                            preset="ultrafast",
                            audio=False,
                            logger=None,
                        )
                        used_stock = True
                        push_live_event("StockVault", "MoviePy", "OK", f"আসল স্টক ক্লিপ ({sec}s) তৈরি হয়েছে")
                        break
                    except Exception as clip_exc:
                        push_live_event("StockClip", "Fallback", "FALLBACK", f"ক্লিপ কাটায় ত্রুটি: {str(clip_exc)}", is_fallback=True)
                    finally:
                        if sub_clip:
                            try:
                                sub_clip.close()
                            except Exception:
                                pass
                        if source_clip:
                            try:
                                source_clip.close()
                            except Exception:
                                pass

            if not used_stock:
                color = palette[idx % len(palette)]
                clip = ColorClip(size=target_size, color=color, duration=sec)
                trimmed = clip.subclipped(0, sec) if hasattr(clip, "subclipped") else clip.subclip(0, sec)
                trimmed.write_videofile(fpath, fps=20, codec="libx264", preset="ultrafast", audio=False, logger=None)
                trimmed.close()
                clip.close()
                push_live_event("MoviePy", "ColorFallback", "FALLBACK", f"স্টক না থাকায় {sec}s ফলব্যাক ক্লিপ তৈরি হয়েছে", is_fallback=True)

            part_paths.append(fpath)
            created_files.append({"seconds": sec, "stock_used": used_stock, "file": f"/{OUTPUT_DIR}/{fname}"})

        set_live_stage("VIDEO_MERGING", "ক্লিপগুলো যুক্ত করে এডিটিং চলছে...", "Merge Clips", count_request=False)
        merged_name = f"{label}_merged_{int(time.time())}.mp4"
        merged_path = os.path.join(OUTPUT_DIR, merged_name)
        loaded = [VideoFileClip(p) for p in part_paths]
        final_clip = concatenate_videoclips(loaded)

        music_clip = None
        if bg_music_path and os.path.exists(bg_music_path):
            try:
                raw_audio = AudioFileClip(bg_music_path)
                target_dur = final_clip.duration
                if raw_audio.duration < target_dur and hasattr(raw_audio, "loop"):
                    raw_audio = raw_audio.loop(duration=target_dur)
                music_clip = raw_audio.subclipped(0, target_dur) if hasattr(raw_audio, "subclipped") else raw_audio.subclip(0, target_dur)
                if hasattr(music_clip, "with_volume_scaled"):
                    music_clip = music_clip.with_volume_scaled(0.15)
                elif hasattr(music_clip, "volumex"):
                    music_clip = music_clip.volumex(0.15)
                audio_mix = CompositeAudioClip([music_clip])
                final_clip = final_clip.with_audio(audio_mix) if hasattr(final_clip, "with_audio") else final_clip.set_audio(audio_mix)
            except Exception:
                pass

        final_clip.write_videofile(
            merged_path,
            fps=20,
            codec="libx264",
            preset="ultrafast",
            audio=bool(music_clip),
            logger=None,
        )
        if music_clip:
            music_clip.close()
        final_clip.close()
        for c in loaded:
            c.close()

        push_live_event("MoviePy", "OutputsFolder", "OK", f"চূড়ান্ত ভিডিও প্রস্তুত: {merged_name}")
        return {
            "ok": True,
            "mode": label,
            "size": f"{target_size[0]}x{target_size[1]}",
            "clip_seconds": safe_steps[0] if len(safe_steps) == 1 else safe_steps,
            "steps_seconds": safe_steps,
            "created_count": len(created_files),
            "clips": created_files,
            "merged_file": f"/{OUTPUT_DIR}/{merged_name}",
            "download_url": f"/api/download/{merged_name}",
        }
    except Exception as exc:
        push_live_event("MoviePy", "Client", "ERROR", str(exc))
        return {"ok": False, "error": f"ক্লিপ তৈরিতে সমস্যা হয়েছে: {str(exc)}"}
    finally:
        for tmp_f in temp_downloads:
            if os.path.exists(tmp_f):
                try:
                    os.remove(tmp_f)
                except Exception:
                    pass
        set_live_stage("IDLE", "প্রস্তুত (IDLE)", None, count_request=False)


def build_sequential_clips(clip_seconds: int = 5, clip_count: int = 3, label: str = "fast_clip", format_type: str | None = None) -> dict:
    safe_seconds = max(1, min(int(clip_seconds), 10))
    safe_count = max(1, min(int(clip_count), 6))
    return _render_clip_sequence([safe_seconds] * safe_count, label=label, format_type=format_type)


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
        "current_stage": LIVE_MONITOR["current_stage"],
        "stage_label_bn": LIVE_MONITOR["stage_label_bn"],
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
    LATEST_STOCK_LOCKED_URLS.append(record)
    LATEST_STOCK_LOCKED_URLS[:] = LATEST_STOCK_LOCKED_URLS[-20:]
    return jsonify({"ok": True, "category": category, "record": record})


@app.route("/api/generate-plan", methods=["POST"])
def generate_plan():
    if not client:
        push_live_event("MasterBrain", "Gemini", "ERROR", "GEMINI_API_KEY সেট করা নেই")
        return jsonify({"error": "GEMINI_API_KEY সেট করা নেই।"}), 500

    data = request.get_json(silent=True) or {}
    niche = (data.get("niche") or "Tech & AI").strip()
    topic = (data.get("topic") or "বিজ্ঞান ও প্রযুক্তি").strip()
    language = (data.get("language") or "Bengali Female").strip()
    format_type = (data.get("format_type") or "Short Video (9:16)").strip()
    duration = (data.get("duration") or "5 seconds").strip()
    visual_style = (data.get("visual_style") or "Cinematic Dark AI").strip()
    category = neural_brain.route_category(niche, topic)

    prompt = f"""
Create a short video production plan in {language}.
Niche: {niche}
Topic: {topic}
Format: {format_type}
Duration: {duration}
Visual Style: {visual_style}
Keep scenes concise (1s to 10s each). Provide simple English search keywords for stock/space media.

Return ONLY valid JSON:
{{
  "title": "",
  "hook": "",
  "media_search_query": "",
  "thumbnail_prompt": "",
  "voiceover_script": "",
  "scenes": [
    {{
      "scene_number": 1,
      "duration": "5s",
      "visual_prompt": "",
      "narration": "",
      "on_screen_text": ""
    }}
  ]
}}
"""
    set_live_stage("PLAN_GENERATING", "আইডিয়া ও সিন প্ল্যান তৈরি হচ্ছে...", f"Plan: {topic[:30]}", count_request=True)
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

                nasa_items = neural_brain.search_nasa_library(query, media_type="video", limit=3)
                pixabay_items = neural_brain.search_pixabay_videos(query, per_page=3)

                for p_item in pixabay_items:
                    if isinstance(p_item.get("locked_url"), dict):
                        LATEST_STOCK_LOCKED_URLS.append(p_item["locked_url"])
                for n_item in nasa_items:
                    if isinstance(n_item.get("locked_preview"), dict):
                        LATEST_STOCK_LOCKED_URLS.append(n_item["locked_preview"])
                LATEST_STOCK_LOCKED_URLS[:] = LATEST_STOCK_LOCKED_URLS[-20:]

                return jsonify({
                    "status": "SUCCESS",
                    "model": GEMINI_MODEL,
                    "category": category,
                    "format_type": format_type,
                    "plan": plan,
                    "media_sources": {
                        "nasa": nasa_items,
                        "pixabay": pixabay_items,
                        "vault_count": len(CUSTOM_ASSET_VAULT.get(category, [])),
                    },
                })
            except Exception as exc:
                err_str = str(exc)
                last_err = err_str
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    push_live_event("Gemini", "Client", "ERROR", "মিনিটের কোটা (RPM) শেষ; প্রায় ৪৫-৫০ সেকেন্ড অপেক্ষা করুন")
                    return jsonify({
                        "error": "Gemini Free Tier-এর প্রতি মিনিটের রিকোয়েস্ট সীমা শেষ হয়েছে। অনুগ্রহ করে প্রায় ৪৫–৫০ সেকেন্ড অপেক্ষা করে আবার চেষ্টা করুন।"
                    }), 429
                push_live_event("Gemini", "RetryLoop", "FALLBACK", f"চেষ্টা {attempt + 1} ব্যর্থ: {last_err}", is_fallback=True)
                time.sleep(1.5 * (attempt + 1))

        push_live_event("Gemini", "Client", "ERROR", last_err or "প্ল্যান তৈরি ব্যর্থ")
        return jsonify({"error": f"প্ল্যান তৈরি করতে সমস্যা হয়েছে: {last_err}"}), 503
    finally:
        set_live_stage("IDLE", "প্রস্তুত (IDLE)", None, count_request=False)


@app.route("/api/tts", methods=["POST"])
def api_tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or ""
    language = data.get("language") or "Bengali Female"
    rate = data.get("rate") or "-4%"
    pitch = data.get("pitch") or "+1Hz"
    result = generate_free_tts(text, language, rate=rate, pitch=pitch)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/build-clips", methods=["POST"])
def api_build_clips():
    data = request.get_json(silent=True) or {}
    clip_seconds = data.get("clip_seconds", 5)
    clip_count = data.get("clip_count", 1)
    label = data.get("label") or "fast_clip"
    format_type = data.get("format_type")
    result = build_sequential_clips(clip_seconds=clip_seconds, clip_count=clip_count, label=label, format_type=format_type)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/build-steps", methods=["POST"])
def api_build_steps():
    data = request.get_json(silent=True) or {}
    durations = data.get("durations") or [1, 2, 3, 4, 5]
    if not isinstance(durations, list) or not durations:
        durations = [1, 2, 3, 4, 5]
    label = data.get("label") or "step_clip"
    bg_music_path = data.get("bg_music_path")
    format_type = data.get("format_type")
    result = _render_clip_sequence(durations=durations, label=label, bg_music_path=bg_music_path, format_type=format_type)
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
