"""Общие детали студии: пути, запуск FFmpeg, Chrome-слой для текста, сейф ключей.

Только стандартная библиотека Python + FFmpeg + Google Chrome. Ничего не скачивает.
Ключи читаются из .env внутри скрипта и никогда не печатаются.
"""
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
TMP = ROOT / "studio" / ".tmp"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

W, H, FPS = 1080, 1920, 30


def stop(msg):
    """Понятная ошибка для владелицы — без простыни технического текста."""
    sys.exit("✗ " + msg)


def need(tool):
    if tool == "chrome":
        if not Path(CHROME).exists():
            stop("нет Google Chrome — он рисует текст поверх видео. Поставим? (навык ustanovka)")
        return
    if not shutil.which(tool):
        stop(f"нет программы {tool}. Поставим? (навык ustanovka)")


def run(cmd, what="FFmpeg"):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-6:])
        stop(f"{what} не справился.\n{tail}")
    return r.stdout


def ff(*args):
    need("ffmpeg")
    return run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *map(str, args)])


def probe(path):
    need("ffprobe")
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
              "ffprobe")
    d = json.loads(out)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    fps = 0.0
    if v and v.get("avg_frame_rate", "0/0") != "0/0":
        n, m = v["avg_frame_rate"].split("/")
        fps = float(n) / float(m or 1)
    return {
        "dlit": float(d["format"].get("duration", 0) or 0),
        "w": int(v["width"]) if v else 0,
        "h": int(v["height"]) if v else 0,
        "fps": round(fps, 2),
        "zvuk": a is not None,
    }


def klyuch(name):
    """Ключ из сейфа .env. Не печатать! Возвращает '' если нет."""
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def tmpdir(name):
    d = TMP / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    return d


# ---------- Chrome-слой: HTML → прозрачная PNG ----------

def render_png(html, png, w=W, h=H):
    need("chrome")
    page = Path(str(png) + ".html")
    page.write_text(html, encoding="utf-8")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", "--default-background-color=00000000",
                    "--virtual-time-budget=1500", "--allow-file-access-from-files",
                    f"--window-size={w},{h}", f"--screenshot={png}", page.as_uri()],
                   capture_output=True)
    page.unlink(missing_ok=True)
    if not Path(png).exists():
        stop("Chrome не нарисовал кадр текста. Закрой лишние окна Chrome и попробуй ещё раз.")


def render_many(items, w=W, h=H):
    """items: [(html, png), ...] — рисуем параллельно по 4."""
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda it: render_png(it[0], it[1], w, h), items))


def sloj_video(states, total, out, w=W, h=H):
    """states: [(png или None, start, end), ...] → прозрачное видео-слой длиной total (qtrle .mov).
    Промежутки без текста заполняются пустым прозрачным кадром."""
    d = Path(out).parent
    blank = d / "_pusto.png"
    if not blank.exists():
        render_png("<html><body style='margin:0;background:transparent'></body></html>", blank, w, h)
    seq, t = [], 0.0
    for png, s, e in sorted(states, key=lambda x: x[1]):
        s, e = max(s, t), min(e, total)
        if s - t > 0.001:
            seq.append((blank, s - t))
        if e - s > 0.001:
            seq.append((png or blank, e - s))
            t = e
    if total - t > 0.001:
        seq.append((blank, total - t))
    lst = d / (Path(out).stem + ".txt")
    lines = []
    for png, dur in seq:
        lines.append(f"file '{png}'\nduration {dur:.4f}")
    lines.append(f"file '{seq[-1][0]}'")  # concat требует повтор последнего кадра
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ff("-f", "concat", "-safe", "0", "-i", lst, "-vf", f"fps={FPS},format=argb",
       "-c:v", "qtrle", "-t", f"{total:.3f}", out)
    return out


def css_text(st):
    """Общий CSS для крупного читаемого текста по стилю паспорта."""
    font = st.get("shrift", "Montserrat")
    stroke = st.get("obvodka_px", 6)
    sc = st.get("obvodka", "#000000")
    shadow = "0 6px 18px rgba(0,0,0,.55)" if st.get("ten", True) else "none"
    tt = "uppercase" if st.get("registr", "upper") == "upper" else "none"
    return (f"font-family:'{font}','Montserrat','Inter','Helvetica Neue',Arial,sans-serif;"
            f"font-weight:{st.get('ves', 900)};font-size:{st.get('razmer', 86)}px;line-height:1.05;"
            f"color:{st.get('cvet', '#FFFFFF')};text-transform:{tt};"
            f"-webkit-text-stroke:{stroke}px {sc};paint-order:stroke fill;text-shadow:{shadow};")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
