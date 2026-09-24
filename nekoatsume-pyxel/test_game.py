"""game.py のテスト。 実行: pytest -q"""
import json
import random
import statistics

import pytest

import game

T0 = 1_000_000.0


def fresh():
    return game.new_state(T0)


def stocked(toys=("rubber_ball", "yarn_ball", "cereal_box", "plastic_bucket", "paper_bag")):
    s = fresh()
    for t in toys:
        s["owned_toys"].append(t)
        assert game.place_toy(s, t).ok
    s["food_stock"]["dry_food"] = 1
    assert game.set_food(s, "dry_food").ok
    return s


# ---------------------------------------------------------------- 買い物・配置
def test_buy_toy_and_food():
    s = fresh()
    assert game.buy(s, "rubber_ball").ok
    assert s["s_fish"] == 295 and s["owned_toys"] == ["rubber_ball"]
    assert game.buy(s, "rubber_ball").code == "owned"          # おもちゃは1個だけ
    assert game.buy(s, "dry_food").ok and game.buy(s, "dry_food").ok
    assert s["food_stock"] == {"dry_food": 2}                  # エサは何個でも買える
    assert game.buy(s, "nothing").code == "unknown"


def test_buy_needs_money():
    s = fresh()
    assert game.buy(s, "laser_pointer").code == "no_money"     # 金125 > 所持10
    assert s["g_fish"] == 10


def test_space_is_really_six():
    """元のコードは < 判定で実質5マスだった。6マスまで使える。"""
    s = fresh()
    six = ["rubber_ball", "yarn_ball", "cereal_box", "plastic_bucket", "paper_bag", "tennis_ball"]
    s["owned_toys"] = list(six)
    for t in six:
        assert game.place_toy(s, t).ok
    assert game.space_used(s) == 6
    s["owned_toys"].append("fruit_box")
    assert game.place_toy(s, "fruit_box").code == "no_room"


def test_large_condo_is_placeable():
    s = fresh()
    s["owned_toys"] = ["large_condo"]
    assert game.place_toy(s, "large_condo").ok


def test_place_remove_and_occupants_pay_out():
    s = stocked(("rubber_ball",))
    rng = random.Random(1)
    game.ensure_cat(s, "gordo").update(in_yard=True, toy="rubber_ball", time_in_yard=10)
    s["occ"]["rubber_ball"] = ["gordo"]
    assert game.remove_toy(s, "rubber_ball", rng).ok
    assert not s["cats"]["gordo"]["in_yard"] and s["cats"]["gordo"]["total_time"] == 10
    assert len(s["pending_money"]) == 1                         # 外した猫もさかなを置いて帰る
    assert "rubber_ball" not in s["occ"]


def test_set_food_confirm_before_discarding():
    s = fresh()
    s["food_stock"] = {"dry_food": 2}
    assert game.set_food(s, "dry_food").ok
    s["food_remaining"] = 120
    r = game.set_food(s, "dry_food")
    assert r.code == "need_confirm" and s["food_remaining"] == 120 and s["food_stock"]["dry_food"] == 1
    assert game.set_food(s, "dry_food", force=True).ok
    assert s["food_remaining"] == 300 and "dry_food" not in s["food_stock"]
    assert game.set_food(s, "dry_food", force=True).code == "no_stock"


def test_collect():
    s = fresh()
    s["pending_money"] = [["gordo", 10, "s"], ["pukka", 3, "g"]]
    got = game.collect(s)
    assert got == [("gordo", 10, "s"), ("pukka", 3, "g")]
    assert (s["s_fish"], s["g_fish"]) == (310, 13) and s["pending_money"] == []


# ---------------------------------------------------------------- 時間経過
def test_no_visitors_without_food_or_toys():
    s = stocked()
    s["food"], s["food_remaining"] = "", 0
    game.advance(s, T0 + 3600, random.Random(1))
    assert game.cats_in_yard(s) == [] and s["pending_money"] == []
    s2 = fresh()
    s2["food_stock"]["dry_food"] = 1
    game.set_food(s2, "dry_food")
    game.advance(s2, T0 + 3600, random.Random(1))
    assert game.cats_in_yard(s2) == []                         # おもちゃがなければ来ない


