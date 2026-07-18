"""
AI Video Creator - Backend Server
Jalankan: python app.py
Akses: http://localhost:5000
"""
import os, json, uuid, re, subprocess, shutil, tempfile, time
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file, abort
import requests
from groq import Groq
from moviepy.editor import (VideoFileClip, AudioFileClip, concatenate_videoclips,
                            CompositeVideoClip, TextClip, ColorClip)
from moviepy.video.fx.all import fadein, fadeout
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB

BASE_DIR   = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Global config (diset dari UI)
CONFIG = {"groq_key": "", "pexels_key": ""}


# ============================================================
# HELPERS
# ============================================================
def err(msg, code=400):
    return jsonify({"ok": False, "error": str(msg)}), code

def ok(data=None):
    return jsonify({"ok": True, "data": data})


# ============================================================
# ROUTES: UI
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# ROUTES: TEST KONEKSI
# ============================================================
@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    data = request.json or {}
    groq   = (data.get("groq_key")   or "").strip()
    pexels = (data.get("pexels_key") or "").strip()
    if not groq or not pexels:
        return err("Groq API Key dan Pexels API Key wajib diisi")

    CONFIG["groq_key"]   = groq
    CONFIG["pexels_key"] = pexels

    # Test Groq
    groq_status = "offline"
    try:
        client = Groq(api_key=groq)
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":"ping"}],
            max_tokens=5
        )
        groq_status = "online"
    except Exception as e:
        groq_status = f"error: {e}"

    # Test Pexels
    pexels_status = "offline"
    try:
        r = requests.get("https://api.pexels.com/videos/search",
            headers={"Authorization": pexels},
            params={"query":"nature","per_page":1}, timeout=15)
        if r.status_code == 200:
            pexels_status = "online"
        else:
            pexels_status = f"error: HTTP {r.status_code}"
    except Exception as e:
        pexels_status = f"error: {e}"

    return ok({"groq": groq_status, "pexels": pexels_status})


# ============================================================
# ROUTES: TRANSCRIBE AUDIO
# ============================================================
@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    if not CONFIG.get("groq_key"):
        return err("Groq API Key belum diset. Klik Test Koneksi dulu.")
    if "audio" not in request.files:
        return err("File audio tidak ditemukan")

    f = request.files["audio"]
    ext = Path(f.filename).suffix or ".mp3"
    path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    f.save(path)

    try:
        client = Groq(api_key=CONFIG["groq_key"])
        with open(path, "rb") as fh:
            tr = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=fh,
                response_format="verbose_json",
                language="id"
            )
        text = tr.text or ""
        segs = []
        if hasattr(tr, "segments") and tr.segments:
            segs = [{"start": s.start, "end": s.end, "text": s.text} for s in tr.segments]
        return ok({"text": text, "segments": segs, "file": str(path)})
    except Exception as e:
        return err(f"Transkripsi gagal: {e}")


# ============================================================
# ROUTES: SEARCH VIDEO (PEXELS)
# ============================================================
@app.route("/api/search-videos", methods=["POST"])
def search_videos():
    if not CONFIG.get("pexels_key"):
        return err("Pexels API Key belum diset")
    data = request.json or {}
    query = (data.get("query") or "").strip()
    count = int(data.get("count") or 8)
    if not query:
        return err("Query pencarian kosong")

    try:
        r = requests.get("https://api.pexels.com/videos/search",
            headers={"Authorization": CONFIG["pexels_key"]},
            params={"query": query, "per_page": min(count, 40), "orientation":"portrait"},
            timeout=20)
        if r.status_code != 200:
            return err(f"Pexels error: HTTP {r.status_code}")
        j = r.json()
        videos = []
        for v in j.get("videos", []):
            # Pilih file SD/HD yang masuk akal
            files = sorted(v.get("video_files", []),
                           key=lambda x: x.get("width", 0))
            chosen = next((f for f in files if f.get("quality")=="hd" and f.get("height",0)>=720), files[-1] if files else None)
            if not chosen: continue
            videos.append({
                "id": v["id"],
                "url": chosen["link"],
                "width": chosen["width"],
                "height": chosen["height"],
                "duration": v.get("duration", 0),
                "image": v.get("image", ""),
                "user": v.get("user", {}).get("name", "")
            })
        return ok({"videos": videos, "total": j.get("total_results", 0)})
    except Exception as e:
        return err(f"Search gagal: {e}")


# ============================================================
# ROUTES: GENERATE SEO (GROQ)
# ============================================================
@app.route("/api/generate-seo", methods=["POST"])
def generate_seo():
    if not CONFIG.get("groq_key"):
        return err("Groq API Key belum diset")
    data = request.json or {}
    transcript = data.get("transcript", "")
    topic      = data.get("topic", "")
    platform   = data.get("platform", "tiktok")
    if not transcript and not topic:
        return err("Transkrip/topik kosong")

    prompt = f"""Kamu ahli SEO & content creator viral.
Buat 3 alternatif JUDUL (maks 70 char) yang mengandung HOOK kuat + emosional + clickbait sehat.
Buat DESKRIPSI (150-250 kata) yang SEO-friendly, mengandung keyword relevan, CTA, dan 10 hashtag viral.
Platform target: {platform}
Topik/transkrip: {topic or transcript}

Format JSON:
{{"titles":["...","...","..."],"description":"...","hashtags":["#..."]}}
HANYA output JSON, tanpa markdown."""

    try:
        client = Groq(api_key=CONFIG["groq_key"])
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.8, max_tokens=1200
        )
        txt = r.choices[0].message.content.strip()
        # bersihkan markdown code block
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.MULTILINE).strip()
        data_out = json.loads(txt)
        return ok(data_out)
    except Exception as e:
        return err(f"Generate SEO gagal: {e}")


