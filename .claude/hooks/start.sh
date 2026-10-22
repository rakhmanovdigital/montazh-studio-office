#!/bin/bash
# Начало дня в студии: живые файлы из шаблонов → снимок-страховка в git → режим и где остановились
# → одно напоминание в день о том, что не установлено. Всё, что печатается, видит помощник.

DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$DIR" || exit 0
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 1. Живые файлы: шаблон `_x-shablon.md` → `x.md`, если ещё нет. Шаблоны обновляет офис,
#    живые — её, поэтому обновления офиса их не перетирают.
make_live() { [ -f "$2" ] || { [ -f "$1" ] && cp "$1" "$2"; }; }
make_live studio/_ucheba-shablon.md     studio/ucheba.md
make_live studio/_ustanovka-shablon.md  studio/ustanovka.md
make_live studio/_doska-shablon.md      studio/doska.md
make_live studio/_pravki-shablon.md     studio/pravki.md
make_live team/uchitel/_memory-shablon.md  team/uchitel/memory.md
make_live team/direktor/_memory-shablon.md team/direktor/memory.md

# 2. Снимок-страховка («кнопка отмена»). Имя для git ставим сами, если его нет, — иначе снимок не сделать.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git config user.name  >/dev/null 2>&1 || git config user.name  "Студия"
  git config user.email >/dev/null 2>&1 || git config user.email "studio@localhost"
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A >/dev/null 2>&1
    if git commit -qm "снимок перед работой: $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1; then
      echo "[страховка] снимок сделан — всё, что было до этого разговора, можно вернуть."
    else
      echo "[страховка] ⚠️ снимок НЕ сделан. Скажи владелице честно: сегодня работаем без страховочной копии."
    fi
  fi
fi

# 3. Режим и место в учёбе.
MODE="учёба"
[ -f studio/ucheba.md ] && grep -qi '^Режим: работа' studio/ucheba.md && MODE="работа"
STEP=$(grep -m1 '^Сейчас:' studio/ucheba.md 2>/dev/null | sed 's/^Сейчас: *//')

if [ ! -f studio/profil.md ]; then
  echo "[студия] ПЕРВЫЙ ЗАХОД. Ты — Господин Тимур, учитель. Прочитай team/uchitel/core.md и скилл uchitel, начни ступень 1 (знакомство). Любое сообщение, даже «привет», — это начало."
elif [ "$MODE" = "учёба" ]; then
  echo "[студия] режим УЧЁБА. Ты — Господин Тимур (team/uchitel/core.md, скилл uchitel). Остановились: ${STEP:-см. studio/ucheba.md}. Первой фразой тепло и без вины: «в прошлый раз мы …, продолжим?»"
else
  echo "[студия] режим РАБОТА. Ты — Директор студии (team/direktor/core.md). Учитель выпустил владелицу и не появляется. Первым сообщением: что в работе по доске studio/doska.md и один следующий шаг."
fi

# 4. Напоминание об установке — не чаще раза в день и только после ступени 2
#    (до неё установкой целиком занимается сам учитель).
TODAY=$(date +%F)
LAST=$(cat studio/.napominanie 2>/dev/null)
STUP2=$(grep -cE '^\| *✅ *\| *2\.' studio/ucheba.md 2>/dev/null)
if [ -f studio/ustanovka.md ] && [ "$LAST" != "$TODAY" ] && { [ "${STUP2:-0}" -gt 0 ] || [ "$MODE" = "работа" ]; }; then
  MISS=$(grep -E '^\| *☐' studio/ustanovka.md | grep -v 'потом' | sed -E 's/^\| *☐ *\| *([^|]+)\|.*/\1/' | sed 's/ *$//' | paste -sd ',' - | sed 's/,/, /g')
  if [ -n "$MISS" ]; then
    echo "[установка] не поставлено: $MISS. Напомни ОДНОЙ строкой в начале (что это и зачем, «поставим сейчас или позже?»). «Позже» = позже, без давления."
    echo "$TODAY" > studio/.napominanie
  fi
fi
exit 0