def test_advance_counts_whole_ticks_and_carries_remainder():
    s = stocked()
    assert game.advance(s, T0 + 59)["ticks"] == 0
    assert game.advance(s, T0 + 60)["ticks"] == 1
    assert game.advance(s, T0 + 60 + 150)["ticks"] == 2       # 150秒=2tick+30秒持ち越し
    assert s["last_tick"] == T0 + 60 + 120


def test_clock_rewind_is_safe():
    s = stocked()
    r = game.advance(s, T0 - 5000)
    assert r["ticks"] == 0 and s["last_tick"] == T0 - 5000


def test_catchup_is_capped():
    s = stocked()
    r = game.advance(s, T0 + 10 ** 9, random.Random(1))
    assert r["ticks"] == game.MAX_CATCHUP_TICKS


def test_food_runs_out_eventually_during_active_play():
    """フェーズ1: エサはもう「経過時間」では減らない。おもちゃがあって猫が遊びに来る状況が続けば、
    いずれは食べ尽くされる、という点だけを確認する(何tick目に尽きるかは猫の来訪次第で決まらない)。"""
    s = stocked()
    r = game.advance(s, T0 + 60 * 600, random.Random(2))
    assert s["food"] == "" and s["food_remaining"] == 0
    assert any(e[0] == "food_out" for e in r["events"])


def test_food_is_not_consumed_without_cats_in_the_yard():
    """②エサは時間経過でなく、庭にいる猫が食べた分だけ減る"""
    s = fresh()
    s["food_stock"]["dry_food"] = 1
    game.set_food(s, "dry_food")
    before = s["food_remaining"]
    for _ in range(50):                       # おもちゃが無いので、誰も庭に来ない
        game.tick(s, random.Random(0))
    assert s["food_remaining"] == before


def test_food_is_consumed_by_appetite_and_raises_fullness():
    """②食べた猫の満腹度が上がり、その分だけエサが減る"""
    s = fresh()
    s["owned_toys"].append("rubber_ball")
    game.place_toy(s, "rubber_ball")
    game.ensure_cat(s, "gordo")["in_yard"] = True
    s["occ"]["rubber_ball"] = ["gordo"]
    s["food_stock"]["dry_food"] = 1
    game.set_food(s, "dry_food")
    before = s["food_remaining"]
    game.tick(s, random.Random(0))
    assert s["food_remaining"] < before
    assert s["cats"]["gordo"]["fullness"] > 0.5


def test_taste_affects_entry_probability():
    """①猫ごとにエサの好みで来訪率が変わる(ゴードーは魚より肉気味のドライフードが得意)"""
    s = fresh()
    s["food"], s["food_remaining"] = "dry_food", 300
    p_dry = game._entry_probability(s, "gordo")
    s["food"], s["food_remaining"] = "wet_food", 300
    p_wet = game._entry_probability(s, "gordo")
    assert p_dry > p_wet


def test_fullness_lowers_entry_probability():
    """③満腹の猫は来訪率が下がる"""
    s = fresh()
    s["food"], s["food_remaining"] = "dry_food", 300
    p_hungry = game._entry_probability(s, "gordo")
    game.ensure_cat(s, "gordo")["fullness"] = 1.0
    p_full = game._entry_probability(s, "gordo")
    assert p_full < p_hungry


# ---------------------------------------------------------------- フェーズ2: レベル・条件判定・ログ
def test_level_rises_when_meeting_a_new_cat():
    """①レベルが行動に応じて上がる(はじめて猫に出会うと上がる)"""
    s = fresh()
    s["owned_toys"].append("rubber_ball")
    game.place_toy(s, "rubber_ball")
    assert s["level"] == 0
    game._join(s, "gordo", "rubber_ball", [])
    assert s["level"] == game.LEVEL_GAINS["met_new_cat"]
    assert any(e[1] == "met_cat" and e[2] == "gordo" for e in s["log"])
    level_after_first = s["level"]
    game._join(s, "gordo", "rubber_ball", [])          # 2回目は「はじめて」ではないので増えない
    assert s["level"] == level_after_first


