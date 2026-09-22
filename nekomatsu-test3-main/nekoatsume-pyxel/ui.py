"""ねこあつめ - 文字表示パーツ(Typewriter + PagedText)"""

import pyxel
from config import PAD_X, PAD_Y, LINE_H, CURSOR_H, C_ACCENT, C_DIM, FONT_SIZE


class Typewriter:
    """1文字ずつ表示するための小さな状態機械。

    aozora_reader.py(kanekofumiko)の演出を移植したもの。
    表示する文字列はあらかじめ折り返し済み("\n" 区切り)で渡す前提で、
    改行はコマ数を消費せずに読み飛ばす。
    """
    INTERVAL = 2   # 1文字ごとのフレーム数(30fpsで秒間15文字ほど)

    def __init__(self):
        self.text = ""
        self.revealed = 0
        self.timer = 0
        self.done = True

    def set_text(self, text):
        if text == self.text:
            return
        self.text = text
        self.revealed = 0
        self.timer = 0
        self.done = len(text) == 0

    def skip(self):
        self.revealed = len(self.text)
        self.done = True

    def update(self, on_char=None):
        if self.done:
            return
        self.timer += 1
        if self.timer < self.INTERVAL:
            return
        self.timer = 0
        while self.revealed < len(self.text) and self.text[self.revealed] == "\n":
            self.revealed += 1
        if self.revealed < len(self.text):
            ch = self.text[self.revealed]
            self.revealed += 1
            if on_char:
                on_char(ch)
        if self.revealed >= len(self.text):
            self.done = True

    @property
    def visible(self):
        return self.text[:self.revealed]


class PagedText:
    """長い文章を、決められた大きさの枠に収まるページに分け、1文字ずつ表示する。

    - 枠の下には、ページ番号と「▼」を出すための余白(CURSOR_H)を必ず空ける。文章が枠の下にはみ出すことはない
    - 次のページがあるとき、文字を出し終えると「▼」が点滅する。タップ(クリック)かキーで次のページへ進む
    - 行の位置とページの割り方は set() のときに決まり、key が同じあいだは決め直さない
      (伏せ字ときも、本当の文と同じ長さで組むので、あとで明かされても位置がずれない)
    """

    def __init__(self):
        self.key = None
        self.group = None
        self.pages = [[]]          # [[(行, 色), ...], ...]
        self.page = 0
        self.tw = Typewriter()
        self.w = 0
        self.h = 0
        self.seen = -1             # 表示したページの最大番号(いちど出したページは、戻ったとき/進み直すとき、すぐ全部出す)
        self.back_rect = None      # 「◀」(前のページへ)のタップ範囲。直前の描画で決まる(x, y, w, h)

    def set(self, key, blocks, wrap, w, h, group=None):
        """blocks は [(文章, 色), ...]。w, h は枠の大きさ。group が同じなら、ページと表示済みの状態を引き継ぐ。"""
        if key == self.key:
            return
        keep = group is not None and group == self.group
        self.key, self.group = key, group
        self.w, self.h = w, h
        max_lines = max(1, (h - 2 * PAD_Y - CURSOR_H) // LINE_H)
        lines = []
        for text, col in blocks:
            for line in wrap(text, w - 2 * PAD_X - FONT_SIZE):
                lines.append((line, col))
        pages, cur = [], []
        for item in lines:
            if len(cur) >= max_lines:
                pages.append(cur)
                cur = []
            if not cur and pages and item[0] == "":       # ページの頭に来た空行は捨てる
                continue
            cur.append(item)
        if cur or not pages:
            pages.append(cur)
        self.pages = pages
        self.page = min(self.page, len(pages) - 1) if keep else 0
        if not keep:
            self.seen = -1
        self._start_page(skip=keep)

    def _start_page(self, skip=False):
        if self.page <= self.seen:                        # いちど読んだページは、すぐ全部出す
            skip = True
        self.seen = max(self.seen, self.page)
        self.tw.text = None                               # 同じ文でも、最初から出し直す
        self.tw.set_text("\n".join(line for line, _c in self.pages[self.page]))
        if skip:
            self.tw.skip()

    @property
    def typing(self):
        return not self.tw.done

    @property
    def has_next(self):
        return self.page < len(self.pages) - 1

    @property
    def has_prev(self):
        return self.page > 0

    def prev_page(self):
        if self.has_prev:
            self.page -= 1
            self._start_page(skip=True)                   # 戻ったときは、はじめから全部出しておく

    def skip(self):
        self.tw.skip()

    def next_page(self):
        if self.has_next:
            self.page += 1
            self._start_page()

    def advance(self):
        """タップ・キーで呼ぶ。文字送りの途中なら全部出す。出し終えていれば次のページへ。何かしたら True。"""
        if not self.tw.done:
            self.tw.skip()
            return True
        if self.has_next:
            self.next_page()
            return True
        return False

    def update(self, on_char=None):
        self.tw.update(on_char)

    def draw(self, app, x, y):
        """(x, y) は枠の左上。文字は枠の余白の内側に並べる。"""
        cols = [c for _line, c in self.pages[self.page]]
        for i, line in enumerate(self.tw.visible.split("\n")):
            if i < len(cols):
                app.tx(x + PAD_X, y + PAD_Y + i * LINE_H, line, cols[i])
        base = y + self.h - PAD_Y
        self.back_rect = None
        if len(self.pages) > 1:
            # 左下: 「◀ 2/3」。◀ は2ページ目以降に出る(押すと前のページへ)。ページ番号の位置はどのページでも同じ
            if self.has_prev:
                ax, ay = x + PAD_X, base - 10
                pyxel.tri(ax + 6, ay, ax + 6, ay + 8, ax, ay + 4, C_ACCENT)
                self.back_rect = (x, base - FONT_SIZE - 4, PAD_X + 24, FONT_SIZE + 8)   # 指でも押しやすい大きさ
            app.tx(x + PAD_X + 14, base - FONT_SIZE, "{0}/{1}".format(self.page + 1, len(self.pages)), C_DIM)
        if self.tw.done and self.has_next and (pyxel.frame_count // 12) % 2 == 0:
            cx = x + self.w - PAD_X - 8
            pyxel.tri(cx, base - 9, cx + 7, base - 9, cx + 3, base - 3, C_ACCENT)   # 逆三角(▼)の点滅
