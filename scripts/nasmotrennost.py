"""«Насмотренность» — разбор стиля монтажа по готовым роликам: цифры + листы кадров для глаз Claude.

  python3 -I scripts/nasmotrennost.py <ролик1> [<ролик2> ...] --klient <имя>   # разбор примеров → черновик паспорта
  python3 -I scripts/nasmotrennost.py <наш_ролик> --sravnit clients/<клиент>/pasport.json   # самопроверка

Слои: склейки и темп · переходы (кадры вокруг склеек) · текст и субтитры (частые кадры) ·
звук (громкость, бит, режут ли в бит) · цвет (яркость, насыщенность) · речь (если есть ключ Deepgram).
Claude сам видит только картинки и цифры — поэтому скрипт делает ему «глаза во времени»:
листы кадров (jpg), которые нужно ОТКРЫТЬ И ПОСМОТРЕТЬ, прежде чем писать паспорт.
"""
import argparse
import array
import json
import math
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402
import titry as T  # noqa: E402


def sklejki(video, porog=0.3):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
                        f"scale=320:-2,select='gt(scene,{porog})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [round(float(m), 3) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def kadr(video, t, out, w=216):
    S.ff("-ss", f"{max(t, 0):.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={w}:-2", "-q:v", "3", out)


def list_kadrov(files, out, cols):
    """Склеить кадры в один лист (сетка cols колонок)."""
    if not files:
        return None
    rows = math.ceil(len(files) / cols)
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join(f"file '{f}'\n" for f in files), encoding="utf-8")
    S.ff("-f", "concat", "-safe", "0", "-i", lst, "-vf", f"tile={cols}x{rows}:padding=4:color=white",
         "-frames:v", "1", "-q:v", "3", out)
    lst.unlink(missing_ok=True)
    return out