def test_meets_composite_conditions():
    """②meets()で複合条件(レベル+所持品など)を判定できる"""
    s = fresh()
    assert game.meets(s, None) is True                 # 条件なしは常に満たす
    assert game.meets(s, {"level": 1}) is False
    s["level"] = 2
    assert game.meets(s, {"level": 1}) is True

    assert game.meets(s, {"items": ["smartphone"]}) is False
    s["ever_had"].add("smartphone")
    assert game.meets(s, {"items": ["smartphone"]}) is True

    assert game.meets(s, {"flag": "unlocked_jiro"}) is False
    s["flags"].add("unlocked_jiro")
    assert game.meets(s, {"flag": "unlocked_jiro"}) is True

    assert game.meets(s, {"met": 1}) is False
    s["met_actors"]["jiro"] = {}
    assert game.meets(s, {"met": 1}) is True

    # 複合条件は、すべて満たして初めて True
    assert game.meets(s, {"level": 2, "flag": "unlocked_jiro", "items": ["smartphone"]}) is True
    assert game.meets(s, {"level": 3, "flag": "unlocked_jiro"}) is False


def test_save_roundtrip_keeps_level_sets_and_log():
    """③セーブ・読み込みを往復しても壊れない(特に ever_had / flags の set 化)"""
    s = fresh()
    s["level"] = 4
    s["ever_had"] = {"smartphone", "amulet"}
    s["flags"] = {"unlocked_jiro"}
    s["met_actors"] = {"jiro": {"trust": 1, "milestones_done": [0], "rewarded": True}}
    game.set_player_name(s, "  黒猫  ")
    game._log(s, "test_event", {"x": 1})

    s2 = game.loads(game.dumps(s))
    assert s2["level"] == 4
    assert s2["ever_had"] == {"smartphone", "amulet"} and isinstance(s2["ever_had"], set)
    assert s2["flags"] == {"unlocked_jiro"} and isinstance(s2["flags"], set)
    assert s2["met_actors"] == {"jiro": {"trust": 1.0, "milestones_done": [0], "rewarded": True}}
    assert s2["player_name"] == "黒猫"
    assert s2["log"][-1][1] == "test_event" and s2["log"][-1][2] == {"x": 1}


def test_set_player_name_trims_and_limits_length():
    s = fresh()
    game.set_player_name(s, "  " + "あ" * 30 + "  ")
    assert s["player_name"] == "あ" * 20


def test_log_is_capped_at_log_max():
    s = fresh()
    for i in range(game.LOG_MAX + 10):
        game._log(s, "x", i)
    assert len(s["log"]) == game.LOG_MAX
    assert s["log"][-1][2] == game.LOG_MAX + 9


# ---------------------------------------------------------------- フェーズ3: 訪問者・人・ギフトの鎖
def test_catseye_appears_at_level_5_and_always_brings_a_smartphone():
    """①出現条件を満たすとキャツアイが現れる(現れた瞬間、必ずスマホをくれる)"""
    s = fresh()
    game._tick_actors(s, random.Random(0), [])
    assert "catseye_a" not in s["met_actors"]          # まだレベル不足

    s["level"] = 5
    ev = []
    game._tick_actors(s, random.Random(0), ev)
    assert "catseye_a" in s["met_actors"]
    assert "smartphone" in s["owned_goods"]
    assert any(e[0] == "met_actor" and e[1] == "catseye_a" for e in ev)
    assert any(e[0] == "milestone_gift" and e[1] == "catseye_a" for e in ev)


def test_giving_smartphone_to_jiro_grants_turtle_once():
    """②スマホを渡すと一度だけ亀がもらえる"""
    s = fresh()
    s["level"] = 5
    game._tick_actors(s, random.Random(0), [])        # catseyeが現れてスマホをくれ、jiroも同tickで現れる
    assert "jiro" in s["met_actors"]

    r = game.give(s, "jiro", "smartphone", random.Random(0))
    assert r.ok and r.code == "given_reward"
    assert s["pets"] == {"turtle"}
    assert "unlocked_obaachan" in s["flags"]
    assert "smartphone" not in s["owned_goods"] and "smartphone" in s["ever_had"]


def test_giving_again_reacts_differently_and_grants_no_second_reward():
    """③2回目以降は違う反応になる(reward は出ない・レベルも増えない)"""
    s = fresh()
    s["level"] = 5
    game._tick_actors(s, random.Random(0), [])
    game.give(s, "jiro", "smartphone", random.Random(0))
    level_after_first = s["level"]

    s["owned_goods"].add("smartphone")                 # テスト用にもう1台持たせる
    r = game.give(s, "jiro", "smartphone", random.Random(0))
    assert r.ok and r.code == "given_thanks"            # 1回目(given_reward)とは違う反応
    assert s["level"] == level_after_first               # reward が出ないので、レベルは増えない
    assert s["pets"] == {"turtle"}                       # 亀が2匹になったりはしない


