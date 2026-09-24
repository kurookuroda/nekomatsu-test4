"""
ねこあつめ Pyxel 版 ― ゲームロジック(Pyxel に依存しない純粋な Python)

元のコンソール版(nekoatsume_py)の update.py / yard.py / buy_menu.py の挙動を、
表示や入力から切り離して移植したもの。UI は nekoatsume.py 側が担当する。

時間モデル
    1 tick = 60 秒(実時間)。advance() が「前回から経過した実時間」ぶんの tick を進める。
    起動時の一括計算(離席中の分)も、起動中のリアルタイム進行も、同じ関数で処理する。

元のコードからの意図的な変更点(README にも記載)
    1. 庭の容量判定を `<` から `<=` にした(元は 6 マスあっても 5 マスしか使えなかった)
    2. 大型キャットハウスをサイズ 7 → 6 にした(元は置けず、エサ扱いで購入されるバグがあった)
    3. アイテム種別(toy / food)を size の閾値ではなく kind で判定する
    4. 内部IDと表示名を分離した(セーブデータのキーは ID)
    5. おもちゃを庭から外したとき、遊んでいた猫はさかなを置いて帰る(元は無報酬で追い出していた)
    6. エサを置き換えるとき、残りが捨てられることを確認する(set_food が need_confirm を返し、UI がダイアログを出す)

規模への備え(猫が1000匹、商品が数百種類になっても困らないように)
    - アイテムと猫のデータは catalog.py の表にある(コードに埋め込まない)。load_catalog() で差し替えもできる
    - セーブに入る猫の状態は「出会った猫」だけ(未発見の猫は状態を持たない)。出会った順は met_order
    - 猫の来訪判定は、エサとおもちゃがあるときだけ行う。候補が多いときは順番をシャッフルして偏りをなくす
    - ショップの絞り込み・並べ替えは shop_ids() にまとめた(UI は表示だけ)
"""

import json
import random
import time
from collections import namedtuple

import catalog

VERSION = 1

SPACE = 6                      # 庭のマス数
TICK_SECONDS = 60              # 1 tick の実時間
MAX_CATCHUP_TICKS = 60 * 24 * 30   # 極端に長い離席・時計ずれの上限(30日分)
TREASURE_MINUTES = 3000        # 累計滞在がこれを超えるとお宝を持ってくる
GOLD_ONE_IN = 30               # 報酬が金になる確率(1/N)
WEEK_SECONDS = 7 * 24 * 3600

DEFAULT_TRAITS = {"appetite": 0.5, "friendly": 0.5, "wary": 0.5}   # 個性の既定値(0.0〜1.0)
FOOD_CONSUME_PER_APPETITE = 1.0    # appetite=1.0 の猫が1tickで食べるエサの量
FULLNESS_PER_FOOD_UNIT = 0.02      # 食べた量 → 満腹度(0〜1)への変換率
FULLNESS_DECAY_PER_TICK = 0.01     # 何も食べていない間、1tickごとに満腹度が下がる速さ

Result = namedtuple("Result", "ok code msg")


# ---------------------------------------------------------------- カタログ
def _toy(name, cost, cur, size, desc):
    return {"kind": "toy", "name": name, "cost": cost, "cur": cur, "size": size, "desc": desc}


def _food(name, cost, cur, amount, tags, desc):
    return {"kind": "food", "name": name, "cost": cost, "cur": cur, "size": amount,
            "tags": dict(tags or {}), "desc": desc}


def _cat(name, desc, treasure, strength=5, entry_chance=0.1, time_limit=30, fav_toy="", exclusive=False,
         voice="", traits=None, taste=None, sex=None, affinity=None):
    return {"name": name, "desc": desc, "treasure": treasure, "strength": strength,
            "entry_chance": entry_chance, "time_limit": time_limit,
            "fav_toy": fav_toy, "exclusive": exclusive, "voice": voice,
            "traits": dict(traits) if traits else dict(DEFAULT_TRAITS),
            "taste": dict(taste or {}), "sex": sex, "affinity": dict(affinity or {})}


def taste_score(cat_taste, food_tags):
    """猫の好み(taste)とエサの好みタグ(food_tags)の一致度。情報が無ければ中立の 0.5。"""
    if not cat_taste or not food_tags:
        return 0.5
    return sum(cat_taste.get(tag, 0.0) * weight for tag, weight in food_tags.items())


