"""
FTH Trade Copier — единый источник правды по дизайну (тёмная тема, cyan-акцент).

Меняешь внешний вид → правишь ТОЛЬКО этот файл (и fth_theme.json для самих
CustomTkinter-виджетов). Логика приложения сюда не попадает.

Палитра намеренно совпадает с текущим оформлением gui.py (neon cyan на тёмном),
чтобы прототип на CustomTkinter был узнаваем.
"""

# ── Цветовая палитра (neon cyan на тёмном) ──────────────────
BG_DEEP      = "#080810"   # самый тёмный фон окна
BG           = "#0C0C14"   # базовый фон
BG_ROW       = "#111119"   # карточки / строки
BG_ROW_HOVER = "#171722"   # ховер строки
BG_INPUT     = "#191924"   # поля ввода / нейтральные кнопки
BG_HEADER    = "#0E0E18"   # шапка

FG       = "#E4E4EE"        # основной текст
FG_DIM   = "#6A6A80"        # вторичный текст
FG_LABEL = "#8888A0"        # подписи
FG_MUTED = "#3A3A50"        # почти невидимый текст

ACCENT     = "#00B4D8"      # cyan-акцент
ACCENT_H   = "#00D0F0"      # cyan ховер
ACCENT_DIM = "#006E88"      # приглушённый cyan

GREEN     = "#00E676"
GREEN_DIM = "#00B85E"
RED       = "#FF3D57"
RED_DIM   = "#CC3044"
YELLOW    = "#FFB020"
YELLOW_DIM = "#CC8D1A"

BORDER       = "#1C1C2C"
BORDER_LIGHT = "#252538"
DIVIDER      = "#111120"

# ── Шрифты (семейство, размер) ──────────────────────────────
# На Windows по умолчанию Segoe UI / Cascadia Mono. Для рендера прототипа в
# окружении без этих шрифтов можно подменить семейство через переменные
# окружения FTH_FONT_FAMILY / FTH_MONO_FAMILY (на дизайн на Windows не влияет).
import os as _os
FONT_FAMILY = _os.environ.get("FTH_FONT_FAMILY", "Segoe UI")
FONT_MONO_FAMILY = _os.environ.get("FTH_MONO_FAMILY", "Cascadia Mono")

FONT_TITLE    = (FONT_FAMILY, 16, "bold")
FONT_H2       = (FONT_FAMILY, 13, "bold")
FONT_VAL_BOLD = (FONT_FAMILY, 11, "bold")
FONT_VAL      = (FONT_FAMILY, 11)
FONT          = (FONT_FAMILY, 10)
FONT_BOLD     = (FONT_FAMILY, 10, "bold")
FONT_SM       = (FONT_FAMILY, 9)
FONT_XS       = (FONT_FAMILY, 8)
FONT_MONO     = (FONT_MONO_FAMILY, 9)
FONT_MONO_SM  = (FONT_MONO_FAMILY, 8)

# ── Геометрия (скругления, отступы, размеры) ────────────────
RADIUS_CARD   = 10          # карточки KPI / панели
RADIUS_BTN    = 8           # кнопки
RADIUS_INPUT  = 8           # поля ввода
RADIUS_PILL   = 14          # «таблетки» / статус-чипы

PAD_WINDOW = 16             # внешний отступ окна
PAD_CARD   = 14             # внутренний отступ карточки
PAD_GAP    = 8              # промежуток между элементами
PAD_GAP_SM = 4

BTN_HEIGHT     = 32
ICON_BTN_SIZE  = 30
ROW_HEIGHT     = 44
ACCENT_STRIP_W = 3          # ширина цветной полоски слева у панели/строки

WINDOW_MIN = (1100, 720)
WINDOW_DEFAULT = "1140x760"
