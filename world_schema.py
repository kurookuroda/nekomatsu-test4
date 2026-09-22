"""
nekomatsu-test3 データ構造 草案(フェーズ1〜4) 修正版

いまの catalog.py と同じ「タプルの行を1つ足せば増やせる」スタイルを保ったまま、
猫の個性・訪問者(actor)・場所(place)を扱えるようにする試作です。

このファイル単体は Pyxel に依存しません。
本採用する場合は、この中身を catalog.py / game.py に少しずつ移していく想定です。

【今回の主な修正点】
- give() の _rewarded を catalog 定数ではなく state 側に移動
- state["pets"] を set で統一(セーブ時の型整合)
- validate_world() に FOODS / GOODS / TOYS との ID 衝突チェックを追加
- new_player_state() に「既存 new_state() と統合が必要」旨のコメントを追加
- apply_reward() の pets 初期化を set に変更
"""

# ---------------------------------------------------------------------------
# フェーズ1: 猫の個性・エサのタグ
# ---------------------------------------------------------------------------

DEFAULT_TRAITS = {"appetite": 0.5, "friendly": 0.5, "wary": 0.5}

# 猫: (ID, 名前, 紹介文, お宝, 個性の上書き辞書)
#   個性のキー: sex, traits({appetite, friendly, wary}), taste({タグ: 重み}),
#              affinity({同居する生き物のID: 重み}), strength, entry_chance, time_limit, fav_toy
CATS = [
    ('gordo', 'ゴードー', 'いつもあなたのごはんを食べにくる、いちばん手のかかる猫',
     '役に立たない木切れ(ゴードーだから)',
     {'sex': 'm', 'traits': {'appetite': 0.8, 'friendly': 0.4, 'wary': 0.3},
      'taste': {'meat': 1.0, 'fish': 0.2}}),
    ('tarawa', 'タラワ', '白い筋の入ったグレーの長毛で、灰色の目の猫。のんびりするのと、鳥を追いかけるのが好き',
     'アオカケスの羽根',
     {'strength': 6, 'sex': 'f', 'traits': {'appetite': 0.3, 'friendly': 0.2, 'wary': 0.6},
      'taste': {'grass': 1.0}, 'affinity': {'turtle': 0.8}}),
]

# エサ: (ID, 名前, 価格, 通貨, もつ時間(分), 好みタグ, 説明)
# 【注意】game.py の _food() / load_catalog() も tags 対応に修正が必要
FOODS = [
    ('dry_food', 'ドライフード', 10, 's', 300, {'meat': 0.5, 'grain': 0.5},
     'ごく普通のドライフード。カリカリでシンプルな味。'),
    ('wet_food', 'ウェットフード缶', 2, 'g', 300, {'fish': 1.0},
     'ごく普通のウェットフード。においが強烈!'),
]


def taste_score(cat_taste, food_tags):
    """猫の好み(taste)とエサのタグ(tags)から、相性(0以上)を出す。"""
    if not cat_taste or not food_tags:
        return 0.5  # 情報がなければ中庸
    return sum(cat_taste.get(tag, 0.0) * weight for tag, weight in food_tags.items())


# ---------------------------------------------------------------------------
# フェーズ2: 条件判定(ショップ解放・訪問者の出現・鎖の次の一手、共通で使う)
# ---------------------------------------------------------------------------

def meets(state, requires):
    """state が requires を満たしているか。requires は None なら常に True。
    【注意】state["ever_had"] / state["flags"] は set として保持すること。
           game.py の dumps/loads の _sanitize で set 化の対象に追加が必要。"""
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


LEVEL_GAINS = {
    "met_new_cat": 1,
    "chain_step": 3,
    "stage_unlocked": 10,
}


def gain_level(state, reason):
    state["level"] = state.get("level", 0) + LEVEL_GAINS.get(reason, 0)


