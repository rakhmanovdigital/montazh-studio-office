# Словарь «CapCut → студия»

> Владелица говорит на языке CapCut — офис переводит. Колонка «В студии»: что уже есть
> (поле паспорта стиля / рецепта) или как сделать в FFmpeg, если ещё нет — тогда дописываем
> опцию в `scripts/montazh.py` и строку сюда.

| CapCut | В студии | FFmpeg (для помощника) |
|---|---|---|
| Обрезка, склейка | рецепт: `kuski` (файл, с, по) | `-ss 3 -t 4` / `trim`, `concat` |
| Формат 9:16 | всегда, автоматически | `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920` |
| 9:16 с размытым фоном | — (дописать) | `split[a][b];[a]scale=1080:1920,boxblur=20[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2` |
| Переход «растворение» | паспорт `perehod.tip = fade` / `dissolve` | `xfade=transition=fade:duration=0.3:offset=…` |
| Переход «сдвиг / шторка» | `perehod.tip = slideleft / slideup / wipeleft` | `xfade=transition=slideleft` |
| Переход «зум» | `perehod.tip = zoomin` | `xfade=transition=zoomin` |
| Другие переходы | `circleopen · smoothup · pixelize · radial` | список: `ffmpeg -h filter=xfade` |
| Наезд / punch-in (зум-склейка) | паспорт `zum` (`vkl`, `sila`, `kazhdye_sek`) | кроп + масштаб на чётных кусках |
| Плавный наезд (Кен Бёрнс) | — (дописать) | `zoompan=z='min(zoom+0.0015,1.2)':d=1:s=1080x1920:fps=30` |
| Тряска | — (дописать) | `crop=iw-40:ih-40:x='20+15*sin(t*50)':y='20+15*cos(t*43)',scale=1080:1920` |
| Скорость ×2 / замедление | — (дописать) | `setpts=0.5*PTS` + `atempo=2.0` |
| Стоп-кадр | — (дописать) | `tpad=stop_mode=clone:stop_duration=1` |
| Реверс | — (дописать) | `reverse,areverse` |
| Автосубтитры | паспорт `titry` + Deepgram | Chrome-слой поверх видео |
| Субтитры с подсветкой слова | `titry.rezhim = karaoke`, `akcent` — цвет слова | — |
| Субтитры по одному слову | `titry.rezhim = po-slovu` | — |
| Субтитры фразой | `titry.rezhim = fraza`, `slov` — сколько слов | — |
| «Пружинка» слова | `titry.anim = pop` | — |
| Плашка под субтитрами | `titry.fon_plashka = "#000000"` / `"rgba(0,0,0,.7)"` | — |
| Шрифт, размер, цвет, обводка | `titry.shrift / razmer / cvet / obvodka / obvodka_px / ten` | — |
| Капс | `titry.registr = upper` (или `as-is`) | — |
| Где субтитры | `titry.polozhenie` — 0 верх … 1 низ (0.68 — чуть ниже центра) | — |
| Текст-заголовок (хук) | рецепт `zagolovok` + паспорт `zagolovok` (цвета, шрифт) | Chrome-слой |
| Счётчик цифр | есть в витрине (`scripts/vitrina.py`, `schyotchik_sloj`) — перенести в рецепт по просьбе | Chrome-кадры |
| Фильтр / цвет | паспорт `cvet` (`kontrast`, `nasyshchennost`, `yarkost`) | `eq=contrast=1.1:saturation=1.25` |
| LUT | — (дописать) | `lut3d=look.cube` |
| Виньетка | — (дописать) | `vignette=PI/5` |
| Размытие | — (дописать) | `gblur=sigma=20` |
| Сплит-скрин | есть в витрине (демо 4) | `vstack` / `hstack` |
| Картинка в картинке | — (дописать) | `overlay=W-w-40:40` |
| Вспышка | — (дописать) | `fade=t=in:st=4:d=0.15:color=white` |
| Глитч | — (дописать) | `rgbashift=rh=-8:bh=8,noise=alls=20:allf=t` |
| Хромакей | — (дописать) | `chromakey=0x00FF00:0.1:0.05` |
| Музыка | рецепт `muzyka` (файл, громкость) | `amix` |
| Музыка тише под голос | автоматически, если есть музыка | `sidechaincompress` |
| Громкость как в соцсетях | автоматически −14 LUFS (паспорт `zvuk.loudness`) | `loudnorm=I=-14:TP=-1.5` |
| Без щелчков на склейках | автоматически | `afade` 30 мс на краях |
| Звуковые эффекты (вжух) | — (дописать: слой звуков в рецепте) | `adelay` + `amix` |