def zvuk(video, dlit):
    """Громкость (LUFS), примерный темп (BPM), моменты ударов."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[0-9.]+) LUFS", r.stderr)
    lufs = float(m[-1]) if m else None
    sr, hop = 11025, 256
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    if len(a) < sr:
        return {"lufs": lufs, "bpm": None, "udary": []}
    env = []
    for i in range(0, len(a) - hop, hop):
        seg = a[i:i + hop]
        env.append(math.sqrt(sum(x * x for x in seg) / hop))
    on = [max(env[i] - env[i - 1], 0) for i in range(1, len(env))]
    mu, sd = st.mean(on), (st.pstdev(on) or 1)
    fr = sr / hop
    udary = [round((i + 1) / fr, 3) for i in range(1, len(on) - 1)
             if on[i] > mu + 1.5 * sd and on[i] >= on[i - 1] and on[i] >= on[i + 1]]
    best, bpm = 0, None
    for lag in range(int(fr * 60 / 180), int(fr * 60 / 70) + 1):
        c = sum(on[i] * on[i - lag] for i in range(lag, len(on)))
        if c > best:
            best, bpm = c, round(60 * fr / lag)
    return {"lufs": lufs, "bpm": bpm, "udary": udary}


def cvet(video, work):
    log = work / "cvet.txt"
    subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(video), "-vf",
                    "fps=2,scale=320:-2,signalstats,metadata=mode=print:file=cvet.txt", "-an", "-f", "null", "-"],
                   capture_output=True, cwd=work)
    txt = log.read_text() if log.exists() else ""
    y = [float(v) for v in re.findall(r"signalstats\.YAVG=([0-9.]+)", txt)]
    s = [float(v) for v in re.findall(r"signalstats\.SATAVG=([0-9.]+)", txt)]
    return {"yarkost": round(st.mean(y), 1) if y else None, "nasyshchennost": round(st.mean(s), 1) if s else None}


def razobrat(video, work, slova_vkl=True):
    video = Path(video)
    info = S.probe(video)
    d = info["dlit"]
    cuts = [c for c in sklejki(video) if 0.15 < c < d - 0.15]
    bounds = [0.0] + cuts + [d]
    plany = [round(bounds[i + 1] - bounds[i], 3) for i in range(len(bounds) - 1)]
    half = d / 2
    p1 = [p for p, b in zip(plany, bounds) if b < half] or plany
    p2 = [p for p, b in zip(plany, bounds) if b >= half] or plany
    w = work / video.stem
    w.mkdir(parents=True, exist_ok=True)
    # лист «планы»: по кадру из середины каждого плана
    pf = []
    for i in range(len(bounds) - 1)[:48]:
        f = w / f"plan_{i:03}.jpg"
        kadr(video, (bounds[i] + bounds[i + 1]) / 2, f, 180)
        pf.append(f)
    list_plany = list_kadrov(pf, w / "1_plany.jpg", 8)
    # лист «переходы»: 5 кадров вокруг каждой из первых 8 склеек
    tf = []
    for c in cuts[:8]:
        for k, dt in enumerate((-0.2, -0.1, 0.0, 0.07, 0.2)):
            f = w / f"per_{c:07.3f}_{k}.jpg"
            kadr(video, c + dt, f, 216)
            tf.append(f)
    list_per = list_kadrov(tf, w / "2_perehody.jpg", 5)
    # лист «текст»: первые 3 секунды, 6 кадров/с — видно субтитры, их анимацию и хук
    xf = []
    for i in range(18):
        f = w / f"txt_{i:02}.jpg"
        kadr(video, i / 6, f, 216)
        xf.append(f)
    list_txt = list_kadrov(xf, w / "3_tekst_nachalo.jpg", 6)
    # крупные кадры — прочитать шрифт
    kf = []
    for j, t in enumerate((d * 0.2, d * 0.4, d * 0.6, d * 0.8)):
        f = w / f"krup_{j}.jpg"
        kadr(video, t, f, 540)
        kf.append(f)
    list_krup = list_kadrov(kf, w / "4_krupno.jpg", 2)
    for f in pf + tf + xf + kf:
        f.unlink(missing_ok=True)
    zv = zvuk(video, d) if info["zvuk"] else {"lufs": None, "bpm": None, "udary": []}
    v_bit = None
    if cuts and zv["udary"]:
        v_bit = round(sum(1 for c in cuts if any(abs(c - u) < 0.09 for u in zv["udary"])) / len(cuts), 2)
    rech = None
    if slova_vkl and info["zvuk"]:
        words = T.slova(video)
        if words:
            rech = {"slov": len(words), "slov_v_sek": round(len(words) / max(d, 1), 2)}
    return {
        "fajl": video.name, "dlit": round(d, 2), "format": f"{info['w']}x{info['h']}", "fps": info["fps"],
        "sklejki": len(cuts), "plan_sek": round(st.mean(plany), 2), "plan_mediana": round(st.median(plany), 2),
        "plan_min": min(plany), "plan_max": max(plany),
        "sklejki_pervye_3s": sum(1 for c in cuts if c < 3),
        "temp_1_polovina": round(st.mean(p1), 2), "temp_2_polovina": round(st.mean(p2), 2),
        "lufs": zv["lufs"], "bpm": zv["bpm"], "sklejki_v_bit": v_bit,
        **cvet(video, w), "rech": rech,
        "listy": [str(Path(x).relative_to(S.ROOT)) for x in (list_plany, list_per, list_txt, list_krup) if x],
    }


def srednee(rs, k):
    v = [r[k] for r in rs if isinstance(r.get(k), (int, float))]
    return round(st.mean(v), 2) if v else None


ETALON_KEYS = ("plan_sek", "plan_mediana", "sklejki_pervye_3s", "lufs", "bpm", "sklejki_v_bit",
               "yarkost", "nasyshchennost")


def sravnit(r, pasport_path):
    p = json.loads((S.ROOT / pasport_path).read_text(encoding="utf-8"))
    et = p.get("etalon") or {}
    if not et:
        S.stop("в паспорте нет блока «etalon» — сначала разбор примеров клиента.")
    print(f"\nСамопроверка «{r['fajl']}» против паспорта {pasport_path}:")
    bad = 0
    for k in ETALON_KEYS:
        a, b = r.get(k), et.get(k)
        if a is None or b is None:
            continue
        if k == "lufs":
            ok = abs(a - b) <= 2.5
        elif k == "sklejki_pervye_3s":
            ok = abs(a - b) <= 1
        elif k == "sklejki_v_bit":
            ok = a >= b - 0.2
        else:
            ok = abs(a - b) <= max(abs(b) * 0.25, 0.15)
        bad += 0 if ok else 1
        print(f"  {'✅' if ok else '⚠️ '} {k}: у нас {a} · эталон {b}")
    print("Итог: " + ("совпадает со стилем ✅" if bad == 0 else f"расхождений: {bad} — поправь рецепт/паспорт и пересобери"))
    print("Не забудь посмотреть листы кадров глазами — цифры не видят «вайб»:")
    for x in r["listy"]:
        print("  ", x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="+")
    ap.add_argument("--klient")
    ap.add_argument("--sravnit")
    ap.add_argument("--bez-rechi", action="store_true", help="не отправлять звук в Deepgram")
    a = ap.parse_args()
    S.need("ffmpeg")
    name = a.klient or "razbor"
    work = S.ROOT / "clients" / name / "nasmotrennost" if a.klient else S.tmpdir("nasmotrennost")
    work.mkdir(parents=True, exist_ok=True)
    rs = []
    for v in a.video:
        vp = S.ROOT / v if not Path(v).is_absolute() else Path(v)
        if not vp.exists():
            S.stop(f"не нашёл файл {v}")
        print(f"… разбираю {vp.name}")
        rs.append(razobrat(vp, work, not a.bez_rechi))
    if a.sravnit:
        return sravnit(rs[0], a.sravnit)
    obshee = {k: srednee(rs, k) for k in ETALON_KEYS + ("temp_1_polovina", "temp_2_polovina", "dlit")}
    (work / "razbor.json").write_text(json.dumps({"roliki": rs, "obshee": obshee}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    md = [f"# Насмотренность — {name}", "", f"Разобрано роликов: {len(rs)}", "", "## Общее (среднее по роликам)", ""]
    md += [f"- {k}: {v}" for k, v in obshee.items()]
    md += ["", "## По роликам", ""]
    for r in rs:
        md += [f"### {r['fajl']} — {r['dlit']} с, {r['format']}",
               f"- склеек: {r['sklejki']} · план в среднем {r['plan_sek']} с (медиана {r['plan_mediana']}) · "
               f"в первые 3 с склеек: {r['sklejki_pervye_3s']}",
               f"- темп: 1-я половина {r['temp_1_polovina']} с/план → 2-я {r['temp_2_polovina']} с/план",
               f"- звук: {r['lufs']} LUFS · ~{r['bpm']} BPM · склейки в бит: {r['sklejki_v_bit']}",
               f"- цвет: яркость {r['yarkost']}/255 · насыщенность {r['nasyshchennost']}",
               f"- речь: {r['rech']}", "- листы кадров (ОТКРОЙ И ПОСМОТРИ):"]
        md += [f"  - {x}" for x in r["listy"]]
        md.append("")
    (work / "razbor.md").write_text("\n".join(md), encoding="utf-8")
    if a.klient:
        pas_path = S.ROOT / "clients" / name / "pasport.json"
        if not pas_path.exists():
            black = json.loads((S.ROOT / "clients" / "_pasport-shablon.json").read_text(encoding="utf-8"))
            black["klient"] = name
            black["etalon"] = {k: obshee[k] for k in ETALON_KEYS}
            black["zum"]["kazhdye_sek"] = obshee["plan_sek"] or 2.5
            pas_path.write_text(json.dumps(black, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"✅ черновик паспорта: {pas_path.relative_to(S.ROOT)} — допиши стиль по листам кадров")
        else:
            print("ℹ️  паспорт уже есть — эталон не перезаписан; сравни razbor.json и обнови вручную")
    print(f"✅ разбор: {(work / 'razbor.md').relative_to(S.ROOT)}")


if __name__ == "__main__":
    main()