def new_player_state(player_name, now):
    """プレイヤー名を含む、新規セーブの雛形(フェーズ2以降の追加分だけ)。
    【注意】これは「追加分」のみ。既存の game.new_state(now) と統合して使うこと。
           統合例:
           state = game.new_state(now)
           state.update(new_player_state("黒いネコちゃん", now))"""
    return {
        "player_name": player_name,
        "level": 0,
        "ever_had": set(),
        "flags": set(),
        "met_actors": {},
        "created_at": now,
        "log": [],
    }


# ---------------------------------------------------------------------------
# フェーズ3: 訪問者・人・物(取引品)・ギフトの鎖
# ---------------------------------------------------------------------------

# 物(取引品。庭には置かない): (ID, 名前, 好みタグ, 説明)
GOODS = [
    ('smartphone', 'スマホ', {'electronics': 1.0}, '使い古しのスマートフォン。'),
    ('laptop', 'パソコン', {'electronics': 1.0}, '使い古しのノートパソコン。'),
    ('sweets', 'お菓子', {'sweets': 1.0}, '素朴な焼き菓子。'),
    ('amulet', 'お守り', {}, '古びたお守り。'),
]

# 訪問者・人: (ID, 種類, 名前, 紹介文, 個性の上書き辞書)
#   種類: "visitor"(通り過ぎるだけ) / "person"(居着く・ギフトを受け取る)
#   個性のキー:
#     habitat: 出現しうる場所のIDリスト
#     requires: 出現条件(meets() に渡す辞書)
#     gifts: [(outcome, 重み), ...]  visitor が帰るときの抽選
#     wants: {タグ: 重み}            person が好む物のタグ
#     one_time_reward: {..., "unlocks": 次のID}  最初にwantsを満たす物を渡されたときだけ
#   outcome の形式: "item:xxx" / "creature:xxx" / "flag:xxx" / "stage:xxx"
ACTORS = [
    ('catseye_a', 'visitor', 'キャツアイの誰か',
     '使い古し電子機器を引き取って売り買いしている。お金にはこだわらず、猫を愛している。',
     {'habitat': ['mansion'], 'requires': {'level': 5},
      'gifts': [('item:smartphone', 0.5), ('item:laptop', 0.2), ('item:sweets', 0.3)]}),

    ('jiro', 'person', 'じろうさん', '...',
     {'habitat': ['mansion'], 'requires': {'items': ['smartphone']},
      'wants': {'electronics': 1},
      'one_time_reward': {'creature': 'turtle', 'unlocks': 'obaachan'}}),

    ('obaachan', 'person', 'おばあちゃん', '...',
     {'habitat': ['mansion'], 'requires': {'flag': 'unlocked_obaachan'},
      'wants': {'sweets': 1},
      'one_time_reward': {'item': 'amulet', 'unlocks': 'stage:mansion2'}}),
]


def parse_outcome(outcome):
    """'item:smartphone' -> ('item', 'smartphone') のように分解する。"""
    kind, _, value = outcome.partition(":")
    return kind, value


def apply_reward(state, reward, rng):
    """one_time_reward / gifts の抽選結果を state に反映し、unlocks があればフラグを立てる。
    【修正】state["pets"] は set で統一(セーブ時の型整合)。"""
    if "creature" in reward:
        state.setdefault("pets", set()).add(reward["creature"])
    if "item" in reward:
        state.setdefault("owned_goods", set()).add(reward["item"])
        state.setdefault("ever_had", set()).add(reward["item"])
    unlocks = reward.get("unlocks")
    if unlocks:
        state.setdefault("flags", set()).add("unlocked_" + unlocks)
        gain_level(state, "chain_step")


