"""Gemini смотрит ролик целиком (картинка + звук) — разбор стиля монтажа «глазами человека». ПО ЖЕЛАНИЮ.

Нужно: Google Cloud ($300 подарочных) + `gcloud auth login` + включённый Vertex AI API.
ВНИМАНИЕ: ролик уходит в Google. Перед первым разом — объяснить владелице и получить «да».
Кнопку Upgrade в Google Cloud не нажимаем никогда.

  python3 -I scripts/gemini-smotret.py <ролик.mp4> --out <разбор.md> [--model gemini-2.5-pro]
"""
import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402

PROMPT = """Ты — опытный монтажёр коротких вертикальных видео. Смотри И слушай ролик. Пиши по-русски.
Задача: описать СТИЛЬ МОНТАЖА так, чтобы другой монтажёр повторил его на другом исходнике.
1. ТЕМП: как часто склейки, ускоряется ли к концу, что в первые 3 секунды (хук).
2. ПЕРЕХОДЫ: какие именно (резкая склейка, растворение, шторка, зум, вспышка) и где.
3. ДВИЖЕНИЕ: зумы-наезды, тряска, плавные наезды — на каких моментах.
4. СУБТИТРЫ: шрифт (на что похож), толщина, цвет, обводка/тень, плашка, сколько слов на экране,
   где на экране, как появляются слова (подсветка, всплытие, по одному).
5. ГРАФИКА: плашки, стикеры, счётчики, стрелки, эмодзи — что и когда.
6. ЗВУК: музыка (жанр, темп), режут ли в бит, звуковые эффекты (вжух, щелчки), голос.
7. ЦВЕТ: тёплый/холодный, контраст, насыщенность.
Таймкоды [мм:сс]. Ничего не выдумывай: не видно — так и пиши."""


def gcloud(*args):
    try:
        r = subprocess.run(["gcloud", *args], capture_output=True, text=True)
    except FileNotFoundError:
        S.stop("Google Cloud не установлен — это опция «по желанию» (навык ustanovka).")
    if r.returncode != 0:
        S.stop("gcloud: " + ((r.stderr.strip().splitlines() or ["ошибка"])[-1]))
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemini-2.5-pro")
    a = ap.parse_args()
    src = Path(a.video) if Path(a.video).is_absolute() else S.ROOT / a.video
    if not src.exists():
        S.stop(f"не нашёл {a.video}")
    project = gcloud("config", "get-value", "project")
    token = gcloud("auth", "print-access-token")
    work = S.tmpdir("gemini")
    small = work / "maly.mp4"  # ужимаем, чтобы влезть в один запрос (~до 15 МБ)
    S.ff("-i", src, "-t", "120", "-vf", "scale=-2:640,fps=24", "-c:v", "libx264", "-crf", "30", "-preset", "fast",
         "-c:a", "aac", "-b:a", "64k", small)
    if small.stat().st_size > 15_000_000:
        S.stop("ролик слишком тяжёлый для одного запроса — обрежь до 60 секунд.")
    body = {"contents": [{"role": "user", "parts": [
        {"inlineData": {"mimeType": "video/mp4", "data": base64.b64encode(small.read_bytes()).decode()}},
        {"text": PROMPT}]}], "generationConfig": {"maxOutputTokens": 8000}}
    url = (f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/"
           f"{a.model}:generateContent")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    print("… Gemini смотрит ролик (до пары минут)")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        S.stop(f"Google ответил {e.code}. Частое: не включён Vertex AI API или кончились кредиты.")
    text = "".join(p.get("text", "") for c in res.get("candidates", []) for p in c.get("content", {}).get("parts", []))
    out = S.ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# Gemini: разбор стиля — {src.name}\n\n{text}\n", encoding="utf-8")
    print(f"✅ разбор: {out.relative_to(S.ROOT)}")


if __name__ == "__main__":
    main()