# load_catalog() が埋める。他のモジュールは game.ITEMS のように、使う時に参照すること(差し替えに追従するため)
ITEMS = {}          # アイテムID -> 仕様(おもちゃとエサ。表の並び順)
TOYS = {}
FOODS = {}
IDS_BY_KIND = {}    # 種別 -> アイテムIDのリスト(表の並び順)
CATS = {}           # 猫ID -> 仕様(表の並び順)
CATEGORIES = []     # ショップの種別 [(種別ID, 表示名)]
GOODS = {}          # 物(取引品)ID -> 仕様
ACTORS = {}         # 訪問者・人ID -> 仕様(表の並び順)
CATALOG_VERSION = 0     # load_catalog() のたびに増える(UI 側のキャッシュ無効化用)


def _good(name, tags, desc):
    return {"name": name, "tags": dict(tags or {}), "desc": desc}


def _actor(kind, name, desc, requires=None, wants=None, one_time_reward=None,
           milestones=None, casual_gifts=None):
    return {"kind": kind, "name": name, "desc": desc, "requires": requires,
            "wants": dict(wants or {}),
            "one_time_reward": dict(one_time_reward) if one_time_reward else None,
            "milestones": list(milestones or []), "casual_gifts": list(casual_gifts or [])}


def load_catalog(toys, foods, cats, categories, goods=(), actors=()):
    """アイテムと猫、物・訪問者/人のデータ表を読み込む(既定は catalog.py)。
    ID の重複や不正な値は ValueError。"""
    global ITEMS, TOYS, FOODS, IDS_BY_KIND, CATS, CATEGORIES, GOODS, ACTORS, CATALOG_VERSION
    items, cat_specs = {}, {}
    for row in toys:
        iid = row[0]
        if iid in items:
            raise ValueError("duplicate item id: %s" % iid)
        items[iid] = _toy(*row[1:])
    for row in foods:
        iid = row[0]
        if iid in items:
            raise ValueError("duplicate item id: %s" % iid)
        items[iid] = _food(*row[1:])
    for row in cats:
        cid, name, desc, treasure = row[:4]
        if cid in cat_specs:
            raise ValueError("duplicate cat id: %s" % cid)
        cat_specs[cid] = _cat(name, desc, treasure, **(row[4] if len(row) > 4 else {}))
    for iid, it in items.items():
        if it["cur"] not in ("s", "g") or it["cost"] <= 0 or it["size"] < 1:
            raise ValueError("bad item: %s" % iid)
        if it["kind"] == "toy" and it["size"] > SPACE:
            raise ValueError("toy does not fit in the yard: %s" % iid)
    kinds = [k for k, _label in categories]
    ids_by_kind = {k: [] for k in kinds}
    for iid, it in items.items():
        if it["kind"] not in ids_by_kind:
            raise ValueError("item %s has no category" % iid)
        ids_by_kind[it["kind"]].append(iid)

    good_specs = {}
    for row in goods:
        gid, name, tags, desc = row
        if gid in good_specs:
            raise ValueError("duplicate good id: %s" % gid)
        if gid in items:
            raise ValueError("good id collides with an item id: %s" % gid)
        good_specs[gid] = _good(name, tags, desc)

    actor_specs = {}
    for row in actors:
        aid = row[0]
        if aid in actor_specs:
            raise ValueError("duplicate actor id: %s" % aid)
        actor_specs[aid] = _actor(*row[1:4], **(row[4] if len(row) > 4 else {}))

    ITEMS = items
    TOYS = {k: v for k, v in items.items() if v["kind"] == "toy"}
    FOODS = {k: v for k, v in items.items() if v["kind"] == "food"}
    IDS_BY_KIND = ids_by_kind
    CATS = cat_specs
    CATEGORIES = list(categories)
    GOODS = good_specs
    ACTORS = actor_specs
    CATALOG_VERSION += 1


load_catalog(catalog.TOYS, catalog.FOODS, catalog.CATS, catalog.CATEGORIES,
             catalog.GOODS, catalog.ACTORS)


def cur_name(cur):
    return "銀" if cur == "s" else "金"


def price_text(item_id):
    it = ITEMS[item_id]
    return "{0}{1}".format(cur_name(it["cur"]), it["cost"])


# ---------------------------------------------------------------- 状態
def _new_cat():
    return {"in_yard": False, "toy": "", "time_in_yard": 0, "total_time": 0,
            "given_treasure": False, "met": False, "fullness": 0.5}


