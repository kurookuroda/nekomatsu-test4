"""ねこあつめ - 音関係(AudioManager)"""

import pyxel
import game
from config import MEOW_CHANNEL


class AudioManager:
    """WASMでも鳴る生成音で猫の鳴き声を作る(PCMファイルはブラウザで読めないため)。"""

    def __init__(self):
        self.snd_talk = pyxel.Sound()
        self.snd_talk.set("c3", "t", "2", "n", 1)
        self.snd_talk_space = pyxel.Sound()
        self.snd_talk_space.set("c3", "t", "3", "n", 1)
        self.meow_pool = []
        self.meow_named = {}
        self._init_meows()

    def _init_meows(self):
        patterns = [
            ("c3e3g3", "p", "3", "n", 6),   # 高め
            ("a2c3e3", "p", "3", "n", 6),   # 低め
            ("g3b3d4", "p", "3", "n", 8),   # 子猫風
        ]
        for notes, tone, volume, effect, speed in patterns:
            snd = pyxel.Sound()
            snd.set(notes, tone, volume, effect, speed)
            self.meow_pool.append(snd)

    def play_type_sound(self, ch):
        pyxel.play(3, self.snd_talk_space if ch.isspace() else self.snd_talk)

    def meow_for(self, cat_id):
        name = game.CATS.get(cat_id, {}).get("voice")
        if name and name in self.meow_named:
            return self.meow_named[name]
        if self.meow_pool:
            return self.meow_pool[sum(ord(c) for c in cat_id) % len(self.meow_pool)]
        return None

    def play_meow(self, cat_id):
        snd = self.meow_for(cat_id)
        if snd is not None:
            pyxel.play(MEOW_CHANNEL, snd)