def test_obaachan_chain_and_catseyes_second_milestone():
    """じろうさん経由でおばあちゃんまでつながり、キャツアイも2つめの大事な物(パソコン)を持ってくる"""
    s = fresh()
    s["level"] = 5
    game._tick_actors(s, random.Random(0), [])
    game.give(s, "jiro", "smartphone", random.Random(0))
    assert "obaachan" not in s["met_actors"]             # フラグが立った直後は、まだ_tick_actorsを回していない

    game._tick_actors(s, random.Random(0), [])
    assert "obaachan" in s["met_actors"]
    assert "laptop" in s["owned_goods"]                  # catseyeの2つめのmilestone

    s["owned_goods"].add("sweets")
    r = game.give(s, "obaachan", "sweets", random.Random(0))
    assert r.ok and r.code == "given_reward"
    assert "amulet" in s["owned_goods"]
    assert "unlocked_stage_mansion2" in s["flags"]


def test_give_requires_meeting_and_owning_the_item():
    s = fresh()
    assert game.give(s, "jiro", "smartphone").code == "not_met"
    s["level"] = 5
    game._tick_actors(s, random.Random(0), [])
    s["owned_goods"].discard("smartphone")
    assert game.give(s, "jiro", "smartphone").code == "not_owned"


def test_invariants_hold_over_long_random_play():
    s = stocked(("rubber_ball", "small_condo", "yarn_ball"))
    rng = random.Random(7)
    for minute in range(1, 6000):
        if s["food_remaining"] == 0:
            s["food_stock"]["dry_food"] = 1
            game.set_food(s, "dry_food")
        game.tick(s, rng)
        for toy in s["yard"]:
            assert len(s["occ"][toy]) <= game.TOYS[toy]["size"]
        seen = []
        for toy, lst in s["occ"].items():
            assert toy in s["yard"]
            for cid in lst:
                c = s["cats"][cid]
                assert c["in_yard"] and c["toy"] == toy and cid not in seen
                seen.append(cid)
        assert sorted(seen) == sorted(game.cats_in_yard(s))


def test_strong_cat_can_push_weaker():
    s = stocked(("rubber_ball",))
    rng = random.Random(3)
    game.ensure_cat(s, "gordo").update(in_yard=True, toy="rubber_ball", time_in_yard=5)
    s["occ"]["rubber_ball"] = ["gordo"]
    events = []
    game._try_push(s, "tarawa", "rubber_ball", rng, events)     # tarawa の強さ 6 > 5
    assert s["occ"]["rubber_ball"] == ["tarawa"]
    assert [e[0] for e in events] == ["leave", "met", "arrive"]      # 初めて庭に来た猫には "met" が付く
    events = []
    game._try_push(s, "felix", "rubber_ball", rng, events)      # 5 < 6 なので押し出せない
    assert s["occ"]["rubber_ball"] == ["tarawa"] and events == []


def test_treasure_when_joining_after_3000_minutes():
    s = stocked(("rubber_ball",))
    game.ensure_cat(s, "felix")["total_time"] = 3001
    ev = []
    game._join(s, "felix", "rubber_ball", ev)
    assert s["pending_treasures"] == ["felix"] and ("treasure", "felix") in ev
    game._join(s, "felix", "rubber_ball", ev)                   # 2回目はもらえない
    assert s["pending_treasures"] == ["felix"]
    assert game.collect_treasures(s) == ["felix"] and s["pending_treasures"] == []


def test_launch_bonus():
    s = fresh()
    assert game.launch_bonus(s, T0, T0 + 999, random.Random(1)) is None   # 誰も遊んでいない
    game.ensure_cat(s, "pukka")["total_time"] = 100

    class Always(random.Random):
        def random(self):
            return 0.0
    assert game.launch_bonus(s, T0, T0 + 10, Always()) == "pukka"
    assert s["cats"]["pukka"]["given_treasure"] and s["pending_treasures"] == ["pukka"]


