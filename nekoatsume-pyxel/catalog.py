"""
ねこあつめ Pyxel 版 ― データ表(アイテムと猫)

ここに1行足すだけで、おもちゃ・エサ・猫を増やせます(コードの変更は要りません)。
猫が1000匹、商品が数百種類になっても動くように作ってあります。

ID は英数字とアンダースコア(セーブデータのキーになるので、あとから変えないこと)。
通貨は "s"=銀 / "g"=金。
"""

# ショップの種別(タブ): (種別ID, 表示名)。種別IDは TOYS="toy" / FOODS="food"
CATEGORIES = [("toy", "おもちゃ"), ("food", "エサ")]

# おもちゃ: (ID, 名前, 価格, 通貨, 庭で使うマス数(=同時に遊べる猫の数), 説明)
TOYS = [
    ('rubber_ball', 'ゴムボール', 5, 's', 1, '小さな明るいオレンジ色のゴムボール。ふにふにで、ピコピコ鳴るよ!'),
    ('sparkle_ball', 'キラキラボール', 5, 'g', 1, 'きらめくラメが入った、小さな透明のゴムボール!'),
    ('yarn_ball', '毛糸玉', 10, 's', 1, '赤い毛糸玉だよ!'),
    ('fancy_yarn_ball', '高級毛糸玉', 15, 'g', 1, '赤・青・緑に銀色の糸がきらめく、高級な毛糸玉!'),
    ('tennis_ball', 'テニスボール', 25, 's', 1, '毛羽立った鮮やかな黄色のテニスボール!'),
    ('paper_bag', '紙袋', 20, 's', 1, 'スーパーの紙袋。ガサガサいい音がするよ!'),
    ('scratching_post', '爪とぎポール', 5, 'g', 1, '猫がバリバリ爪をとげる、いい感じのポール!'),
    ('fancy_scratching_post', '高級爪とぎポール', 15, 'g', 1, '硬い木と合成皮革でできた、デラックスな爪とぎポール!'),
    ('fishbowl', '金魚鉢', 10, 'g', 1, 'かわいい金魚が泳ぐ小さな金魚鉢!'),
    ('small_condo', '小型キャットハウス', 75, 's', 3, '少しだけカーペット張りの小さなキャットハウス。3匹まで入れるよ!'),
    ('medium_condo', '中型キャットハウス', 150, 's', 5, '全面カーペット張りの中くらいのキャットハウス。5匹まで入れるよ!'),
    ('large_condo', '大型キャットハウス', 50, 'g', 6, '高級ベルベル絨毯に手縫いの仕上げ、6匹まで入れる大きなキャットハウス!'),
    ('catnip', 'マタタビの袋', 7, 'g', 1, '小さなマタタビの袋。においで猫が大興奮!'),
    ('plain_pillow', '無地のクッション', 30, 's', 1, '青くてやわらかい、小さな無地のクッション!'),
    ('tie_dye_pillow', '絞り染めのクッション', 15, 'g', 1, '絞り染めのフリースでできた、ふかふかの厚いクッション!'),
    ('plastic_bucket', 'プラスチックのバケツ', 20, 's', 1, '白い取っ手のついた小さな緑のバケツ。バケツがあるぞ!'),
    ('cereal_box', 'シリアルの箱', 15, 's', 1, '「シナモンとろけるゴロゴロ」の空き箱!'),
    ('fruit_box', '果物の箱', 75, 's', 1, '小さな段ボールの果物箱。入れそうなら、入っちゃう!'),
    ('large_box', '大きな箱', 30, 'g', 4, 'もとは家電が入っていた大きな段ボール箱。猫が4匹まで入れるよ!'),
    ('butterfly_toy', '蝶々のおもちゃ', 15, 'g', 1, '長い棒の先の糸に蝶々がぶら下がった、かわいいおもちゃ。ひらひら楽しい!'),
    ('laser_pointer', 'ロボットレーザーポインター', 125, 'g', 1, 'レーザーポインターを持った小さなロボットアーム。みんな大好き!'),
    ('rainbow_umbrella', '虹色の傘', 25, 'g', 5, '虹色もようの大きな傘。猫が5匹まで入れるよ!'),
    ('plain_umbrella', '無地の傘', 250, 's', 4, '明るい黄色の大きな無地の傘。猫が4匹まで入れるよ!'),
    ('plush_froggy', 'カエルのぬいぐるみ', 75, 's', 1, 'ぎゅっとすると鳴く、緑のかわいいカエルのぬいぐるみ!'),
]