def new_state(now=None):
    now = time.time() if now is None else now
    return {
        "version": VERSION,
        "s_fish": 300,
        "g_fish": 10,
        "owned_toys": [],          # 持っているおもちゃID
        "yard": [],                # 庭に置いてあるおもちゃID(置いた順)
        "occ": {},                 # おもちゃID -> 遊んでいる猫ID(入った順)
        "food_stock": {},          # エサID -> 個数
        "food": "",                # 庭に出ているエサID
        "food_remaining": 0,       # 残り量(庭にいる猫が食べた分だけ減る。時間では減らない)
        "cats": {},                # 出会った猫だけ(猫ID -> 状態)。猫が何匹いても、セーブは出会った分だけで済む
        "met_order": [],           # 出会った順(図鑑の並び)
        "pending_money": [],       # [猫ID, 量, "s"/"g"]
        "pending_treasures": [],   # 猫ID
        "player_name": "",         # プレイヤー名(表示用)
        "level": 0,                # レベル(行動に応じて gain_level() で上がる)
        "ever_had": set(),         # これまでに手に入れたことがある物のID(一度でも持てば残る)
        "flags": set(),            # 立てたフラグ(文字列)。解放条件などに使う
        "met_actors": {},          # 出会った訪問者・人(ID -> {trust, milestones_done, rewarded})
        "owned_goods": set(),      # いま持っている物(GOODS のID)。庭には置かない、あげる専用の所持品
        "pets": set(),             # もらった生き物(亀など)。今はデータとして持つだけ
        "log": [],                 # 日時ログ [ [last_tick時点の時刻, 種類, 詳細], ... ] 直近 LOG_MAX 件
        "created_at": now,
        "last_tick": now,
        "last_seen": now,
    }


def space_used(state):
    return sum(TOYS[t]["size"] for t in state["yard"])


def occupants(state, toy_id):
    return list(state["occ"].get(toy_id, []))


def ensure_cat(state, cid):
    """猫の状態を返す。まだ無ければ既定値で作る(出会い済みにはしない)。"""
    c = state["cats"].get(cid)
    if c is None:
        c = state["cats"][cid] = _new_cat()
    return c


def met_list(state):
    """出会った猫を、出会った順に返す(図鑑の並び)。"""
    return list(state["met_order"])


def cats_in_yard(state):
    return [cid for cid, c in state["cats"].items() if c["in_yard"]]


def fish(state, cur):
    return state[cur + "_fish"]


# ---------------------------------------------------------------- レベル・条件判定・ログ
LOG_MAX = 200


def _log(state, kind, detail=None):
    """日時ログに1件追加する(時刻はゲーム内時計 last_tick を使う)。直近 LOG_MAX 件だけ残す。"""
    log = state.setdefault("log", [])
    log.append([state["last_tick"], kind, detail])
    if len(log) > LOG_MAX:
        del log[: len(log) - LOG_MAX]


LEVEL_GAINS = {
    "met_new_cat": 1,
    "chain_step": 3,           # 訪問者・人の鎖が1段階進んだとき(unlocks が付いた reward を受け取った)
}


def gain_level(state, reason):
    """reason に応じてレベルを上げ、ログに残す(未知の reason は 0 なので何も起きない)。"""
    gained = LEVEL_GAINS.get(reason, 0)
    if gained <= 0:
        return
    state["level"] = state.get("level", 0) + gained
    _log(state, "level_up", {"reason": reason, "level": state["level"]})


def meets(state, requires):
    """state が requires(複合条件の辞書)を満たしているか。requires が空/None なら常に True。
    使える条件キー: level(以上か) / items(ever_had に全部あるか) / met(met_actors の人数以上か) / flag(立っているか)。"""
    if not requires:
        return True
    if "level" in requires and state.get("level", 0) < requires["level"]:
        return False
    if "items" in requires and not set(requires["items"]) <= state.get("ever_had", set()):
        return False
    if "met" in requires and len(state.get("met_actors", {})) < requires["met"]:
        return False
    if "flag" in requires and requires["flag"] not in state.get("flags", set()):
        return False
    return True


def set_player_name(state, name):
    """プレイヤー名を設定する(前後の空白を除き、20文字まで)。"""
    name = "" if name is None else str(name).strip()[:20]
    state["player_name"] = name
    return Result(True, "ok", "")


# ---------------------------------------------------------------- 訪問者・人・物(取引品)
CASUAL_GIFT_CHANCE = 0.02      # 1tickあたり、casual_gifts を渡すか判定する確率


