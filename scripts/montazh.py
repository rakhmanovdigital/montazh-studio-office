"""Монтажный стол студии: рецепт ролика (JSON) + паспорт стиля клиента → готовый вертикальный ролик.

  python3 -I scripts/montazh.py <рецепт.json>              # весь ролик
  python3 -I scripts/montazh.py <рецепт.json> --probnik    # 1 кадр-пробник (jpg) — показать до монтажа
  python3 -I scripts/montazh.py --test                     # проверка студии: 3-секундный тестовый ролик

Рецепт (пример — clients/_primer-recept.json):
  {"pasport": "clients/<клиент>/pasport.json", "vyhod": "media/gotovo/<клиент>/R-001.mp4",
   "kuski": [{"fajl": "media/ishodniki/<клиент>/a.mp4", "s": 2.0, "po": 9.5}, ...],
   "zagolovok": {"tekst": "3 ошибки в ...", "s": 0, "po": 2.5},          # необязательно
   "muzyka": {"fajl": "media/muzyka/trek.mp3", "gromkost": 0.15},       # необязательно
   "titry": true,                                                        # субтитры из речи (Deepgram)
   "titry_tekst": "текст вручную, если нет речи или ключа"}             # необязательно
Монтаж: обрезка → 9:16 → цвет → зум-склейки → переходы → субтитры → заголовок → музыка под голос
→ громкость -14 LUFS (стандарт соцсетей).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402
import titry as T  # noqa: E402

PASPORT_PO_UMOLCHANIYU = {
    "perehod": {"tip": "cut", "dlit": 0.25},
    "zum": {"vkl": False, "sila": 1.12, "kazhdye_sek": 2.5},
    "cvet": {"kontrast": 1.05, "nasyshchennost": 1.10, "yarkost": 0.0},
    "zvuk": {"loudness": -14, "muzyka_gromkost": 0.15},
    "titry": T.STIL_PO_UMOLCHANIYU,
    "zagolovok": {"fon": "#FFE600", "cvet": "#111111", "shrift": "Montserrat", "razmer": 92, "polozhenie": 0.16},
}


def zagruzit_pasport(path):
    p = json.loads(json.dumps(PASPORT_PO_UMOLCHANIYU))
    if path:
        f = S.ROOT / path
        if not f.exists():
            S.stop(f"нет паспорта стиля {path}. Сначала разберём примеры клиента (навык nasmotrennost).")
        user = json.loads(f.read_text(encoding="utf-8"))
        for k, v in user.items():
            p[k] = {**p.get(k, {}), **v} if isinstance(v, dict) and isinstance(p.get(k), dict) else v
    return p


def vf_osnova(pas, zoom=1.0):
    c = pas["cvet"]
    vf = f"scale={S.W}:{S.H}:force_original_aspect_ratio=increase,crop={S.W}:{S.H}"
    if zoom > 1.001:
        zw, zh = int(S.W / zoom) // 2 * 2, int(S.H / zoom) // 2 * 2
        vf += f",crop={zw}:{zh},scale={S.W}:{S.H}"
    vf += (f",eq=contrast={c['kontrast']}:saturation={c['nasyshchennost']}:brightness={c['yarkost']}"
           f",fps={S.FPS},setsar=1,format=yuv420p")
    return vf


def kusok(src, s, po, idx, pas, work):
    """Один кусок исходника → готовый фрагмент 1080x1920 (с зум-склейками внутри, если в стиле)."""
    src = S.ROOT / src if not Path(src).is_absolute() else Path(src)
    if not src.exists():
        S.stop(f"не нашёл исходник {src.name}")
    info = S.probe(src)
    po = min(po, info["dlit"]) if po else info["dlit"]
    z = pas["zum"]
    step = float(z.get("kazhdye_sek", 2.5)) if z.get("vkl") else (po - s)
    parts, t, j = [], s, 0
    while t < po - 0.05:
        e = min(t + step, po)
        if po - e < 0.4:  # хвостик короче 0.4 с — приклеиваем, а не делаем микро-план
            e = po
        zoom = float(z.get("sila", 1.12)) if (z.get("vkl") and (idx + j) % 2 == 1) else 1.0
        out = work / f"k{idx:02}_{j:02}.mp4"
        d = e - t
        inp = ["-ss", f"{t:.3f}", "-t", f"{d:.3f}", "-i", src]
        if not info["zvuk"]:
            inp += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fade = f"afade=t=in:d=0.03,afade=t=out:st={max(d - 0.03, 0):.3f}:d=0.03,aresample=48000"
        S.ff(*inp, "-vf", vf_osnova(pas, zoom), "-af", fade, "-map", "0:v:0",
             "-map", "0:a:0" if info["zvuk"] else "1:a:0", "-ac", "2",
             "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", out)
        parts.append(out)
        t, j = e, j + 1
    whole = work / f"k{idx:02}.mp4"
    skleit(parts, whole)
    return whole


def skleit(files, out):
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join(f"file '{f}'\n" for f in files), encoding="utf-8")
    S.ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out)


def s_perehodami(files, pas, out):
    tip, d = pas["perehod"].get("tip", "cut"), float(pas["perehod"].get("dlit", 0.25))
    if tip in ("cut", "", None) or len(files) == 1:
        return skleit(files, out)
    durs = [S.probe(f)["dlit"] for f in files]
    args, fc = [], []
    for f in files:
        args += ["-i", f]
    v, a, acc = "[0:v]", "[0:a]", durs[0]
    for i in range(1, len(files)):
        off = acc - d
        fc.append(f"{v}[{i}:v]xfade=transition={tip}:duration={d}:offset={off:.3f}[v{i}]")
        fc.append(f"{a}[{i}:a]acrossfade=d={d}[a{i}]")
        v, a, acc = f"[v{i}]", f"[a{i}]", acc + durs[i] - d
    S.ff(*args, "-filter_complex", ";".join(fc), "-map", v, "-map", a, "-c:v", "libx264", "-crf", "18",
         "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", out)


def zagolovok_png(z, pas, png):
    st = pas["zagolovok"]
    y = int(S.H * st.get("polozhenie", 0.16))
    html = (f"<html><head><meta charset='utf-8'></head><body style='margin:0;width:{S.W}px;height:{S.H}px;"
            f"background:transparent'><div style='position:absolute;left:6%;width:88%;top:{y}px;"
            f"transform:translateY(-50%);text-align:center'><span style=\"display:inline-block;"
            f"background:{st['fon']};color:{st['cvet']};font-family:'{st['shrift']}','Montserrat',Arial,sans-serif;"
            f"font-weight:900;font-size:{st['razmer']}px;line-height:1.05;padding:22px 34px;border-radius:26px;"
            f"text-transform:uppercase;box-shadow:0 10px 30px rgba(0,0,0,.35)\">{S.esc(z['tekst'])}</span></div>"
            f"</body></html>")
    S.render_png(html, png)


def slova_vruchnuyu(tekst, total):
    ws = tekst.split()
    if not ws:
        return []
    step = max(total - 0.4, 0.5) / len(ws)
    return [{"w": w, "s": round(0.2 + i * step, 3), "e": round(0.2 + (i + 1) * step - 0.03, 3)} for i, w in enumerate(ws)]


def finish(base, rec, pas, work, out):
    total = S.probe(base)["dlit"]
    inputs, fc, vlast, n = ["-i", base], [], "[0:v]", 1
    # субтитры
    words = None
    if rec.get("slova"):
        words = rec["slova"]
    elif rec.get("titry_tekst"):
        words = slova_vruchnuyu(rec["titry_tekst"], total)
    elif rec.get("titry", True):
        words = T.slova(base, rec.get("yazyk", "ru"))
        if words is None:
            print("⚠️  нет ключа Deepgram — ролик без субтитров из речи (навык klyuchi)")
    if words:
        layer = T.sloj(words, total, pas["titry"], work / "titry")
        if layer:
            inputs += ["-i", layer]
            fc.append(f"{vlast}[{n}:v]overlay=0:0:format=auto[v{n}]")
            vlast, n = f"[v{n}]", n + 1
    # заголовок-плашка
    z = rec.get("zagolovok")
    if z and z.get("tekst"):
        png = work / "zagolovok.png"
        zagolovok_png(z, pas, png)
        inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", png]
        fc.append(f"{vlast}[{n}:v]overlay=0:0:enable='between(t,{z.get('s', 0)},{z.get('po', 2.5)})'[v{n}]")
        vlast, n = f"[v{n}]", n + 1
    fc.append(f"{vlast}format=yuv420p[vout]")
    # звук: музыка под голос + громкость соцсетей
    lufs = pas["zvuk"].get("loudness", -14)
    m = rec.get("muzyka")
    if m and m.get("fajl"):
        mf = S.ROOT / m["fajl"]
        if not mf.exists():
            S.stop(f"не нашёл музыку {mf.name}")
        g = m.get("gromkost", pas["zvuk"].get("muzyka_gromkost", 0.15))
        inputs += ["-stream_loop", "-1", "-t", f"{total:.3f}", "-i", mf]
        fc.append(f"[0:a]asplit=2[g1][g2];[{n}:a]volume={g}[mu];[mu][g1]sidechaincompress=threshold=0.03:"
                  f"ratio=6:attack=20:release=350[md];[g2][md]amix=inputs=2:duration=first:normalize=0,"
                  f"loudnorm=I={lufs}:TP=-1.5:LRA=11[aout]")
    else:
        fc.append(f"[0:a]loudnorm=I={lufs}:TP=-1.5:LRA=11[aout]")
    out.parent.mkdir(parents=True, exist_ok=True)
    S.ff(*inputs, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", out)


def probnik(rec, pas, out):
    """Один кадр: середина первого куска + пример субтитра + заголовок → jpg. Показать до монтажа."""
    work = S.tmpdir("probnik")
    k = rec["kuski"][0]
    src = S.ROOT / k["fajl"]
    t = (k.get("s", 0) + (k.get("po") or S.probe(src)["dlit"])) / 2
    frame = work / "kadr.png"
    S.ff("-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", vf_osnova(pas).replace(f",fps={S.FPS}", ""), frame)
    st = {**T.STIL_PO_UMOLCHANIYU, **pas["titry"]}
    sample = [{"w": w, "s": 0, "e": 1} for w in "Так будут выглядеть субтитры".split()[: max(2, int(st.get("slov", 3)))]]
    tpng = work / "titr.png"
    S.render_png(T.html_frazy(sample, 1 if st.get("rezhim") != "fraza" else None, st), tpng)
    layers = ["-i", frame, "-i", tpng]
    fc = "[0:v][1:v]overlay=0:0[a]"
    z = rec.get("zagolovok")
    if z and z.get("tekst"):
        zpng = work / "zag.png"
        zagolovok_png(z, pas, zpng)
        layers += ["-i", zpng]
        fc += ";[a][2:v]overlay=0:0[b]"
        last = "[b]"
    else:
        last = "[a]"
    out.parent.mkdir(parents=True, exist_ok=True)
    S.ff(*layers, "-filter_complex", fc, "-map", last, "-frames:v", "1", "-q:v", "2", out)
    print(f"✅ кадр-пробник: {out}")


def test():
    work = S.tmpdir("test")
    src = work / "istochnik.mp4"
    S.ff("-f", "lavfi", "-i", f"testsrc2=size={S.W}x{S.H}:rate={S.FPS}:duration=3", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=3:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", src)
    rec = {"kuski": [{"fajl": str(src), "s": 0, "po": 3}], "zagolovok": {"tekst": "Студия работает ✅", "s": 0, "po": 3},
           "titry_tekst": "Это собрал твой офис"}
    pas = zagruzit_pasport(None)
    base = kusok(str(src), 0, 3, 0, pas, work)
    out = S.MEDIA / "gotovo" / "test" / "test.mp4"
    finish(base, rec, pas, work, out)
    i = S.probe(out)
    ok = i["w"] == S.W and i["h"] == S.H and i["zvuk"] and abs(i["dlit"] - 3) < 0.3
    print(("✅ студия работает: " if ok else "⚠️  ролик собран, но проверь его: ") + str(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recept", nargs="?")
    ap.add_argument("--probnik", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        return test()
    if not a.recept:
        S.stop("нужен рецепт ролика: python3 -I scripts/montazh.py clients/<клиент>/recepty/R-001.json")
    rec = json.loads((S.ROOT / a.recept).read_text(encoding="utf-8"))
    pas = zagruzit_pasport(rec.get("pasport"))
    out = S.ROOT / rec.get("vyhod", "media/gotovo/rolik.mp4")
    if a.probnik:
        return probnik(rec, pas, out.with_name(out.stem + "_probnik.jpg"))
    work = S.tmpdir("montazh")
    parts = []
    for i, k in enumerate(rec["kuski"]):
        print(f"… кусок {i + 1}/{len(rec['kuski'])}")
        parts.append(kusok(k["fajl"], float(k.get("s", 0)), float(k.get("po") or 0), i, pas, work))
    base = work / "sklejka.mp4"
    s_perehodami(parts, pas, base)
    print("… субтитры, заголовок, звук")
    finish(base, rec, pas, work, out)
    print(f"✅ ролик готов: {out}  ({S.probe(out)['dlit']:.1f} с)")
    print(f"   самопроверка: python3 -I scripts/nasmotrennost.py {out.relative_to(S.ROOT)} --sravnit "
          f"{rec.get('pasport', 'clients/<клиент>/pasport.json')}")


if __name__ == "__main__":
    main()
