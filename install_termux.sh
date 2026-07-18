#!/data/data/com.termux/files/usr/bin/bash
# AI Video Creator - Installer untuk Termux
set -e
echo "🚀 Installing AI Video Creator di Termux..."

# Update & install dep dasar
pkg update -y && pkg upgrade -y
pkg install -y python ffmpeg imagemagick wget curl git

# Konfigurasi ImageMagick untuk MoviePy TextClip
MAGICK_POL="/data/data/com.termux/files/usr/etc/ImageMagick-7/policy.xml"
if [ -f "$MAGICK_POL" ]; then
  sed -i 's/rights="none" pattern="@*"/rights="read|write" pattern="@*"/g' "$MAGICK_POL" 2>/dev/null || true
fi

# Buat venv
cd "$HOME"
[ ! -d "ai-video-creator" ] && mkdir ai-video-creator
cd ai-video-creator

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install flask==3.0.3 requests==2.32.3 groq==0.9.0 moviepy==1.0.3 werkzeug==3.0.3 Pillow==10.4.0 decorator==4.4.2

# Buat struktur folder
mkdir -p templates uploads outputs

echo "✅ Install selesai!"
echo ""
echo "📝 LANGKAH SELANJUTNYA:"
echo "1. Salin file app.py ke folder ini"
echo "2. Salin folder templates/index.html"
echo "3. Jalankan: source venv/bin/activate && python app.py"
echo "4. Buka browser: http://localhost:5000"