def parse_outcome(outcome):
    """'item:smartphone' -> ('item', 'smartphone') のように分解する。"""
    kind, _, value = outcome.partition(":")
    return kind, value


def _weighted_choice(pairs, rng):
    """[(値, 重み), ...] から重み付きで1つ選ぶ。重みの合計が0以下なら None。"""
    total = sum(w for _v, w in pairs)
    if total <= 0:
        return None
    r = rng.random() * total
    upto = 0.0
    for value, w in pairs:
        upto += w
        if r <= upto:
            return value
    return pairs[-1][0]


def apply_reward(state, reward, rng=random):
    """milestones / one_time_reward の中身を state に反映する。
    item は所持品に、creature はペットに加わり、unlocks があればフラグを立ててレベルも上がる。"""
    if not reward:
        return
    if "item" in reward:
        state["owned_goods"].add(reward["item"])
        state["ever_had"].add(reward["item"])
    if "creature" in reward:
        state["pets"].add(reward["creature"])
    unlocks = reward.get("unlocks")
    if unlocks:
        state["flags"].add("unlocked_" + unlocks)
        gain_level(state, "chain_step")


def _tick_actors(state, rng, events):
    """訪問者・人の出現判定、一度きりの重要な贈り物(milestones)、たまの贈り物(casual_gifts)を進める。"""
    for actor_id, actor in ACTORS.items():
        met = state["met_actors"].get(actor_id)
        if met is None:
            if not meets(state, actor["requires"]):
                continue
            met = {"trust": 0.0, "milestones_done": [], "rewarded": False}
            state["met_actors"][actor_id] = met
            _log(state, "met_actor", actor_id)
            events.append(("met_actor", actor_id))

        for i, (req, reward) in enumerate(actor["milestones"]):
            if i in met["milestones_done"]:
                continue
            if meets(state, req):
                apply_reward(state, reward, rng)
                met["milestones_done"].append(i)
                _log(state, "milestone_gift", {"actor": actor_id, "index": i, "reward": reward})
                events.append(("milestone_gift", actor_id, reward))

        gifts = actor["casual_gifts"]
        if gifts and rng.random() < CASUAL_GIFT_CHANCE:
            outcome = _weighted_choice(gifts, rng)
            if outcome:
                kind, value = parse_outcome(outcome)
                if kind == "item":
                    state["owned_goods"].add(value)
                    state["ever_had"].add(value)
                    _log(state, "casual_gift", {"actor": actor_id, "item": value})
                    events.append(("casual_gift", actor_id, value))


def give(state, actor_id, item_id, rng=random):
    """出会った人・訪問者(actor_id)に、持っている物(item_id)をあげる。
    好みに合うほど信頼(trust)が上がり、初めて好みに合う物をもらったときだけ one_time_reward が渡る。
    2回目以降に好みの物をあげても、reward は無く、反応(code/msg)が変わる。"""
    actor = ACTORS.get(actor_id)
    met = state["met_actors"].get(actor_id)
    if actor is None or met is None:
        return Result(False, "not_met", "まだ出会っていません。")
    if item_id not in state["owned_goods"] or item_id not in GOODS:
        return Result(False, "not_owned", "持っていません。")

    item = GOODS[item_id]
    score = sum(actor["wants"].get(tag, 0.0) * w for tag, w in item["tags"].items())
    met["trust"] = met.get("trust", 0.0) + score
    state["owned_goods"].discard(item_id)
    _log(state, "gave_item", {"actor": actor_id, "item": item_id, "score": score})

    if score <= 0:
        return Result(True, "given_no_interest",
                       "{0}に{1}をあげたけど、あまり興味は無さそうだった。".format(actor["name"], item["name"]))
    if not met["rewarded"] and actor["one_time_reward"]:
        apply_reward(state, actor["one_time_reward"], rng)
        met["rewarded"] = True
        return Result(True, "given_reward", "{0}はとても喜んで、お礼に何かをくれた!".format(actor["name"]))
    return Result(True, "given_thanks", "{0}は喜んで受け取ってくれた。「ありがとう」".format(actor["name"]))


