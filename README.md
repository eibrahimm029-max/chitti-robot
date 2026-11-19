# AI Video Production Studio (`chitti-robot`)

Flask, Gemini AI, MoviePy, Edge TTS এবং PixVerse / Pexels API ইন্টিগ্রেশনসহ একটি ওয়েব স্টুডিও।

## ফাইলসমূহ
- `main.py`: Flask ব্যাকএন্ড, Gemini স্ক্রিপ্ট ও স্টোরিবোর্ড, Pexels ও PixVerse হেল্পার, Edge TTS অডিও এবং MoviePy ক্লিপ হ্যান্ডলার
- `index.html`: Studio Dashboard ইন্টারফেস
- `requirements.txt`: প্রয়োজনীয় Python প্যাকেজ
- `render.yaml`: Render ডিপ্লয়মেন্ট কনফিগারেশন
- `README.md`: প্রজেক্ট গাইড

## Environment Variables (Render Dashboard)
বিদ্যমান কীগুলো (`GEMINI_API_KEY`, `YOUTUBE_API_KEY`, Firebase ও GitHub কী) অক্ষত রেখে প্রয়োজনে নিচেরগুলো যুক্ত করুন:
- `PIXVERSE_API_KEY`
- `PEXELS_API_KEY`
