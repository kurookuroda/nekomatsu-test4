# nekomatsu-test3 データ構造設計(草案)

いままでの雑談を、実装できる形に落としたものです。
いまの `catalog.py` の「タプルの行を1つ足せば増やせる」というスタイルは崩さずに、
そこへ差し込む形にしてあります。

段階を分けているのは、一度に全部作ると身動きが取れなくなるからです。
各フェーズは、それ単体で動く状態まで作ってから次へ進めます。

---

## フェーズ1: 猫の個性(満腹・好み・性格)

いちばん体感が変わる部分なので、最初に着手するのがおすすめです。

### catalog.py: CATS の個性上書きを拡張

いまの `{'strength': 6}` のような上書き辞書に、キーを増やします。

```python
CATS = [
    ('gordo', 'ゴードー', '...', '役に立たない木切れ(ゴードーだから)',
     {'sex': 'm',
      'traits': {'appetite': 0.8, 'friendly': 0.4, 'wary': 0.3},
      'taste': {'meat': 1.0, 'fish': 0.2},
      'affinity': {'turtle': 0.1}}),
    ('tarawa', 'タラワ', '...', 'アオカケスの羽根',
     {'strength': 6,
      'sex': 'f',
      'traits': {'appetite': 0.3, 'friendly': 0.2, 'wary': 0.6},
      'taste': {'grass': 1.0},
      'affinity': {'turtle': 0.8}}),   # のんびりした猫は亀と仲良し
]
```

- `traits` / `taste` / `affinity` は 0〜1 の少数。書かなければ既定値(中庸)。
- `taste` のキーは、エサの `tags`(下記)と突き合わせる。

### catalog.py: FOODS にタグを追加

```python
# エサ: (ID, 名前, 価格, 通貨, もつ時間(分), 好みタグ, 説明)
FOODS = [
    ('dry_food', 'ドライフード', 10, 's', 300, {'meat': 0.5, 'grain': 0.5}, '...'),
    ('wet_food', 'ウェットフード缶', 2, 'g', 300, {'fish': 1.0}, '...'),
    ('fancy_food', '高級フード缶', 5, 'g', 300, {'fish': 0.7, 'meat': 0.3}, '...'),
    ('catnip_snack', '猫草スナック', 8, 's', 200, {'grass': 1.0}, '...'),  # 新規
]
```

### game.py: 効果の掛け先(いまある変数にそのまま乗る)

- **来やすさ** (`entry_chance`): `taste` とエサの `tags` の内積で補正。好きなエサほど来やすい。
- **満腹度** (`fullness`, 猫の状態に新規追加): 食べると増え、時間で減る。
  エサの減り方も「時間で1ずつ」から「庭にいる猫が食べた分」に変える。
- **食いしん坊** (`traits.appetite`): 高いほど1回に多く食べる → エサの減りが速い。
- **警戒** (`traits.wary`): 初期の「そっけなさ」。後述の `trust` で緩和される。

### 猫の状態(セーブに入る側)に足す

```python
cat_state = {
    ..., "fullness": 0.5, "trust": 0.0, "happiness": 0.5,
}
```

---

## フェーズ2: 隠れたレベルと日時ログ

ユーザーに見せない進行度と、あとで振り返れる記録です。フェーズ3以降の「出現条件」の土台になります。

### game.py: 状態に追加

```python
state["player_name"] = "黒いネコちゃん"   # 初回起動時に決める。あとから変更も可
state["level"] = 0
state["ever_had"] = set()      # 一度でも持ったことがあるアイテムID
state["flags"] = set()         # 一度きりの出来事の印
state["met_actors"] = {}       # {actor_id: 最初に出会った時刻}
state["created_at"] = now
state["log"] = []              # [{"at": epoch秒, "type": "...", "detail": {...}}, ...]
```

`player_name` の使いどころ:

- **人のキャラのセリフ**: 「〇〇さん、ありがとう」のように、時々名前で呼ばせると、
  キャツアイ経由で物を渡す関係が、ぐっと個人的なものに感じられる。
  ただし毎回名前を出すと煩わしいので、初対面や `one_time_reward` のときなど、節目だけに絞る。
- **ログ**(`state["log"]`): 「〇〇さんの庭に、キャツアイが立ち寄った」のように書ける。
- **フェーズ5(ユーザー間のやり取り)**: `mail` の送り主表示や、届いたときの文面に使う
  (`from_user_id` はDBの内部キー、`player_name` は画面表示用、という役割分担にしておく)。

### レベルの上がり方(1本の隠れた合計値)

```python
LEVEL_GAINS = {
    "met_new_cat": 1,
    "chain_step": 3,
    "stage_unlocked": 10,
}
```

猫を集めても、贈り物を辿っても、同じ「レベル」という1つの数字に積み上がる。
どちらかに偏っても、もう片方の出現条件(フェーズ3)が止まるだけで、詰みにはしない。

### 条件判定を1つの関数にまとめる(ショップ解放・キャラ出現・鎖の次の一手、全部で使う)