# ---------------------------------------------------------------- 時間経過
def advance(state, now, rng=random):
    """実時間 now に合わせて tick を進める。

    戻り値: {"ticks": 進めたtick数, "visits": 来訪回数, "events": 直近のイベント(最大50件)}
    経過が 1 tick 未満なら何も起きない(端数は次回に持ち越す)。
    """
    elapsed = now - state["last_tick"]
    if elapsed < 0:                      # 時計が巻き戻された
        state["last_tick"] = now
        elapsed = 0
    n = int(elapsed // TICK_SECONDS)
    events = []
    if n > MAX_CATCHUP_TICKS:
        n = MAX_CATCHUP_TICKS
        state["last_tick"] = now
    else:
        state["last_tick"] += n * TICK_SECONDS
    for _ in range(n):
        tick(state, rng, events)
    state["last_seen"] = now
    visits = sum(1 for e in events if e[0] == "arrive")
    return {"ticks": n, "visits": visits, "events": events[-50:]}


def resume(state, now, rng=random):
    """アプリ起動時の処理。離席中の分を進め、起動ボーナスのお宝抽選を行う。"""
    prev_seen = state["last_seen"]
    report = advance(state, now, rng)
    report["bonus_treasure"] = launch_bonus(state, prev_seen, now, rng)
    return report


def tick(state, rng=random, events=None):
    """1 分ぶん進める(元の update.tick と同じ順序)。"""
    ev = events if events is not None else []
    cats = state["cats"]
    _decay_fullness(state)
    # 「庭にいる猫」を先に確定する(この tick で帰った猫は同 tick に再入場しない)
    in_yard = set(cats_in_yard(state))
    for cid in list(in_yard):
        c = cats[cid]
        c["time_in_yard"] += 1
        if _time_to_leave(c, CATS[cid], rng):
            _leave(state, cid, rng, ev)
    if state["food"]:
        if state["yard"]:                      # おもちゃが無ければ、誰も来ないので判定しない
            candidates = [cid for cid in CATS if cid not in in_yard]
            if len(candidates) > 8:            # 猫が多いとき、先頭の猫ばかり席を取らないように順番を混ぜる
                rng.shuffle(candidates)
            for cid in candidates:
                if rng.random() < _entry_probability(state, cid):
                    toy = _pick_toy(state, cid, rng)
                    if toy is None:
                        continue
                    if len(state["occ"][toy]) < TOYS[toy]["size"]:
                        _join(state, cid, toy, ev)
                    else:
                        _try_push(state, cid, toy, rng, ev)
        _consume_food(state, ev)
    _tick_actors(state, rng, ev)


def _entry_probability(state, cid):
    """来やすさ = 基本の entry_chance × 好み補正(taste) × 満腹度補正(fullness)。"""
    spec = CATS[cid]
    food_tags = FOODS[state["food"]]["tags"] if state["food"] else {}
    taste_factor = 0.5 + taste_score(spec.get("taste"), food_tags)   # 好みが中立なら ×1.0
    c = state["cats"].get(cid)
    fullness = c["fullness"] if c else 0.5
    fullness_factor = 1.0 - fullness * 0.6                          # 満腹(1.0)なら ×0.4、空腹(0.0)なら ×1.0
    prob = spec["entry_chance"] * taste_factor * fullness_factor
    return max(0.0, min(1.0, prob))


def _time_to_leave(cat, spec, rng):
    upper = rng.randint(10, 20)
    lower = rng.randint(2, 7)
    return rng.randint(lower, upper) + cat["time_in_yard"] > spec["time_limit"]


def _pick_toy(state, cid, rng):
    toys = state["yard"]
    if not toys:
        return None
    spec = CATS[cid]
    if spec["exclusive"]:
        return spec["fav_toy"] if spec["fav_toy"] in toys else None
    return rng.choice(toys)


def _join(state, cid, toy, events):
    c = ensure_cat(state, cid)
    state["occ"][toy].append(cid)
    c["in_yard"] = True
    c["toy"] = toy
    if not c["met"]:                       # 図鑑での位置は「はじめて庭に来た順」で、このとき決まる
        c["met"] = True
        state["met_order"].append(cid)
        events.append(("met", cid))
        _log(state, "met_cat", cid)
        gain_level(state, "met_new_cat")
    events.append(("arrive", cid, toy))
    if c["total_time"] > TREASURE_MINUTES and not c["given_treasure"]:
        c["given_treasure"] = True
        state["pending_treasures"].append(cid)
        events.append(("treasure", cid))


def _try_push(state, cid, toy, rng, events):
    for other in list(state["occ"][toy]):
        if CATS[other]["strength"] < CATS[cid]["strength"]:
            _leave(state, other, rng, events)
            _join(state, cid, toy, events)
            return


def _leave(state, cid, rng, events):
    c = state["cats"][cid]
    toy = c["toy"]
    if cid in state["occ"].get(toy, []):
        state["occ"][toy].remove(cid)
    amount = int(round(c["time_in_yard"] * (rng.randint(5, 10) / 10.0)))
    cur = "g" if rng.randint(1, GOLD_ONE_IN) == 1 else "s"
    state["pending_money"].append([cid, amount, cur])
    events.append(("leave", cid, toy, amount, cur))
    c["total_time"] += c["time_in_yard"]
    c["time_in_yard"] = 0
    c["in_yard"] = False
    c["toy"] = ""


def _decay_fullness(state):
    """出会った猫は、食べていない間ずっと少しずつ満腹度が下がる。"""
    for c in state["cats"].values():
        c["fullness"] = max(0.0, c["fullness"] - FULLNESS_DECAY_PER_TICK)


def _consume_food(state, events):
    """エサは時間経過でなく、庭にいる猫が食べた分だけ減る。食べた猫は満腹度が上がる。"""
    if state["food_remaining"] <= 0:
        state["food"] = ""
        return
    in_yard = cats_in_yard(state)
    if not in_yard:
        return                                  # 食べる猫がいなければ減らない
    remaining = state["food_remaining"]
    eaten_total = 0.0
    for cid in in_yard:
        if remaining - eaten_total <= 0:
            break
        appetite = CATS[cid]["traits"].get("appetite", DEFAULT_TRAITS["appetite"])
        eaten = min(appetite * FOOD_CONSUME_PER_APPETITE, remaining - eaten_total)
        if eaten <= 0:
            continue
        eaten_total += eaten
        c = state["cats"][cid]
        c["fullness"] = min(1.0, c["fullness"] + eaten * FULLNESS_PER_FOOD_UNIT)
    if eaten_total > 0:
        state["food_remaining"] = max(0.0, remaining - eaten_total)
        if state["food_remaining"] <= 0:
            state["food"] = ""
            events.append(("food_out",))


def launch_bonus(state, prev_seen, now, rng=random):
    """起動時のお宝抽選(元の bestow_treasures)。離席が長いほど当たりやすい(5%〜10%)。"""
    not_given = [cid for cid, c in state["cats"].items()
                 if c["total_time"] > 0 and not c["given_treasure"]]
    if not not_given:
        return None
    absent = max(0.0, now - prev_seen) / WEEK_SECONDS
    prob = 0.05 + 0.05 * min(1.0, absent)
    if rng.random() >= prob:
        return None
    giver = rng.choice(not_given)
    state["cats"][giver]["given_treasure"] = True
    state["pending_treasures"].append(giver)
    return giver


# ---------------------------------------------------------------- プレイヤー操作
def buy(state, item_id):
    it = ITEMS.get(item_id)
    if it is None:
        return Result(False, "unknown", "そんな商品はありません")
    if it["kind"] == "toy" and item_id in state["owned_toys"]:
        return Result(False, "owned", "もう持っています")
    key = it["cur"] + "_fish"
    if state[key] < it["cost"]:
        return Result(False, "no_money", "ごめんなさい、お金が足りません!")
    state[key] -= it["cost"]
    if it["kind"] == "toy":
        state["owned_toys"].append(item_id)
    else:
        state["food_stock"][item_id] = state["food_stock"].get(item_id, 0) + 1
    return Result(True, "ok", "まいど! すばらしい選択です!")


def place_toy(state, toy_id):
    if toy_id not in state["owned_toys"]:
        return Result(False, "not_owned", "そのおもちゃは持っていません")
    if toy_id in state["yard"]:
        return Result(False, "placed", "もう庭に置いてあります")
    if space_used(state) + TOYS[toy_id]["size"] > SPACE:
        return Result(False, "no_room", "庭がいっぱいです。先にどれかを外してください")
    state["yard"].append(toy_id)
    state["occ"][toy_id] = []
    return Result(True, "ok", "{0}を庭に置きました".format(TOYS[toy_id]["name"]))


def remove_toy(state, toy_id, rng=random, events=None):
    if toy_id not in state["yard"]:
        return Result(False, "not_placed", "庭に置いていません")
    ev = events if events is not None else []
    for cid in list(state["occ"].get(toy_id, [])):
        _leave(state, cid, rng, ev)
    state["yard"].remove(toy_id)
    state["occ"].pop(toy_id, None)
    return Result(True, "ok", "{0}を庭から外しました".format(TOYS[toy_id]["name"]))


def set_food(state, food_id, force=False):
    if food_id not in FOODS or state["food_stock"].get(food_id, 0) <= 0:
        return Result(False, "no_stock", "そのエサは持っていません")
    if state["food_remaining"] > 0 and not force:
        return Result(False, "need_confirm",
                      "庭のエサ(残り{0})は捨てられます。置き換えますか?".format(round(state["food_remaining"])))
    state["food_stock"][food_id] -= 1
    if state["food_stock"][food_id] <= 0:
        del state["food_stock"][food_id]
    state["food"] = food_id
    state["food_remaining"] = FOODS[food_id]["size"]
    return Result(True, "ok", "{0}を置きました(残り{1})".format(FOODS[food_id]["name"], round(state["food_remaining"])))


SHOP_FILTERS = (("all", "すべて"), ("buyable", "買える"), ("unowned", "未所持"))
SHOP_SORTS = (("catalog", "標準"), ("price_asc", "安い順"), ("price_desc", "高い順"))


def shop_ids(state, kind=None, filt="all", sort="catalog"):
    """ショップに並べるアイテムIDを、絞り込み・並べ替え済みで返す。
    kind: 種別ID(おもちゃ / エサ など)。None なら、すべての種別をまとめて表の順で返す
    filt: all=すべて / buyable=いま買える(所持金が足り、持っていない) / unowned=持っていない
    sort: catalog=表の順 / price_asc=安い順 / price_desc=高い順(銀→金の順に、値段で比べる)
    """
    ids = list(ITEMS) if kind is None else list(IDS_BY_KIND.get(kind, []))
    if filt != "all":
        owned = set(state["owned_toys"])
        stock = state["food_stock"]

        def is_toy(i):
            return ITEMS[i]["kind"] == "toy"

        def have(i):
            return (i in owned) if is_toy(i) else stock.get(i, 0) > 0

        if filt == "unowned":
            ids = [i for i in ids if not have(i)]
        elif filt == "buyable":
            ids = [i for i in ids
                   if not (is_toy(i) and have(i)) and state[ITEMS[i]["cur"] + "_fish"] >= ITEMS[i]["cost"]]
    if sort in ("price_asc", "price_desc"):
        ids.sort(key=lambda i: (0 if ITEMS[i]["cur"] == "s" else 1, ITEMS[i]["cost"]),
                 reverse=(sort == "price_desc"))
    return ids


def collect(state):
    """猫たちが置いていったさかなを受け取る。[(猫ID, 量, 通貨)] を返す。"""
    got = [tuple(m) for m in state["pending_money"]]
    state["pending_money"] = []
    for _cid, amount, cur in got:
        state[cur + "_fish"] += amount
    return got


def collect_treasures(state):
    got = list(state["pending_treasures"])
    state["pending_treasures"] = []
    return got


def treasures_owned(state):
    return [cid for cid, c in state["cats"].items() if c["given_treasure"]]


# ---------------------------------------------------------------- 保存・読み込み
_SET_FIELDS = ("ever_had", "flags", "owned_goods", "pets")


def dumps(state):
    out = dict(state)
    for key in _SET_FIELDS:
        if isinstance(out.get(key), set):
            out[key] = sorted(out[key])
    return json.dumps(out, ensure_ascii=False)


def loads(text, now=None):
    """JSON 文字列から状態を復元する。壊れた値は補正し、形式が違えば ValueError。"""
    raw = json.loads(text)
    if not isinstance(raw, dict) or raw.get("version") != VERSION:
        raise ValueError("unsupported save data")
    state = new_state(now)
    for k in state:
        if k in raw:
            state[k] = raw[k]
    _sanitize(state, raw)
    return state


def _int(v, default=0):
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return default


def _float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp01(v, default):
    v = _float(v, default)
    return max(0.0, min(1.0, v))


def _clean_met_actor(v):
    if not isinstance(v, dict):
        return {"trust": 0.0, "milestones_done": [], "rewarded": False}
    return {
        "trust": _float(v.get("trust"), 0.0),
        "milestones_done": [i for i in (v.get("milestones_done") or []) if isinstance(i, int)],
        "rewarded": bool(v.get("rewarded", False)),
    }


def _sanitize(state, raw):
    for key in ("s_fish", "g_fish"):
        state[key] = _int(state[key])
    state["food_remaining"] = max(0.0, _float(state["food_remaining"], 0.0))
    now = time.time()
    state["last_tick"] = _float(state["last_tick"], now)
    state["last_seen"] = _float(state["last_seen"], now)
    state["created_at"] = _float(state.get("created_at"), state["last_tick"])

    state["player_name"] = state["player_name"].strip()[:20] \
        if isinstance(state.get("player_name"), str) else ""
    state["level"] = _int(state.get("level", 0))
    for key in _SET_FIELDS:
        src = state.get(key)
        state[key] = set(x for x in src if isinstance(x, str)) if isinstance(src, (list, set)) else set()
    state["met_actors"] = {k: _clean_met_actor(v) for k, v in state["met_actors"].items() if isinstance(k, str)} \
        if isinstance(state.get("met_actors"), dict) else {}
    log = state.get("log")
    if isinstance(log, list):
        clean = [e for e in log if isinstance(e, list) and len(e) == 3]
        state["log"] = clean[-LOG_MAX:]
    else:
        state["log"] = []

    owned = []
    for t in state["owned_toys"] if isinstance(state["owned_toys"], list) else []:
        if t in TOYS and t not in owned:
            owned.append(t)
    state["owned_toys"] = owned

    yard = []
    for t in state["yard"] if isinstance(state["yard"], list) else []:
        if t in owned and t not in yard and sum(TOYS[x]["size"] for x in yard) + TOYS[t]["size"] <= SPACE:
            yard.append(t)
    state["yard"] = yard

    stock = {}
    if isinstance(state["food_stock"], dict):
        for k, v in state["food_stock"].items():
            if k in FOODS and _int(v) > 0:
                stock[k] = _int(v)
    state["food_stock"] = stock
    if state["food"] not in FOODS or state["food_remaining"] <= 0:
        state["food"], state["food_remaining"] = "", 0

    saved_cats = state["cats"] if isinstance(state["cats"], dict) else {}
    saved_occ = state["occ"] if isinstance(state["occ"], dict) else {}
    cats = {}
    for cid, src in saved_cats.items():
        if cid not in CATS or not isinstance(src, dict):
            continue
        c = _new_cat()
        c["in_yard"] = bool(src.get("in_yard", False))
        c["toy"] = src.get("toy", "") if isinstance(src.get("toy", ""), str) else ""
        c["time_in_yard"] = _int(src.get("time_in_yard", 0))
        c["total_time"] = _int(src.get("total_time", 0))
        c["given_treasure"] = bool(src.get("given_treasure", False))
        c["fullness"] = _clamp01(src.get("fullness", 0.5), 0.5)
        # met が無い旧セーブでも、遊んだ形跡があれば「出会い済み」扱いにする
        c["met"] = bool(src.get("met", False)) or c["in_yard"] \
            or c["total_time"] > 0 or c["given_treasure"]
        if c["met"]:                       # 出会っていない猫の状態は持たない(旧セーブの全員分の既定値は捨てる)
            cats[cid] = c
    met_order = []
    for cid in (state["met_order"] if isinstance(state["met_order"], list) else []):
        if cid in cats and cid not in met_order:
            met_order.append(cid)
    met_order.extend(cid for cid in cats if cid not in met_order)   # 順番が不明な旧セーブ分は、後ろに足す
    state["met_order"] = met_order
    occ = {t: [] for t in yard}
    order = []
    for t in yard:
        lst = saved_occ.get(t, [])
        if isinstance(lst, list):
            order.extend(cid for cid in lst if cid in cats)
    order.extend(cid for cid in cats if cid not in order)
    for cid in order:
        c = cats[cid]
        t = c["toy"]
        if c["in_yard"] and t in occ and cid not in occ[t] and len(occ[t]) < TOYS[t]["size"]:
            occ[t].append(cid)
        elif not (c["in_yard"] and t in occ and cid in occ[t]):
            c["in_yard"], c["toy"], c["time_in_yard"] = False, "", 0
    state["occ"] = occ
    state["cats"] = cats

    money = []
    for m in state["pending_money"] if isinstance(state["pending_money"], list) else []:
        if isinstance(m, (list, tuple)) and len(m) == 3 and m[0] in CATS and m[2] in ("s", "g"):
            money.append([m[0], _int(m[1]), m[2]])
    state["pending_money"] = money
    state["pending_treasures"] = [c for c in (state["pending_treasures"]
                                              if isinstance(state["pending_treasures"], list) else [])
                                  if c in CATS]