# ---------------------------------------------------------------- 元のコンソール版との経済パリティ
def test_economy_matches_console_version():
    """元の update.tick で実測した値(5個・エサ常時): 銀 約112/時, 来訪 約9.1回/時, 滞在 平均約18分"""
    silver, visits, hours = [], [], 24 * 3
    for seed in range(8):
        s = stocked()
        rng = random.Random(seed)
        ev = []
        for _ in range(60 * hours):
            if s["food_remaining"] == 0:
                s["food_stock"]["dry_food"] = 1
                game.set_food(s, "dry_food")
            game.tick(s, rng, ev)
        silver.append(sum(a for _c, a, cur in s["pending_money"] if cur == "s") / hours)
        visits.append(sum(1 for e in ev if e[0] == "arrive") / hours)
    assert 100 <= statistics.mean(silver) <= 125
    assert 8.3 <= statistics.mean(visits) <= 9.9


def test_stay_time_distribution():
    rng = random.Random(2)
    stays = []
    for _ in range(5000):
        c = {"time_in_yard": 0}
        while True:
            c["time_in_yard"] += 1
            if game._time_to_leave(c, game.CATS["gordo"], rng):
                break
        stays.append(c["time_in_yard"])
    assert 17 <= statistics.mean(stays) <= 19 and min(stays) >= 11 and max(stays) <= 26


# ---------------------------------------------------------------- 保存
def test_roundtrip():
    s = stocked()
    game.advance(s, T0 + 3600, random.Random(5))
    s2 = game.loads(game.dumps(s))
    assert s2 == s


def test_loads_rejects_other_versions_and_garbage():
    with pytest.raises(ValueError):
        game.loads(json.dumps({"version": 99}))
    with pytest.raises(ValueError):
        game.loads("[]")
    with pytest.raises(json.JSONDecodeError):
        game.loads("{broken")


def test_loads_repairs_inconsistent_data():
    s = stocked()
    d = json.loads(game.dumps(s))
    d["yard"] = ["rubber_ball", "no_such_toy", "rubber_ball"]
    d["owned_toys"] = ["rubber_ball", "ghost"]
    d["s_fish"] = "abc"
    d["food"] = "unknown_food"
    d["cats"]["gordo"] = {"in_yard": True, "toy": "paper_bag"}   # 庭にないおもちゃで遊んでいる
    d["pending_money"] = [["gordo", 5, "s"], ["ghost", 1, "s"], "bad"]
    r = game.loads(json.dumps(d))
    assert r["yard"] == ["rubber_ball"] and r["owned_toys"] == ["rubber_ball"]
    assert r["s_fish"] == 0 and r["food"] == "" and r["food_remaining"] == 0
    assert not r["cats"]["gordo"]["in_yard"] and r["occ"] == {"rubber_ball": []}
    assert r["pending_money"] == [["gordo", 5, "s"]]


def test_catalog_is_consistent():
    assert len(game.TOYS) == 24 and len(game.FOODS) == 4 and len(game.CATS) == 5
    assert len(game.GOODS) == 4 and len(game.ACTORS) == 3
    for it in game.ITEMS.values():
        assert it["cur"] in ("s", "g") and it["cost"] > 0 and it["size"] >= 1
        assert it["size"] <= game.SPACE or it["kind"] == "food"



# ---------------------------------------------------------------- 猫の状態は「出会った分だけ」+ 図鑑の並び
def test_state_holds_only_met_cats_in_discovery_order():
    s = stocked()
    assert s["cats"] == {} and s["met_order"] == []            # 誰にも会っていなければ空
    rng = random.Random(3)
    ev = []
    for _ in range(400):
        if s["food_remaining"] == 0:
            s["food_stock"]["dry_food"] = 1
            game.set_food(s, "dry_food")
        game.tick(s, rng, ev)
    met_events = [e[1] for e in ev if e[0] == "met"]
    assert met_events == s["met_order"] and set(s["cats"]) == set(s["met_order"])
    assert all(c["met"] for c in s["cats"].values())
    assert game.met_list(s) == s["met_order"] and len(set(met_events)) == len(met_events)   # 重複なし


def test_met_order_survives_roundtrip_and_sanitize():
    s = stocked()
    for cid in ("felix", "gordo", "pukka"):
        game._join(s, cid, "rubber_ball", [])
        game._leave(s, cid, random.Random(1), [])
    assert s["met_order"] == ["felix", "gordo", "pukka"]
    r = game.loads(game.dumps(s))
    assert r["met_order"] == ["felix", "gordo", "pukka"]
    d = json.loads(game.dumps(s))
    d["met_order"] = ["pukka", "ghost", "pukka", "felix"]     # 不正な id・重複・抜けがあっても直る
    r = game.loads(json.dumps(d))
    assert r["met_order"] == ["pukka", "felix", "gordo"]