# エサ: (ID, 名前, 価格, 通貨, 量, 好みタグ({タグ名: 重み}), 説明)
#   量は「時間(分)」ではなく、庭にいる猫が食べた分だけ減っていく(game.py 参照)。
FOODS = [
    ('dry_food', 'ドライフード', 10, 's', 300, {'meat': 0.5, 'grain': 0.5}, 'ごく普通のドライフード。カリカリでシンプルな味。'),
    ('wet_food', 'ウェットフード缶', 2, 'g', 300, {'fish': 1.0}, 'ごく普通のウェットフード。においが強烈!'),
    ('fancy_food', '高級フード缶', 5, 'g', 300, {'fish': 0.7, 'meat': 0.3}, '職人が手づくりした、フェアトレードのオーガニック猫ごはん。んー、おいしい!'),
    ('catnip_snack', '猫草スナック', 8, 's', 200, {'grass': 1.0}, '猫が大好きな乾燥した猫草のスナック。'),
]

# 猫: (ID, 名前, 紹介文, お宝) または (ID, 名前, 紹介文, お宝, {個性の上書き})
#   個性: strength(押し出す強さ・既定5), entry_chance(来訪率のベース・既定0.1。実際の来やすさは
#         taste とエサの好みタグ、fullness(満腹度)で補正される。game.py の _entry_probability() 参照),
#         time_limit(滞在の上限分・既定30),
#         fav_toy(好きなおもちゃID), exclusive(好物しか使わない),
#         voice(専用の鳴き声の名前。AudioManager.meow_named に同じ名前の声が登録されていれば、それで鳴く。
#               いまは登録がないので、書いても効果はなく、3種類の生成音のどれかで鳴く),
#         traits({appetite/friendly/wary}・既定 DEFAULT_TRAITS、食いしん坊さなどの個性),
#         taste({好みタグ: 重み}・既定なし。エサの好みタグとの一致度で来やすさが変わる),
#         sex(いまは表示用データのみで、ゲーム内の判定には未使用),
#         affinity({同居キャラID: 重み}・いまは書けるだけでゲーム内の判定には未使用。フェーズ3/4で使う予定)
CATS = [
    ('gordo', 'ゴードー', 'いつもあなたのごはんを食べにくる、いちばん手のかかる猫', '役に立たない木切れ(ゴードーだから)',
     {'traits': {'appetite': 0.8, 'friendly': 0.4, 'wary': 0.3}, 'taste': {'meat': 1.0, 'fish': 0.2}, 'sex': 'm'}),
    ('pukka', 'プッカ', 'クリーム色のぶちがある白い短毛で、緑の目の猫。レーザーを追いかけたり、サーフィンをするのが大好き', 'サーフワックスのかたまり'),
    ('peebles', 'ピーブルズ', '青い目の白黒の短毛猫。デスメタルとマタタビの山が好き', 'べっ甲のギターピック'),
    ('tarawa', 'タラワ', '白い筋の入ったグレーの長毛で、灰色の目の猫。のんびりするのと、鳥を追いかけるのが好き', 'アオカケスの羽根',
     {'strength': 6, 'traits': {'appetite': 0.3, 'friendly': 0.2, 'wary': 0.6}, 'taste': {'grass': 1.0},
      'sex': 'f', 'affinity': {'turtle': 0.8}}),
    ('felix', 'フェリックス', 'オレンジと白の短毛のトラ猫で、黄色い目。とてもおだやかで、一日中ほとんど瞑想している', '仏像のお香立て'),
]

# 物(取引品。庭には置かず、訪問者や人とのやり取りだけに使う): (ID, 名前, 好みタグ, 説明)
GOODS = [
    ('smartphone', 'スマホ', {'electronics': 1.0}, '使い古しのスマートフォン。'),
    ('laptop', 'パソコン', {'electronics': 1.0}, '使い古しのノートパソコン。'),
    ('sweets', 'お菓子', {'sweets': 1.0}, '素朴な焼き菓子。'),
    ('amulet', 'お守り', {}, '古びたお守り。'),
]

