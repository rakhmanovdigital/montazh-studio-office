"""Субтитры студии: Deepgram (слова с точным временем) → кадры текста через Chrome → прозрачный слой.

Звук уходит в Deepgram (это согласовано с владелицей на ступени 3). Ключ — из сейфа .env.

  python3 -I scripts/titry.py <видео> --out <готовое.mp4> [--pasport clients/<клиент>/pasport.json]
  python3 -I scripts/titry.py <видео> --tolko-slova      # только расшифровка по словам (.json + .srt)
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402

STIL_PO_UMOLCHANIYU = {
    "rezhim": "karaoke", "slov": 3, "shrift": "Montserrat", "ves": 900, "razmer": 84,
    "cvet": "#FFFFFF", "akcent": "#FFE600", "obvodka": "#000000", "obvodka_px": 6, "ten": True,
    "polozhenie": 0.68, "registr": "upper", "fon_plashka": None, "anim": "pop",
}


def slova(video, lang="ru", cache_dir=None):
    """Слова с временем [{w, s, e}]. Кэш рядом, чтобы не платить дважды за тот же файл."""
    video = Path(video)
    cache_dir = Path(cache_dir or S.TMP / "slova")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / (video.stem + f".{lang}.slova.json")
    if cache.exists() and cache.stat().st_mtime > video.stat().st_mtime:
        return json.loads(cache.read_text(encoding="utf-8"))
    key = S.klyuch("DEEPGRAM_API_KEY")
    if not key:
        return None
    wav = cache_dir / (video.stem + ".wav")
    S.ff("-i", video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav)
    params = f"model=nova-3&smart_format=true&punctuate=true&language={lang}"
    req = urllib.request.Request("https://api.deepgram.com/v1/listen?" + params, data=wav.read_bytes(),
                                 method="POST", headers={"Authorization": f"Token {key}",
                                                         "Content-Type": "audio/wav"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            S.stop("Deepgram не принял ключ. Проверим сейф: python3 -I scripts/klyuchi.py proverit")
        if e.code == 402:
            S.stop("в Deepgram закончились деньги на счёте (подарочные). Сам он ничего не спишет.")
        S.stop(f"Deepgram ответил ошибкой {e.code}.")
    except urllib.error.URLError:
        S.stop("нет связи с Deepgram — проверь интернет.")
    finally:
        wav.unlink(missing_ok=True)
    alt = data["results"]["channels"][0]["alternatives"][0]
    out = [{"w": x.get("punctuated_word") or x["word"], "s": round(x["start"], 3), "e": round(x["end"], 3)}
           for x in alt.get("words", [])]
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def srt(words, path, n=6):
    def ts(t):
        h, m = int(t // 3600), int(t % 3600 // 60)
        return f"{h:02}:{m:02}:{int(t % 60):02},{int(round(t % 1 * 1000)) % 1000:03}"
    lines = []
    for i, g in enumerate(gruppy(words, n), 1):
        lines += [str(i), f"{ts(g[0]['s'])} --> {ts(g[-1]['e'])}", " ".join(x["w"] for x in g), ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def gruppy(words, n):
    """Делим на фразы по n слов; рвём раньше на точке/вопросе или паузе > 0.6 с."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_punct = w["w"][-1:] in ".!?…"
        pause = nxt is not None and nxt["s"] - w["e"] > 0.6
        if len(cur) >= n or end_punct or pause or nxt is None:
            out.append(cur)
            cur = []
    return out


def html_frazy(slova_g, active, st):
    """Одна фраза; active — индекс подсвеченного слова (или None)."""
    y = int(S.H * st.get("polozhenie", 0.68))
    spans = []
    for i, w in enumerate(slova_g):
        t = S.esc(w["w"])
        if active is not None and i == active:
            scale = "transform:scale(1.12);" if st.get("anim") == "pop" else ""
            spans.append(f"<span style='display:inline-block;margin:0 .14em;color:{st.get('akcent', '#FFE600')};"
                         f"{scale}'>{t}</span>")
        else:
            spans.append(f"<span style='display:inline-block;margin:0 .14em'>{t}</span>")
    plashka = st.get("fon_plashka")
    box = (f"background:{plashka};padding:18px 28px;border-radius:22px;-webkit-text-stroke:0;"
           if plashka else "")
    return (f"<html><head><meta charset='utf-8'></head><body style='margin:0;width:{S.W}px;height:{S.H}px;"
            f"background:transparent;overflow:hidden'>"
            f"<div style=\"position:absolute;left:5%;width:90%;top:{y}px;transform:translateY(-50%);"
            f"text-align:center\"><span style=\"{S.css_text(st)}{box}display:inline-block;max-width:100%;"
            f"word-spacing:6px\">{' '.join(spans)}</span></div></body></html>")


def sloj(words, total, st, workdir):
    """Слова → прозрачный видеослой с субтитрами нужного стиля."""
    st = {**STIL_PO_UMOLCHANIYU, **(st or {})}
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    jobs, states = [], []
    mode = st.get("rezhim", "karaoke")
    for gi, g in enumerate(gruppy(words, int(st.get("slov", 3)))):
        g_end = g[-1]["e"] + 0.15
        if mode == "fraza":
            png = work / f"t{gi:04}.png"
            jobs.append((html_frazy(g, None, st), png))
            states.append((png, g[0]["s"], g_end))
            continue
        for wi, w in enumerate(g):
            nxt = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
            png = work / f"t{gi:04}_{wi:02}.png"
            if mode == "po-slovu":
                jobs.append((html_frazy([w], 0, st), png))
            else:
                jobs.append((html_frazy(g, wi, st), png))
            states.append((png, w["s"], max(nxt, w["s"] + 0.05)))
    if not jobs:
        return None
    print(f"… рисую субтитры: {len(jobs)} кадров текста")
    S.render_many(jobs)
    return S.sloj_video(states, total, work / "titry.mov")


def nalozhit(video, layer, out):
    S.ff("-i", video, "-i", layer, "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-c:a", "copy", "-movflags", "+faststart", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out")
    ap.add_argument("--pasport")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--tolko-slova", action="store_true")
    a = ap.parse_args()
    words = slova(a.video, a.lang)
    if words is None:
        S.stop("нет ключа Deepgram в сейфе — субтитры из речи не сделать. Подключим? (навык klyuchi)")
    if a.tolko_slova:
        base = Path(a.out or Path(a.video).with_suffix(""))
        Path(str(base) + ".slova.json").write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
        srt(words, str(base) + ".srt")
        print(f"✅ расшифровка: {len(words)} слов → {base}.srt")
        return
    st = json.loads(Path(a.pasport).read_text(encoding="utf-8")).get("titry", {}) if a.pasport else {}
    total = S.probe(a.video)["dlit"]
    work = S.tmpdir("titry")
    layer = sloj(words, total, st, work)
    out = a.out or str(Path(a.video).with_name(Path(a.video).stem + "_titry.mp4"))
    nalozhit(a.video, layer, out)
    print(f"✅ готово: {out}")


if __name__ == "__main__":
    main()