# ============================================================
# ROUTES: RENDER VIDEO
# ============================================================
@app.route("/api/render", methods=["POST"])
def render_video():
    try:
        p = request.json or {}
        audio_path = p.get("audio_path")
        video_urls = p.get("videos", [])
        segments   = p.get("segments", [])   # caption segments
        aspect     = p.get("aspect", "9:16") # 16:9, 9:16, 1:1
        captions   = bool(p.get("captions", True))
        transitions= p.get("transitions", "fade")  # fade / cut
        title_text = (p.get("title") or "")[:80]

        if not audio_path or not Path(audio_path).exists():
            return err("Audio tidak ditemukan")
        if not video_urls:
            return err("Video_urls kosong")

        audio = AudioFileClip(audio_path)
        total_dur = audio.duration

        # ---- DOWNLOAD VIDEO ----
        tmp = Path(tempfile.mkdtemp())
        clips = []
        per_clip = total_dur / max(len(video_urls), 1)

        for i, url in enumerate(video_urls):
            out_mp4 = tmp / f"v{i}.mp4"
            # wget via python requests (streaming)
            try:
                with requests.get(url, stream=True, timeout=60) as rr:
                    rr.raise_for_status()
                    with open(out_mp4, "wb") as fh:
                        for ch in rr.iter_content(8192):
                            fh.write(ch)
            except Exception as e:
                print("dl fail:", e); continue

            try:
                vc = VideoFileClip(str(out_mp4))
                # potong sesuai alokasi durasi
                target = per_clip if i < len(video_urls)-1 else max(0.1, total_dur - sum(c.duration for c in clips))
                target = min(target, vc.duration)
                if target < 0.3: continue
                vc = vc.subclip(0, target)

                # resize & crop ke target aspect
                if aspect == "9:16":   tw, th = 1080, 1920
                elif aspect == "1:1":  tw, th = 1080, 1080
                else:                  tw, th = 1920, 1080

                vc = resize_and_crop(vc, tw, th)

                # transisi fade
                if transitions == "fade" and target > 1.0:
                    vc = vc.fx(fadein, 0.4).fx(fadeout, 0.4)
                clips.append(vc)
            except Exception as e:
                print("clip fail:", e); continue

        if not clips:
            return err("Tidak ada video yang berhasil diproses")

        final_video = concatenate_videoclips(clips, method="compose")
        # samakan durasi dengan audio
        if final_video.duration > total_dur:
            final_video = final_video.subclip(0, total_dur)
        final_video = final_video.set_audio(audio)

        # ---- CAPTION (burn-in) ----
        if captions and segments:
            txt_clips = []
            for s in segments:
                t = (s.get("text") or "").strip()
                if not t: continue
                try:
                    # TextClip butuh ImageMagick
                    tc = (TextClip(t, fontsize=58, color="white", font="Arial-Bold",
                                   stroke_color="black", stroke_width=3,
                                   size=(int(tw*0.9), None), method="caption")
                          .set_position(("center", 0.75), relative=True)
                          .set_start(s["start"]).set_end(min(s["end"], total_dur)))
                    txt_clips.append(tc)
                except Exception as e:
                    print("caption fail:", e)
            if txt_clips:
                final_video = CompositeVideoClip([final_video, *txt_clips], size=(tw, th))

        # ---- TITLE HOOK (3 detik pertama) ----
        if title_text:
            try:
                title_clip = (TextClip(title_text, fontsize=72, color="yellow",
                                       font="Arial-Bold", stroke_color="black",
                                       stroke_width=4, size=(int(tw*0.9), None), method="caption")
                              .set_position("center").set_duration(min(3.0, total_dur))
                              .fx(fadein, 0.3).fx(fadeout, 0.3))
                final_video = CompositeVideoClip([final_video, title_clip], size=(tw, th))
            except Exception as e:
                print("title fail:", e)

        # ---- RENDER ----
        out_name = f"result_{uuid.uuid4().hex[:8]}.mp4"
        out_path = OUTPUT_DIR / out_name
        final_video.write_videofile(
            str(out_path),
            fps=30, codec="libx264", audio_codec="aac",
            bitrate="5000k", preset="medium",
            logger=None, threads=4
        )

        # cleanup
        try: shutil.rmtree(tmp)
        except: pass
        for c in clips + [final_video, audio]:
            try: c.close()
            except: pass

        return ok({"file": out_name, "path": str(out_path), "size_mb": round(out_path.stat().st_size/1024/1024, 2)})
    except Exception as e:
        import traceback; traceback.print_exc()
        return err(f"Render gagal: {e}", 500)


def resize_and_crop(clip, tw, th):
    """Resize cover + center crop ke target aspect."""
    w, h = clip.size
    scale = max(tw/w, th/h)
    clip = clip.resize(scale)
    x1 = (clip.w - tw) // 2
    y1 = (clip.h - th) // 2
    return clip.crop(x1=x1, y1=y1, width=tw, height=th)


# ============================================================
# ROUTES: DOWNLOAD
# ============================================================
@app.route("/download/<name>")
def download(name):
    p = OUTPUT_DIR / secure_filename(name)
    if not p.exists(): abort(404)
    return send_file(p, as_attachment=True, download_name=name)


# ============================================================
if __name__ == "__main__":
    print("="*60)
    print(" AI VIDEO CREATOR - READY")
    print(" Buka browser: http://localhost:5000")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)