def test_old_save_with_every_cat_is_migrated_to_met_only():
    """旧形式(全猫ぶんの状態がある)のセーブを読むと、出会った猫だけになる。"""
    old = json.loads(game.dumps(fresh()))
    old["cats"] = {cid: {"in_yard": False, "toy": "", "time_in_yard": 0, "total_time": 0,
                         "given_treasure": False, "met": False} for cid in game.CATS}
    old["cats"]["peebles"].update(met=True, total_time=50)
    old["cats"]["gordo"].update(total_time=10)                # met が無くても遊んだ形跡があれば出会い済み
    del old["cats"]["gordo"]["met"]
    old.pop("met_order", None)
    r = game.loads(json.dumps(old))
    assert set(r["cats"]) == {"peebles", "gordo"}
    assert r["met_order"] == ["gordo", "peebles"]             # 順番が不明なぶんは、保存されていた順


# ---------------------------------------------------------------- ショップの絞り込み・並べ替え
def test_shop_ids_default_is_catalog_order():
    s = fresh()
    assert game.shop_ids(s, "toy") == list(game.TOYS)
    assert game.shop_ids(s, "food") == list(game.FOODS)
    assert game.shop_ids(s, "nothing") == []


def test_shop_ids_filters():
    s = fresh()                                               # 銀300 金10
    buyable = game.shop_ids(s, "toy", "buyable")
    assert "rubber_ball" in buyable and "laser_pointer" not in buyable      # 金125は買えない
    assert all(game.ITEMS[i]["cost"] <= s[game.ITEMS[i]["cur"] + "_fish"] for i in buyable)
    game.buy(s, "rubber_ball")
    assert "rubber_ball" not in game.shop_ids(s, "toy", "buyable")
    assert "rubber_ball" not in game.shop_ids(s, "toy", "unowned")
    assert "rubber_ball" in game.shop_ids(s, "toy", "all")
    assert "dry_food" in game.shop_ids(s, "food", "buyable")   # エサは持っていても何個でも買える
    game.buy(s, "dry_food")
    assert "dry_food" not in game.shop_ids(s, "food", "unowned")
    assert "dry_food" in game.shop_ids(s, "food", "buyable")


def test_shop_ids_sort_puts_silver_before_gold_then_by_price():
    s = fresh()
    asc = game.shop_ids(s, "toy", sort="price_asc")
    keys = [(0 if game.ITEMS[i]["cur"] == "s" else 1, game.ITEMS[i]["cost"]) for i in asc]
    assert keys == sorted(keys) and sorted(asc) == sorted(game.TOYS)
    assert game.shop_ids(s, "toy", sort="price_desc") == list(reversed(asc)) or \
        [(0 if game.ITEMS[i]["cur"] == "s" else 1, game.ITEMS[i]["cost"])
         for i in game.shop_ids(s, "toy", sort="price_desc")] == sorted(keys, reverse=True)


# ---------------------------------------------------------------- 猫1000匹・商品数百種類でも動く
@pytest.fixture
def big_catalog():
    import catalog
    toys = [("toy%03d" % i, "おもちゃ%d" % i, 5 + i % 90, "s" if i % 3 else "g", 1 + (i % 7 == 0) * 2, "説明%d" % i)
            for i in range(500)]
    foods = [("food%02d" % i, "エサ%d" % i, 2 + i, "s", 300, {}, "エサの説明") for i in range(40)]
    cats = [("cat%04d" % i, "猫%d" % i, "紹介文%d" % i, "お宝%d" % i) for i in range(1000)]
    game.load_catalog(toys, foods, cats, catalog.CATEGORIES)
    yield
    game.load_catalog(catalog.TOYS, catalog.FOODS, catalog.CATS, catalog.CATEGORIES)


