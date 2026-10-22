"""Витрина: из ОДНОГО исходника — 5 демо-роликов в разных стилях. Показать, а не рассказать.

  python3 -I scripts/vitrina.py <исходник.mp4> [--sek 12]

1 караоке-субтитры · 2 счётчик-инфографика · 3 резкие склейки с зумом ·
4 разделённый экран · 5 заголовок-плашка + плавный переход.
Готовое: media/gotovo/vitrina/. Без ключа Deepgram субтитры будут из готовой фразы.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import studiya as S  # noqa: E402
import titry as T  # noqa: E402
import montazh as M  # noqa: E402

ZAPASNAYA_FRAZA = "Этот ролик собрал твой офис сам за пару минут без единого клика в монтажке"


def pas(**over):
    p = M.zagruzit_pasport(None)
    for k, v in over.items():
        p[k] = {**p[k], **v}
    return p


def schyotchik_sloj(total, work, do=1000, podpis="ПРОСМОТРОВ ЗА ДЕНЬ"):
    """Цифра растёт 0 → do за 1.5 с и держится — инфографика поверх видео."""
    states, jobs, n = [], [], 24
    for i in range(n + 1):
        val = int(do * (1 - (1 - i / n) ** 3))  # плавное замедление к концу
        num = f"{val:,}".replace(",", " ")
        png = work / f"sch_{i:02}.png"
        html = (f"<html><head><meta charset='utf-8'></head><body style='margin:0;width:{S.W}px;height:{S.H}px;"
                f"background:transparent'><div style=\"position:absolute;top:220px;width:100%;text-align:center;"
                f"font-family:'Montserrat','Inter',Arial,sans-serif\"><div style=\"display:inline-block;"
                f"background:rgba(10,10,10,.82);border-radius:36px;padding:28px 56px\">"
                f"<div style='font-size:170px;font-weight:900;color:#FFE600;line-height:1'>+{num}"
                f"</div><div style='font-size:44px;font-weight:800;color:#fff;letter-spacing:2px'>{podpis}</div>"
                f"</div></div></body></html>")
        jobs.append((html, png))
        t0 = 0.6 + i * (1.5 / n)
        states.append((png, t0, t0 + 1.5 / n if i < n else total))
    S.render_many(jobs)
    return S.sloj_video(states, total, work / "schyotchik.mov")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--sek", type=float, default=12.0)
    a = ap.parse_args()
    src = Path(a.video)
    src = src if src.is_absolute() else S.ROOT / src
    if not src.exists():
        S.stop(f"не нашёл файл {a.video}")
    info = S.probe(src)
    L = min(a.sek, info["dlit"])
    if L < 4:
        S.stop("видео слишком короткое — нужно хотя бы 5 секунд, лучше 20–60.")
    out_dir = S.MEDIA / "gotovo" / "vitrina"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("… расшифровываю речь по словам (Deepgram)")
    words = T.slova(src)
    if words:
        words = [w for w in words if w["e"] <= L]
    if not words:
        print("⚠️  речи нет или нет ключа — субтитры будут из готовой фразы")
        words = M.slova_vruchnuyu(ZAPASNAYA_FRAZA, L)

    def sobrat(n, name, p, kuski, extra=None, slova=None):
        print(f"… демо {n}/5: {name}")
        work = S.tmpdir(f"vitrina{n}")
        parts = [M.kusok(str(src), s, e, i, p, work) for i, (s, e) in enumerate(kuski)]
        base = work / "base.mp4"
        M.s_perehodami(parts, p, base)
        rec = {"slova": slova if slova is not None else words, **(extra or {})}
        out = out_dir / f"{n}_{name}.mp4"
        M.finish(base, rec, p, work, out)
        return out, work

    # 1 — караоке
    sobrat(1, "karaoke-subtitry", pas(titry={"rezhim": "karaoke", "slov": 3}), [(0, L)])

    # 2 — счётчик-инфографика (поверх готового ролика с фразовыми субтитрами)
    out2, work2 = sobrat(2, "schyotchik", pas(titry={"rezhim": "fraza", "slov": 4, "akcent": "#FFFFFF"}), [(0, L)])
    tmp2 = work2 / "s_titrami.mp4"
    out2.rename(tmp2)
    layer = schyotchik_sloj(S.probe(tmp2)["dlit"], work2)
    T.nalozhit(tmp2, layer, out2)

    # 3 — резкие склейки с зумом, субтитры по одному слову
    sobrat(3, "zum-sklejki", pas(zum={"vkl": True, "sila": 1.18, "kazhdye_sek": 1.3},
                                  titry={"rezhim": "po-slovu", "razmer": 120, "akcent": "#00E5FF"}), [(0, L)])

    # 4 — разделённый экран: сверху общий план, снизу крупный
    print("… демо 4/5: razdelennyj-ekran")
    work4 = S.tmpdir("vitrina4")
    half = f"scale={S.W}:{S.H // 2}:force_original_aspect_ratio=increase,crop={S.W}:{S.H // 2}"
    big = (f"scale={S.W}:{S.H // 2}:force_original_aspect_ratio=increase,crop={int(S.W / 1.6)}:{int(S.H / 2 / 1.6)},"
           f"scale={S.W}:{S.H // 2}")
    split = work4 / "split.mp4"
    S.ff("-t", f"{L:.3f}", "-i", src, "-filter_complex",
         f"[0:v]split[a][b];[a]{half}[t];[b]{big}[d];[t][d]vstack,fps={S.FPS},setsar=1,format=yuv420p[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac",
         "-ar", "48000", "-ac", "2", split)
    if not info["zvuk"]:
        S.stop("в исходнике нет звука — выбери видео, где кто-то говорит.")
    p4 = pas(titry={"rezhim": "karaoke", "slov": 2, "polozhenie": 0.5, "fon_plashka": "#111111", "obvodka_px": 0,
                    "akcent": "#FF4D8D"})
    M.finish(split, {"slova": words}, p4, work4, out_dir / "4_razdelennyj-ekran.mp4")

    # 5 — заголовок-плашка + плавный переход между двумя кусками
    mid = round(L / 2, 2)
    d = 0.35
    w5 = [dict(w, s=round(w["s"] - (d if w["s"] > mid else 0), 3), e=round(w["e"] - (d if w["s"] > mid else 0), 3))
          for w in words]
    sobrat(5, "plashka-i-perehod", pas(perehod={"tip": "fade", "dlit": d},
                                        titry={"rezhim": "fraza", "slov": 5, "fon_plashka": "rgba(0,0,0,.72)",
                                               "obvodka_px": 0, "razmer": 64, "registr": "as-is"}),
           [(0, mid), (mid, L)], extra={"zagolovok": {"tekst": "3 секрета монтажа", "s": 0, "po": 3}}, slova=w5)

    print(f"\n✅ витрина готова: {out_dir.relative_to(S.ROOT)}/ — 5 роликов")


if __name__ == "__main__":
    main()
