"""Проверка ключей в сейфе .env — показывает только ✅/❌, сами ключи НЕ печатает никогда.

  python3 -I scripts/klyuchi.py proverit
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402


def zapros(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError:
        return 0, None


def deepgram(k):
    code, data = zapros("https://api.deepgram.com/v1/projects", {"Authorization": f"Token {k}"})
    if code == 200:
        return "✅ Deepgram: пропуск работает, Deepgram нас слышит"
    if code in (401, 403):
        return "❌ Deepgram: ключ не принят — скопируй заново (Create a New API Key → Copy) и вставь в сейф"
    return "⚠️  Deepgram: нет связи — проверь интернет" if code == 0 else f"⚠️  Deepgram: ответ {code}"


def elevenlabs(k):
    code, _ = zapros("https://api.elevenlabs.io/v1/user", {"xi-api-key": k})
    return "✅ ElevenLabs: пропуск работает" if code == 200 else f"❌ ElevenLabs: ключ не принят ({code})"


def telegram(k):
    code, data = zapros(f"https://api.telegram.org/bot{k}/getMe", {})
    if code == 200 and data and data.get("ok"):
        return f"✅ Telegram-бот: @{data['result'].get('username')}"
    return f"❌ Telegram-бот: токен не принят ({code})"


PROVERKI = {"DEEPGRAM_API_KEY": deepgram, "ELEVENLABS_API_KEY": elevenlabs, "TELEGRAM_BOT_TOKEN": telegram}


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "proverit":
        S.stop("запуск: python3 -I scripts/klyuchi.py proverit")
    if not (S.ROOT / ".env").exists():
        S.stop("сейфа .env ещё нет. Создаём: cp env-shablon.txt .env (навык klyuchi)")
    pusto = []
    for name, fn in PROVERKI.items():
        k = S.klyuch(name)
        if not k:
            pusto.append(name)
            continue
        print(fn(k))
    if pusto:
        print("☐  пустые места в сейфе: " + ", ".join(pusto) + " (это нормально, если сервис не нужен)")


if __name__ == "__main__":
    main()