# 訪問者・人: (ID, 種類, 名前, 紹介文) または (ID, 種類, 名前, 紹介文, {個性の上書き})
#   種類: "visitor"(通り過ぎるだけ、たまに物をくれる) / "person"(居着く。物をあげると反応する)
#   個性のキー:
#     requires: 現れる条件(meets() に渡す辞書。省略時は常に出現)
#     milestones: [(requires_or_None, reward), ...] 条件を満たすたびに、まだ渡していない最初の1件を渡す、
#                 一度きりの重要な贈り物(None は「出会った時点」を意味する)
#     casual_gifts: [(outcome, 重み), ...] 居る間、低確率で繰り返しくれる、ちょっとした贈り物
#     wants: {タグ: 重み} person が好む物のタグ(give() で使う)
#     one_time_reward: 初めて wants に合う物をもらったときだけ渡す reward
#   reward / outcome の形式: "item:GOODSのID" 等の文字列(outcome)、または {"item": ...}(reward)。
#                            reward にはさらに "creature": ペットID や "unlocks": 次に解放するフラグ名の元、を持てる
ACTORS = [
    ('catseye_a', 'visitor', 'キャツアイの誰か',
     '使い古し電子機器を引き取って売り買いしている。お金にはこだわらず、猫を愛している。',
     {'requires': {'level': 5},
      'milestones': [
          (None, {'item': 'smartphone'}),                             # 出会ったら必ずスマホをくれる
          ({'flag': 'unlocked_obaachan'}, {'item': 'laptop'}),         # 話が進むと、また大事な物を持ってきてくれる
      ],
      'casual_gifts': [('item:sweets', 1.0)]}),                       # たまに、おまけでお菓子もくれる

    ('jiro', 'person', 'じろうさん',
     '愛想はよくないが、電子機器の面倒な相談に乗ってくれる。何かお礼を渡すと喜ぶらしい。',
     {'requires': {'items': ['smartphone']},
      'wants': {'electronics': 1.0},
      'one_time_reward': {'creature': 'turtle', 'unlocks': 'obaachan'}}),

    ('obaachan', 'person', 'おばあちゃん',
     '庭の隅にいつの間にか腰掛けている。甘い物に目がないようだ。',
     {'requires': {'flag': 'unlocked_obaachan'},
      'wants': {'sweets': 1.0},
      'one_time_reward': {'item': 'amulet', 'unlocks': 'stage_mansion2'}}),
]

# 満腹度(0〜1)の帯ごとの一言。境界は game.py の _fullness_bucket() を参照。
FULLNESS_LINES = {
    'very_hungry': [
        'お腹が空いているようだ',
        'じっとエサを見つめている',
        'エサの匂いを嗅いでいる',
        'うずうずと落ち着きがない',
    ],
    'hungry': [
        '時々エサの方を見ている',
        'のんびりしている',
        'あくびをしている',
        '毛づくろいをしている',
    ],
    'content': [
        'くつろいでいる',
        '目を細めている',
        '気持ちよさそうにしている',
        'のびをしている',
    ],
    'full': [
        'ご機嫌で鳴いている',
        '満足そうにしている',
        'ごろごろ喉を鳴らしている',
        'ふわふわしっぽを立てている',
    ],
}

# おもちゃIDごとの、遊んでいるときの一言。対応が無いおもちゃは 'default' を使う。
TOY_LINES = {
    'rubber_ball': ['ボールを追いかけている', 'ボールを前足で押している', 'ボールを転がして遊んでいる'],
    'sparkle_ball': ['きらめくボールに見入っている', 'ボールのラメを目で追っている', 'ボールにじゃれついている'],
    'yarn_ball': ['毛糸玉を転がしている', '毛糸を前足で絡め取っている', '毛糸玉に飛びついている'],
    'fancy_yarn_ball': ['高級毛糸にうっとりしている', '色とりどりの毛糸で遊んでいる', '毛糸を丁寧にほぐしている'],
    'tennis_ball': ['テニスボールを追いかけている', 'ボールを咥えて運んでいる', 'ボールを蹴って遊んでいる'],
    'paper_bag': ['紙袋に頭を突っ込んでいる', '紙袋の中で動いている', '紙袋をガサガサ鳴らしている'],
    'scratching_post': ['爪とぎで爪を研いでいる', '爪とぎに体をこすりつけている', '爪とぎの上で伸びをしている'],
    'fancy_scratching_post': ['高級な爪とぎを堪能している', '爪とぎに背中をこすりつけている', '爪とぎの上でくつろいでいる'],
    'fishbowl': ['金魚をじっと見つめている', '金魚鉢の前から動かない', '金魚を前足でつつこうとしている'],
    'small_condo': ['ハウスの中で丸まっている', 'ハウスから顔だけ出している', 'ハウスの入り口で毛づくろいしている'],
    'medium_condo': ['ハウスでくつろいでいる', 'ハウスの中を気に入っている', 'ハウスの窓から外を見ている'],
    'large_condo': ['広いハウスを満喫している', 'ハウスのてっぺんでくつろいでいる', 'ハウスの中を歩き回っている'],
    'catnip': ['マタタビの匂いに夢中になっている', 'マタタビの袋に頬ずりしている', 'マタタビでゴロゴロ転がっている'],
    'plain_pillow': ['クッションの上で丸まっている', 'クッションを踏んでいる', 'クッションに顔をうずめている'],
    'tie_dye_pillow': ['ふかふかのクッションでくつろいでいる', 'クッションに丸まって眠そうにしている', 'クッションを揉んでいる'],
    'plastic_bucket': ['バケツの中に収まっている', 'バケツの縁に前足をかけている', 'バケツをカタカタ鳴らしている'],
    'cereal_box': ['シリアルの箱に入っている', '箱の中から顔だけ出している', '箱の縁で爪を研いでいる'],
    'fruit_box': ['果物の箱にすっぽり収まっている', '箱の中で丸まっている', '箱から顔だけのぞかせている'],
    'large_box': ['大きな箱の中を探検している', '箱の中で隠れている', '箱の出入りを繰り返している'],
    'butterfly_toy': ['蝶々のおもちゃを追いかけている', '蝶々に飛びかかろうとしている', '蝶々をじっと見つめている'],
    'laser_pointer': ['光の点を追いかけている', '光を捕まえようとしている', '光の点をじっと見つめている'],
    'rainbow_umbrella': ['傘の下でくつろいでいる', '虹色の傘を見上げている', '傘の陰で丸まっている'],
    'plain_umbrella': ['傘の下で雨宿り気分でいる', '傘の陰でくつろいでいる', '傘の下を出たり入ったりしている'],
    'plush_froggy': ['カエルのぬいぐるみを抱きしめている', 'ぬいぐるみを前足で押している', 'ぬいぐるみを甘噛みしている'],
    'default': ['のんびりしている', '周りを見ている', 'くつろいでいる'],
}