def test_big_catalog_loads_and_validates(big_catalog):
    assert len(game.CATS) == 1000 and len(game.TOYS) == 500 and len(game.FOODS) == 40
    assert len(game.shop_ids(fresh(), "toy")) == 500
    import catalog
    with pytest.raises(ValueError):
        game.load_catalog(catalog.TOYS + catalog.TOYS[:1], catalog.FOODS, catalog.CATS, catalog.CATEGORIES)
    with pytest.raises(ValueError):
        game.load_catalog([("huge", "巨大", 5, "s", 99, "庭に入らない")], [], [], catalog.CATEGORIES)
    assert len(game.CATS) == 1000                              # 失敗した読み込みで、今のデータは壊れない


def test_big_catalog_catchup_is_fast_and_save_stays_small(big_catalog):
    import time as _t
    s = fresh()
    for t in ("toy001", "toy002", "toy003", "toy004", "toy005"):
        s["owned_toys"].append(t)
        assert game.place_toy(s, t).ok
    s["food_stock"]["food00"] = 1
    game.set_food(s, "food00")
    t0 = _t.perf_counter()
    r = game.advance(s, T0 + 60 * 300, random.Random(1))           # エサ1個ぶん(=判定が走る最大の長さ)
    game.advance(s, T0 + 60 * 60 * 24 * 30, random.Random(2))      # 30日離れていた
    dt = _t.perf_counter() - t0
    assert dt < 3.0, dt                                            # 実測はこの1/10ほど
    assert r["visits"] > 0
    size = len(game.dumps(s))
    naive = size + (1000 - len(s["cats"])) * 130                   # 全員ぶんの状態を持った場合の見積もり
    assert size < naive / 4, (size, naive)                         # 出会った猫だけなので、ずっと小さい
    assert len(s["cats"]) == len(s["met_order"]) < 300


def test_big_catalog_arrivals_are_spread_over_many_cats(big_catalog):
    """猫が多いとき、カタログの先頭の猫ばかりが席を取らない(候補をシャッフルしている)。"""
    s = fresh()
    for t in ("toy001", "toy002", "toy003", "toy004", "toy005"):
        s["owned_toys"].append(t)
        game.place_toy(s, t)
    rng = random.Random(5)
    for _ in range(600):
        if s["food_remaining"] == 0:
            s["food_stock"]["food00"] = 1
            game.set_food(s, "food00")
        game.tick(s, rng)
    met = game.met_list(s)
    assert len(met) > 100
    first_half = sum(1 for c in met if int(c[3:]) < 500)
    assert 0.3 < first_half / len(met) < 0.7                      # 前半・後半の猫がほぼ半々


def test_big_catalog_shop_is_cheap_to_query(big_catalog):
    import time as _t
    s = fresh()
    t0 = _t.perf_counter()
    for _ in range(200):
        game.shop_ids(s, "toy", "buyable", "price_asc")
    assert _t.perf_counter() - t0 < 1.0


def test_shop_ids_without_kind_lists_everything():
    s = fresh()
    assert game.shop_ids(s) == list(game.ITEMS)                       # 何も選んでいない(=すべて)
    assert game.shop_ids(s, None, "all", "catalog") == list(game.TOYS) + list(game.FOODS)
    game.buy(s, "rubber_ball")
    game.buy(s, "dry_food")
    unowned = game.shop_ids(s, None, "unowned")
    assert "rubber_ball" not in unowned and "dry_food" not in unowned and "yarn_ball" in unowned
    buyable = game.shop_ids(s, None, "buyable")
    assert "rubber_ball" not in buyable and "dry_food" in buyable and "laser_pointer" not in buyable
    asc = game.shop_ids(s, None, sort="price_asc")
    keys = [(0 if game.ITEMS[i]["cur"] == "s" else 1, game.ITEMS[i]["cost"]) for i in asc]
    assert keys == sorted(keys) and set(asc) == set(game.ITEMS)


def test_cat_voice_option():
    import catalog
    assert all(spec["voice"] == "" for spec in game.CATS.values())            # 既定は専用の声なし
    cats = [("a", "猫A", "d", "t"), ("b", "猫B", "d", "t", {"voice": "bbb", "strength": 6})]
    game.load_catalog(catalog.TOYS, catalog.FOODS, cats, catalog.CATEGORIES)
    try:
        assert game.CATS["a"]["voice"] == "" and game.CATS["b"]["voice"] == "bbb" and game.CATS["b"]["strength"] == 6
    finally:
        game.load_catalog(catalog.TOYS, catalog.FOODS, catalog.CATS, catalog.CATEGORIES)