```python
def meets(state, requires):
    if not requires:
        return True
    if "level" in requires and state["level"] < requires["level"]:
        return False
    if "items" in requires and not set(requires["items"]) <= state["ever_had"]:
        return False
    if "met" in requires and len(state["met_actors"]) < requires["met"]:
        return False
    if "flag" in requires and requires["flag"] not in state["flags"]:
        return False
    return True
```

---

## フェーズ3: 訪問者・人・ギフトの鎖(キャツアイ、盗賊団、人のキャラ)

猫と同じ「来て・滞在して・帰る」流れに、訪問者(actor)という共通の型で乗せます。

### 新しい表: ACTORS(catalog.py に追加)

```python
# 訪問者・人: (ID, 種類, 名前, 紹介文, 個性の上書き辞書)
# 種類: "cat"(いまのCATSと同じ) / "visitor"(通り過ぎるだけ) / "person"(居着く・ギフトを受け取る)
ACTORS = [
    ('catseye_a', 'visitor', 'キャツアイの誰か',
     '使い古しの電子機器を引き取って売り買いしている。お金にはこだわらず、猫を愛している。',
     {'habitat': ['mansion'],
      'requires': {'level': 5},
      'gifts': [('item:smartphone', 0.5), ('item:laptop', 0.2), ('item:sweets', 0.3)]}),

    ('jiro', 'person', 'じろうさん',
     '...',
     {'habitat': ['mansion'],
      'requires': {'items': ['smartphone']},   # スマホを一度でも受け取っていれば出現
      'wants': {'electronics': 1},
      'one_time_reward': {'creature': 'turtle', 'unlocks': 'obaachan'}}),

    ('obaachan', 'person', 'おばあちゃん',
     '...',
     {'habitat': ['mansion'],
      'requires': {'flag': 'unlocked_obaachan'},
      'wants': {'sweets': 1},
      'one_time_reward': {'item': 'amulet', 'unlocks': 'stage:mansion2'}}),

    ('sparrow', 'visitor', 'すずめ',
     'ふらっと立ち寄るだけ。何も残さない。',
     {'habitat': ['garden', 'mansion'], 'outcome': None}),
]
```

### ITEMS に goods(取引品)を追加

```python
# 物(取引品。庭には置かない): (ID, 名前, 好みタグ, 説明)
GOODS = [
    ('smartphone', 'スマホ', {'electronics': 1.0}, '...'),
    ('laptop', 'パソコン', {'electronics': 1.0}, '...'),
    ('sweets', 'お菓子', {'sweets': 1.0}, '...'),
    ('amulet', 'お守り', {}, '...'),
]
```

### 出来事の型(outcome / one_time_reward の中身)

`"item:xxx"` / `"creature:xxx"` / `"flag:xxx"` / `"stage:xxx"` のどれか。
猫のお宝(`treasure`)も、将来この型に統一できる。

### あげる/売る操作(game.py に新規関数)

```python
def give(state, actor_id, item_id): ...   # 好みに合うほど trust / happiness が上がる
def sell(state, actor_id, item_id): ...   # さかなが入る。trustの上がりは小さい/なし
```

`one_time_reward` は、**その人物ごとに一度だけ**。2回目以降は `after`(小さな反応)に切り替える。

---

## フェーズ4: 場所(庭→屋敷)とスペースの拡張

### catalog.py: PLACES

```python
PLACES = [
    # (ID, 表示名, マス数, 水辺の種類, 解放条件)
    ('garden',  '庭',  6,  'puddle', None),
    ('mansion', '屋敷', 12, 'pond',   {'flag': 'stage:mansion'}),
]
```

### state の持ち方

```python
state["place"] = "garden"
state["places"] = {
    "garden":  {"yard": [...], "occ": {...}, "pets": []},   # pets = 亀など、マスを使わない同居者
    "mansion": {"yard": [], "occ": {}, "pets": []},
}
```

`pets` は庭のマス(`space`)を消費しない別枠。猫の `affinity` は、いま自分がいる場所の `pets` と突き合わせる。

---

## フェーズ5(先の話): ユーザー間のやり取り

ここはサーバー(FastAPI)が要る段階なので、フェーズ1〜4が固まってからでよい。

```python
# サーバー側テーブルの案
# mail(id, from_user_id, to_user_id, item_id, sent_at, deliver_at, opened_at)
```

`deliver_at` の判定は、フェーズ2で作る「経過時間で進める」考え方(`advance()`)がそのまま使える。
配達役はキャツアイのイメージ(誰かの庭に立ち寄って、預かって、別の庭に届ける)。

---

## 未確定のまま進める判断(要確認)

- **レベルは1本か、2軸(猫まわり/人まわり)か** → ひとまず1本で設計。分けたくなったら `level` を `level_cat` / `level_person` に割るだけで済む形にしてある。
- **亀の入手経路**(ショップで買えるのか、贈り物だけか) → `one_time_reward` 経由のみ、という前提で設計。ショップ購入も許すなら `GOODS` 側に `for_sale: True` を足すだけ。
- **人物の人数**(キャツアイ・受け取り役の人)→ `ACTORS` に何行でも足せる形にしてあるので、後から増減自由。