# ショップでの店主のひとこと(購入時などに使う)
SHOP_KEEPER_LINES = ['まいどあり', 'ナイスチョイスですよ', 'すてきなチョイスですよ', 'これはおすすめですよ']


def validate_world():
    """ID の重複や参照切れが無いかを確認する。game.py の load_catalog() が起動時に呼ぶ。
    エラーの文字列リストを返す。問題がなければ空リスト。"""
    errors = []

    def ids_of(rows):
        return [r[0] for r in rows]

    groups = {'TOYS': ids_of(TOYS), 'FOODS': ids_of(FOODS), 'CATS': ids_of(CATS),
              'GOODS': ids_of(GOODS), 'ACTORS': ids_of(ACTORS)}
    for label, ids in groups.items():
        if len(ids) != len(set(ids)):
            errors.append('{0} にIDの重複があります'.format(label))

    seen = {}
    for label, ids in groups.items():
        for i in ids:
            if i in seen and seen[i] != label:
                errors.append("'{0}' が {1} と {2} でIDが衝突しています".format(i, seen[i], label))
            seen.setdefault(i, label)

    good_ids = set(groups['GOODS'])

    def check_outcome(actor_id, where, outcome):
        kind, value = outcome.split(':', 1) if ':' in outcome else (outcome, '')
        if kind == 'item' and value not in good_ids:
            errors.append("{0} の{1} '{2}' が GOODS にありません".format(actor_id, where, outcome))

    def check_reward(actor_id, where, reward):
        if not reward:
            return
        if 'item' in reward and reward['item'] not in good_ids:
            errors.append("{0} の{1} の item '{2}' が GOODS にありません".format(actor_id, where, reward['item']))

    for actor_id, kind, name, desc, opts in ACTORS:
        for req, reward in opts.get('milestones', []):
            check_reward(actor_id, 'milestones', reward)
        for outcome, _w in opts.get('casual_gifts', []):
            check_outcome(actor_id, 'casual_gifts', outcome)
        check_reward(actor_id, 'one_time_reward', opts.get('one_time_reward'))
        wants = opts.get('wants', {})
        if wants:
            good_tags = {tag for g in GOODS for tag in g[2]}
            for tag in wants:
                if tag not in good_tags:
                    errors.append("{0} の wants のタグ '{1}' を持つ GOODS がありません".format(actor_id, tag))

    for tid, name, cost, cur, size, desc in TOYS:
        if tid not in TOY_LINES:
            pass  # TOY_LINES は無くても 'default' で表示できるので、無くてもエラーにはしない

    return errors


def validate_world_or_raise():
    errors = validate_world()
    if errors:
        raise ValueError('\n'.join(errors))


if __name__ == '__main__':
    validate_world_or_raise()
    print('OK: catalog is consistent')
