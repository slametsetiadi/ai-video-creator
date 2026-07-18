# 🎬 AI Video Creator

Aplikasi web AI untuk membuat video viral otomatis dari audio.

## ✨ Fitur
- Upload audio → auto transkrip (Groq Whisper)
- Auto cari video stock bebas copyright (Pexels)
- Auto edit: gabung clip + transisi fade
- Auto caption (burn-in subtitle)
- Auto judul & deskripsi SEO + hashtag viral (Groq LLM)
- Export multi-aspect: 9:16, 16:9, 1:1
- Test koneksi API Key
- Step-by-step wizard UI
- Download hasil final

## 📱 Install di Termux (Android)

### 1. Install Termux
Download dari F-Droid: https://f-droid.org/packages/com.termux/

### 2. Jalankan installer
```bash
pkg install wget -y
wget https://raw.githubusercontent.com/.../install_termux.sh
chmod +x install_termux.sh
./install_termux.sh