def give(state, actor_def, item_id, rng):
    """actor_def(定義側の辞書)に item_id をあげる。好みに合うほど信頼(trust)が上がる。
    【修正】_rewarded は catalog 定数ではなく state 側に持つ(actor_id を set に保存)。"""
    goods = state.get("owned_goods", set())
    if item_id not in goods:
        return {"ok": False, "code": "not_owned"}
    goods.discard(item_id)

    actor_id = actor_def["id"] if isinstance(actor_def, dict) else actor_def[0]
    wants = actor_def.get("wants", {}) if isinstance(actor_def, dict) else actor_def[4].get("wants", {})

    item = next(g for g in GOODS if g[0] == item_id)
    _, _, item_tags, _ = item
    score = sum(wants.get(tag, 0) * w for tag, w in item_tags.items())

    state["trust_person"] = state.get("trust_person", {})
    state["trust_person"][actor_id] = state["trust_person"].get(actor_id, 0) + score

    # _rewarded は state 側に持つ(catalog 定数を書き換えない)
    rewarded = state.setdefault("_rewarded_actors", set())
    reward = None
    if score > 0 and actor_id not in rewarded:
        reward_def = actor_def.get("one_time_reward", {}) if isinstance(actor_def, dict) else actor_def[4].get("one_time_reward", {})
        reward = reward_def
        if reward:
            apply_reward(state, reward, rng)
            rewarded.add(actor_id)

    return {"ok": True, "code": "given", "reward": reward}


# ---------------------------------------------------------------------------
# フェーズ4: 場所(庭・屋敷)
# ---------------------------------------------------------------------------

# 場所: (ID, 表示名, マス数, 水辺の種類, 解放条件)
PLACES = [
    ('garden', '庭', 6, 'puddle', None),
    ('mansion', '屋敷', 12, 'pond', {'flag': 'unlocked_stage_mansion'}),
]


def validate_world(toy_ids=None):
    """ID の重複や、参照切れがないかを確認する(load_catalog の考え方を踏襲)。
    【修正】FOODS / GOODS の ID 重複チェック、TOYS との ID 衝突チェックを追加。"""
    errors = []

    cat_ids = [c[0] for c in CATS]
    if len(cat_ids) != len(set(cat_ids)):
        errors.append("CATS にIDの重複があります")

    food_ids = [f[0] for f in FOODS]
    if len(food_ids) != len(set(food_ids)):
        errors.append("FOODS にIDの重複があります")

    good_ids = {g[0] for g in GOODS}
    if len(good_ids) != len(GOODS):
        errors.append("GOODS にIDの重複があります")

    actor_ids = [a[0] for a in ACTORS]
    if len(actor_ids) != len(set(actor_ids)):
        errors.append("ACTORS にIDの重複があります")

    place_ids = {p[0] for p in PLACES}
    if len(place_ids) != len(PLACES):
        errors.append("PLACES にIDの重複があります")

    # TOYS(既存)との ID 衝突チェック
    if toy_ids is not None:
        for gid in good_ids:
            if gid in toy_ids:
                errors.append(f"GOODS の '{gid}' が TOYS とIDが衝突しています")
        for fid in food_ids:
            if fid in toy_ids:
                errors.append(f"FOODS の '{fid}' が TOYS とIDが突しています")

    # ACTORS の参照整合性チェック
    for actor_id, kind, name, desc, opts in ACTORS:
        for h in opts.get('habitat', []):
            if h not in place_ids:
                errors.append(f"{actor_id} の habitat '{h}' が PLACES にありません")
        for outcome, _w in opts.get('gifts', []):
            k, v = parse_outcome(outcome)
            if k == "item" and v not in good_ids:
                errors.append(f"{actor_id} の gifts '{outcome}' が GOODS にありません")
        reward = opts.get('one_time_reward')
        if reward and "item" in reward and reward["item"] not in good_ids:
            errors.append(f"{actor_id} の one_time_reward の item '{reward['item']}' が GOODS にありません")

    if errors:
        raise ValueError("\n".join(errors))


if __name__ == "__main__":
    validate_world()
    print("OK: world schema is consistent")
    print("taste_score sample (tarawa vs wet_food):",
          taste_score(CATS[1][4].get('taste', {}), FOODS[1][5]))
