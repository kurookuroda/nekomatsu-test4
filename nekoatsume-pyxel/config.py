"""ねこあつめ - 定数・設定・小関数"""

import game

# ===== 画面 =====
SCREEN_W = 256
SCREEN_H = 256
FONT_PATH = "PixelMplus12-Regular.ttf"
FONT_SIZE = 12
VENDOR = "Neko-Kuroi"
APP_NAME = "nekoatsume-pyxel"
SAVE_NAME = "save.json"

# ===== レイアウト =====
HEADER_H = 18
TAB_Y = 230
TAB_H = SCREEN_H - TAB_Y
ROW_H = FONT_SIZE + 6
LINE_H = FONT_SIZE + 3
LOG_MAX = 30
TOAST_FRAMES = 75
TOAST_MAX_LINES = 3

# ===== ページ送り =====
PAD_X = 6
PAD_Y = 4
CURSOR_H = FONT_SIZE
MSG_X, MSG_Y, MSG_W, MSG_H = 12, 28, SCREEN_W - 24, 192

# ===== スクロールバー =====
BAR_W = 6
BAR_HIT_W = 10
ROW_RIGHT = SCREEN_W - 20

# ===== ショップ =====
SHOP_TOP = HEADER_H + 22
SHOP_HEAD_H = 20
SHOP_DESC_LINES = 3
SHOP_CLOSE_X = SCREEN_W - 8 - 4 - 22
SHOP_BUY_X = SHOP_CLOSE_X - 4 - 48

# ===== 猫の鳴き声 =====
MEOW_DIR = ""
MEOW_EXTS = (".wav", ".ogg", ".mp3", ".flac")
MEOW_MAX = 99
MEOW_CHANNEL = 2

# ===== 色 =====
C_BG, C_PANEL, C_TEXT, C_SUB, C_DIM = 0, 1, 7, 6, 13
C_ACCENT, C_GOOD, C_BAD, C_SILVER, C_GOLD = 10, 11, 8, 6, 10

# ===== タブ・ヘルプ =====
TABS = [("yard", "にわ"), ("shop", "ショップ"), ("bag", "もちもの"), ("cats", "ずかん"), ("help", "ヘルプ")]

HELP_LINES = [
    "ねこあつめへようこそ!",
    "",
    "1. ショップでおもちゃとエサを買う",
    "2. もちものから、おもちゃを庭に置き、エサも置く",
    "3. 猫が遊びに来て、帰るときにさかなを置いていく",
    "4. 「にわ」でさかなを受け取る",
    "",
    "エサは、庭にいる猫が食べた分だけ減っていきます。猫がいないときは減りません。",
    "エサがないと、猫は来ません。",
    "",
    "猫が、お宝を持ってくることがあります。",
    "",
    "文章が長いときは、右下で ▼ が点滅します。画面をタップすると次のページへ、左下の ◀ をタップすると前のページへ戻れます。",
    "猫やアイテムが増えても、リストの右端(バー)をドラッグすれば、すばやく動かせます。",
]

NO_LINE_START = "。、,.!?:;)]」』)…ー・!?"


# ===== 小関数 =====
def fish_text(amount, cur):
    return "{0}のさかな{1}匹".format(game.cur_name(cur), amount)


def event_text(ev):
    kind = ev[0]
    if kind == "arrive":
        return "{0}が{1}で遊び始めた".format(game.CATS[ev[1]]["name"], game.TOYS[ev[2]]["name"])
    if kind == "leave":
        return "{0}が帰った(+{1}{2})".format(game.CATS[ev[1]]["name"], game.cur_name(ev[4]), ev[3])
    if kind == "treasure":
        return "{0}がお宝を置いていった!".format(game.CATS[ev[1]]["name"])
    if kind == "food_out":
        return "エサがなくなった"
    if kind == "met":
        return "{0}と はじめて出会った!".format(game.CATS[ev[1]]["name"])
    return ""