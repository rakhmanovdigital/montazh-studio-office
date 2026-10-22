#!/bin/bash
# Проверка студии: что стоит, а чего нет. Только смотрит — ничего не ставит и не меняет.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1

ok()  { echo "✅ $1"; }
no()  { echo "☐  $1 — $2"; }

xcode-select -p >/dev/null 2>&1 && ok "Инструменты Apple" || no "Инструменты Apple" "нужны первыми"
command -v brew >/dev/null 2>&1 && ok "Homebrew" || no "Homebrew" "магазин программ"
command -v ffmpeg >/dev/null 2>&1 && ok "FFmpeg ($(ffmpeg -version | head -1 | awk '{print $3}'))" || no "FFmpeg" "монтажный стол"
command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1 && ok "Python ($(python3 --version 2>&1 | awk '{print $2}'))" || no "Python" "придёт с инструментами Apple"
[ -d "/Applications/Google Chrome.app" ] && ok "Google Chrome" || no "Google Chrome" "рисует текст поверх видео"

fonts=$(ls ~/Library/Fonts /Library/Fonts 2>/dev/null | grep -ciE "montserrat|inter|bebas|unbounded")
[ "${fonts:-0}" -gt 0 ] && ok "Шрифты для титров" || no "Шрифты" "жирные шрифты для субтитров"
command -v yt-dlp >/dev/null 2>&1 && ok "yt-dlp" || no "yt-dlp" "скачивает ролики по ссылке"
command -v gcloud >/dev/null 2>&1 && ok "Google Cloud (по желанию)" || echo "⏸  Google Cloud — по желанию, потом"

if [ -f .env ]; then
  grep -qE '^DEEPGRAM_API_KEY=.{20,}' .env && ok "Ключ Deepgram в сейфе" || no "Ключ Deepgram" "сейф есть, ключа нет"
else
  no "Сейф .env" "ещё не создан (ступень 3)"
fi
echo "ℹ️  Расширение Claude для Chrome и запасной Инстаграм — проверяем глазами (значок в Chrome)."
