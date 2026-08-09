#!/usr/bin/env python3
"""
KWCI L3 — 다국어 질의 조합기

사전의 질의를 언어별로 손으로 쓰면 두 가지가 무너진다.

  1. 위약 비교가 성립하지 않는다. "한국 화장품"과 "프랑스 화장품"을 따로
     쓰면 두 질의의 어휘 난이도·자연스러움이 달라져, 차이가 관심의 차이인지
     표현의 차이인지 구분되지 않는다.
  2. 40개 개념 x 11개 언어 = 440 셀을 손으로 쓰면 오타와 어색한 직역이
     반드시 섞이고, 어느 셀이 문제인지 사후에 알 수 없다.

그래서 질의를 다음 곱으로 조합한다.

    질의 = 원산지 형용사(6종) x 범주 명사(33종) x 언어별 어순

원산지만 바꾸면 위약이 나온다. 같은 명사, 같은 어순, 같은 자연스러움이
보장되므로 한국 계열과 위약 계열의 유일한 차이가 원산지가 된다. 이것이
위약검정이 요구하는 조건이다.

성 일치
------
불어·독어·포르투갈어·스페인어·아랍어는 형용사가 명사의 성·수에 따라
굴절한다. cuisine(f) 이면 coréenne, sac(m) 이면 coréen 이다. 명사마다 성을
붙여 두고 조합할 때 맞춘다. 이것을 무시하면 원어민이 쓰지 않는 형태가 되어
검색량이 0 에 가까워진다.

어순
----
  {원산지}{명사}   ja th          韓国料理 · อาหารเกาหลี  (붙여 씀)
  {원산지} {명사}  en de tr       Korean food
  {명사} {원산지}  vi id fr pt es ar   cuisine coréenne
"""

from __future__ import annotations

LANGS = ("en", "ja", "vi", "th", "id", "fr", "de", "pt", "es", "tr", "ar")

# 성 굴절이 있는 언어. 나머지는 형용사가 한 형태뿐이다.
GENDERED = {"fr", "de", "pt", "es", "ar"}

# 어순: (템플릿, 구분자)
ORDER = {
    "en": ("AN", " "), "de": ("AN", " "), "tr": ("AN", " "),
    "ja": ("AN", ""),  "th": ("NA", ""),
    "vi": ("NA", " "), "id": ("NA", " "), "fr": ("NA", " "),
    "pt": ("NA", " "), "es": ("NA", " "), "ar": ("NA", " "),
}

# ── 원산지 형용사 ───────────────────────────────────────────────────
# 성 굴절 언어는 {m, f, mp, fp} (독어는 n 도). 나머지는 문자열 하나.
ORIGIN: dict[str, dict[str, object]] = {
    "en": {"KR": "Korean", "JP": "Japanese", "CN": "Chinese",
           "TH": "Thai", "FR": "French", "IT": "Italian"},
    "ja": {"KR": "韓国", "JP": "日本", "CN": "中国",
           "TH": "タイ", "FR": "フランス", "IT": "イタリア"},
    "vi": {"KR": "Hàn Quốc", "JP": "Nhật Bản", "CN": "Trung Quốc",
           "TH": "Thái Lan", "FR": "Pháp", "IT": "Ý"},
    "th": {"KR": "เกาหลี", "JP": "ญี่ปุ่น", "CN": "จีน",
           "TH": "ไทย", "FR": "ฝรั่งเศส", "IT": "อิตาลี"},
    "id": {"KR": "Korea", "JP": "Jepang", "CN": "Cina",
           "TH": "Thailand", "FR": "Prancis", "IT": "Italia"},
    "tr": {"KR": "Kore", "JP": "Japon", "CN": "Çin",
           "TH": "Tayland", "FR": "Fransız", "IT": "İtalyan"},
    "fr": {
        "KR": {"m": "coréen", "f": "coréenne", "mp": "coréens", "fp": "coréennes"},
        "JP": {"m": "japonais", "f": "japonaise", "mp": "japonais", "fp": "japonaises"},
        "CN": {"m": "chinois", "f": "chinoise", "mp": "chinois", "fp": "chinoises"},
        "TH": {"m": "thaïlandais", "f": "thaïlandaise", "mp": "thaïlandais",
               "fp": "thaïlandaises"},
        "FR": {"m": "français", "f": "française", "mp": "français", "fp": "françaises"},
        "IT": {"m": "italien", "f": "italienne", "mp": "italiens", "fp": "italiennes"},
    },
    "de": {
        "KR": {"m": "koreanischer", "f": "koreanische", "n": "koreanisches",
               "p": "koreanische"},
        "JP": {"m": "japanischer", "f": "japanische", "n": "japanisches",
               "p": "japanische"},
        "CN": {"m": "chinesischer", "f": "chinesische", "n": "chinesisches",
               "p": "chinesische"},
        "TH": {"m": "thailändischer", "f": "thailändische", "n": "thailändisches",
               "p": "thailändische"},
        "FR": {"m": "französischer", "f": "französische", "n": "französisches",
               "p": "französische"},
        "IT": {"m": "italienischer", "f": "italienische", "n": "italienisches",
               "p": "italienische"},
    },
    "pt": {
        "KR": {"m": "coreano", "f": "coreana", "mp": "coreanos", "fp": "coreanas"},
        "JP": {"m": "japonês", "f": "japonesa", "mp": "japoneses", "fp": "japonesas"},
        "CN": {"m": "chinês", "f": "chinesa", "mp": "chineses", "fp": "chinesas"},
        "TH": {"m": "tailandês", "f": "tailandesa", "mp": "tailandeses",
               "fp": "tailandesas"},
        "FR": {"m": "francês", "f": "francesa", "mp": "franceses", "fp": "francesas"},
        "IT": {"m": "italiano", "f": "italiana", "mp": "italianos", "fp": "italianas"},
    },
    "es": {
        "KR": {"m": "coreano", "f": "coreana", "mp": "coreanos", "fp": "coreanas"},
        "JP": {"m": "japonés", "f": "japonesa", "mp": "japoneses", "fp": "japonesas"},
        "CN": {"m": "chino", "f": "china", "mp": "chinos", "fp": "chinas"},
        "TH": {"m": "tailandés", "f": "tailandesa", "mp": "tailandeses",
               "fp": "tailandesas"},
        "FR": {"m": "francés", "f": "francesa", "mp": "franceses", "fp": "francesas"},
        "IT": {"m": "italiano", "f": "italiana", "mp": "italianos", "fp": "italianas"},
    },
    "ar": {
        "KR": {"m": "الكوري", "f": "الكورية", "mp": "الكورية", "fp": "الكورية"},
        "JP": {"m": "الياباني", "f": "اليابانية", "mp": "اليابانية", "fp": "اليابانية"},
        "CN": {"m": "الصيني", "f": "الصينية", "mp": "الصينية", "fp": "الصينية"},
        "TH": {"m": "التايلاندي", "f": "التايلاندية", "mp": "التايلاندية",
               "fp": "التايلاندية"},
        "FR": {"m": "الفرنسي", "f": "الفرنسية", "mp": "الفرنسية", "fp": "الفرنسية"},
        "IT": {"m": "الإيطالي", "f": "الإيطالية", "mp": "الإيطالية", "fp": "الإيطالية"},
    },
}

# ── 범주 명사 ───────────────────────────────────────────────────────
# 값은 문자열이거나 (문자열, 성) 튜플. 성은 굴절 언어에서만 쓰인다.
# 독어의 복수는 p, 나머지 굴절 언어는 mp/fp.
NOUN: dict[str, dict[str, object]] = {
    # 도메인 총칭
    "food": {"en": "food", "ja": "料理", "vi": "món ăn", "th": "อาหาร",
             "id": "makanan", "tr": "yemekleri", "fr": ("cuisine", "f"),
             "de": ("Essen", "n"), "pt": ("comida", "f"), "es": ("comida", "f"),
             "ar": ("الطعام", "m")},
    "cosmetics": {"en": "cosmetics", "ja": "コスメ", "vi": "mỹ phẩm",
                  "th": "เครื่องสำอาง", "id": "kosmetik", "tr": "kozmetik",
                  "fr": ("cosmétiques", "mp"), "de": ("Kosmetik", "f"),
                  "pt": ("cosméticos", "mp"), "es": ("cosméticos", "mp"),
                  "ar": ("مستحضرات التجميل", "f")},
    "fashion": {"en": "fashion", "ja": "ファッション", "vi": "thời trang",
                "th": "แฟชั่น", "id": "fashion", "tr": "moda",
                "fr": ("mode", "f"), "de": ("Mode", "f"), "pt": ("moda", "f"),
                "es": ("moda", "f"), "ar": ("الأزياء", "f")},
    # 소비 양식 — 푸드
    "recipe": {"en": "food recipe", "ja": "料理 レシピ", "vi": "công thức nấu ăn",
               "th": "สูตรอาหาร", "id": "resep masakan", "tr": "yemek tarifi",
               "fr": ("recette", "f"), "de": ("Rezept", "n"),
               "pt": ("receita", "f"), "es": ("receta", "f"),
               "ar": ("وصفات", "f")},
    "restaurant": {"en": "restaurant", "ja": "料理店", "vi": "nhà hàng",
                   "th": "ร้านอาหาร", "id": "restoran", "tr": "restoranı",
                   "fr": ("restaurant", "m"), "de": ("Restaurant", "n"),
                   "pt": ("restaurante", "m"), "es": ("restaurante", "m"),
                   "ar": ("مطعم", "m")},
    "street_food": {"en": "street food", "ja": "屋台グルメ",
                    "vi": "ẩm thực đường phố", "th": "สตรีทฟู้ด",
                    "id": "jajanan kaki lima", "tr": "sokak yemekleri",
                    "fr": ("street food", "f"), "de": ("Streetfood", "n"),
                    "pt": ("comida de rua", "f"), "es": ("comida callejera", "f"),
                    "ar": ("طعام الشارع", "m")},
    "instant_noodles": {"en": "ramen", "ja": "ラーメン", "vi": "mì",
                        "th": "รามยอน", "id": "ramyeon", "tr": "ramyeon",
                        "fr": ("ramen", "m"), "de": ("Ramen", "p"),
                        "pt": ("lámen", "m"), "es": ("ramen", "m"),
                        "ar": ("راميون", "m")},
    "chicken": {"en": "fried chicken", "ja": "フライドチキン", "vi": "gà rán",
                "th": "ไก่ทอด", "id": "ayam goreng", "tr": "kızarmış tavuk",
                "fr": ("poulet frit", "m"), "de": ("Fried Chicken", "n"),
                "pt": ("frango frito", "m"), "es": ("pollo frito", "m"),
                "ar": ("دجاج مقلي", "m")},
    "snacks": {"en": "snacks", "ja": "お菓子", "vi": "bánh kẹo", "th": "ขนม",
               "id": "snack", "tr": "atıştırmalıkları",
               "fr": ("snacks", "mp"), "de": ("Snacks", "p"),
               "pt": ("snacks", "mp"), "es": ("snacks", "mp"),
               "ar": ("وجبات خفيفة", "f")},
    "seaweed": {"en": "seaweed snack", "ja": "のり", "vi": "rong biển",
                "th": "สาหร่าย", "id": "rumput laut", "tr": "yosunu",
                "fr": ("algues", "fp"), "de": ("Algen", "p"),
                "pt": ("alga", "f"), "es": ("alga", "f"),
                "ar": ("أعشاب بحرية", "f")},
    # 소비 양식 — 뷰티
    "skincare_routine": {"en": "skincare routine", "ja": "スキンケア",
                         "vi": "quy trình chăm sóc da", "th": "รูทีนสกินแคร์",
                         "id": "skincare routine", "tr": "cilt bakım rutini",
                         "fr": ("routine de soins", "f"),
                         "de": ("Hautpflege Routine", "f"),
                         "pt": ("rotina de skincare", "f"),
                         "es": ("rutina de cuidado facial", "f"),
                         "ar": ("روتين العناية بالبشرة", "m")},
    "cosmetics_brand": {"en": "cosmetics brand", "ja": "コスメ ブランド",
                        "vi": "thương hiệu mỹ phẩm", "th": "แบรนด์เครื่องสำอาง",
                        "id": "merek kosmetik", "tr": "kozmetik markası",
                        "fr": ("marque de cosmétiques", "f"),
                        "de": ("Kosmetikmarke", "f"),
                        "pt": ("marca de cosméticos", "f"),
                        "es": ("marca de cosméticos", "f"),
                        "ar": ("علامة تجميل", "f")},
    "makeup_tutorial": {"en": "makeup tutorial", "ja": "メイク やり方",
                        "vi": "hướng dẫn trang điểm", "th": "สอนแต่งหน้า",
                        "id": "tutorial makeup", "tr": "makyaj eğitimi",
                        "fr": ("tutoriel maquillage", "m"),
                        "de": ("Make-up Tutorial", "n"),
                        "pt": ("tutorial de maquiagem", "m"),
                        "es": ("tutorial de maquillaje", "m"),
                        "ar": ("دروس مكياج", "f")},
    "serum": {"en": "serum", "ja": "美容液", "vi": "serum", "th": "เซรั่ม",
              "id": "serum", "tr": "serumu", "fr": ("sérum", "m"),
              "de": ("Serum", "n"), "pt": ("sérum", "m"), "es": ("sérum", "m"),
              "ar": ("سيروم", "m")},
    "sheet_mask": {"en": "sheet mask", "ja": "シートマスク", "vi": "mặt nạ giấy",
                   "th": "แผ่นมาส์ก", "id": "sheet mask", "tr": "kağıt maske",
                   "fr": ("masque en tissu", "m"), "de": ("Tuchmaske", "f"),
                   "pt": ("máscara facial", "f"), "es": ("mascarilla facial", "f"),
                   "ar": ("قناع ورقي", "m")},
    "sunscreen": {"en": "sunscreen", "ja": "日焼け止め", "vi": "kem chống nắng",
                  "th": "ครีมกันแดด", "id": "sunscreen", "tr": "güneş kremi",
                  "fr": ("crème solaire", "f"), "de": ("Sonnencreme", "f"),
                  "pt": ("protetor solar", "m"), "es": ("protector solar", "m"),
                  "ar": ("واقي الشمس", "m")},
    "cushion": {"en": "cushion foundation", "ja": "クッションファンデ",
                "vi": "phấn nước", "th": "คุชชั่น", "id": "cushion",
                "tr": "cushion fondöten", "fr": ("fond de teint cushion", "m"),
                "de": ("Cushion Foundation", "f"), "pt": ("base cushion", "f"),
                "es": ("base cushion", "f"), "ar": ("كوشن", "m")},
    "lip_tint": {"en": "lip tint", "ja": "リップティント", "vi": "son tint",
                 "th": "ลิปทินท์", "id": "lip tint", "tr": "lip tint",
                 "fr": ("lip tint", "m"), "de": ("Lip Tint", "m"),
                 "pt": ("lip tint", "m"), "es": ("tinta de labios", "f"),
                 "ar": ("تنت الشفاه", "m")},
    "cleanser": {"en": "cleanser", "ja": "クレンジング", "vi": "sữa rửa mặt",
                 "th": "โฟมล้างหน้า", "id": "pembersih wajah",
                 "tr": "yüz temizleyici", "fr": ("nettoyant visage", "m"),
                 "de": ("Reinigungsschaum", "m"), "pt": ("limpador facial", "m"),
                 "es": ("limpiador facial", "m"), "ar": ("غسول الوجه", "m")},
    "haircare": {"en": "hair care", "ja": "ヘアケア", "vi": "chăm sóc tóc",
                 "th": "ผลิตภัณฑ์ดูแลผม", "id": "perawatan rambut",
                 "tr": "saç bakımı", "fr": ("soin capillaire", "m"),
                 "de": ("Haarpflege", "f"), "pt": ("cuidado capilar", "m"),
                 "es": ("cuidado del cabello", "m"), "ar": ("العناية بالشعر", "f")},
    "perfume": {"en": "perfume", "ja": "香水", "vi": "nước hoa", "th": "น้ำหอม",
                "id": "parfum", "tr": "parfümü", "fr": ("parfum", "m"),
                "de": ("Parfum", "n"), "pt": ("perfume", "m"),
                "es": ("perfume", "m"), "ar": ("عطر", "m")},
    # 소비 양식 — 패션
    "style": {"en": "style", "ja": "コーデ", "vi": "phong cách", "th": "สไตล์",
              "id": "gaya", "tr": "tarzı", "fr": ("style", "m"),
              "de": ("Stil", "m"), "pt": ("estilo", "m"), "es": ("estilo", "m"),
              "ar": ("أسلوب", "m")},
    "fashion_brand": {"en": "fashion brand", "ja": "ファッション ブランド",
                      "vi": "thương hiệu thời trang", "th": "แบรนด์แฟชั่น",
                      "id": "merek fashion", "tr": "moda markası",
                      "fr": ("marque de mode", "f"), "de": ("Modemarke", "f"),
                      "pt": ("marca de moda", "f"), "es": ("marca de moda", "f"),
                      "ar": ("علامة أزياء", "f")},
    "idol_fashion": {"en": "idol fashion", "ja": "アイドル ファッション",
                     "vi": "thời trang idol", "th": "แฟชั่นไอดอล",
                     "id": "fashion idol", "tr": "idol modası",
                     "fr": ("mode idol", "f"), "de": ("Idol Mode", "f"),
                     "pt": ("moda idol", "f"), "es": ("moda idol", "f"),
                     "ar": ("أزياء الأيدول", "f")},
    "streetwear": {"en": "streetwear", "ja": "ストリートファッション",
                   "vi": "streetwear", "th": "สตรีทแวร์", "id": "streetwear",
                   "tr": "streetwear", "fr": ("streetwear", "m"),
                   "de": ("Streetwear", "f"), "pt": ("streetwear", "m"),
                   "es": ("streetwear", "m"), "ar": ("ملابس الشارع", "f")},
    "online_shop": {"en": "clothing online shop", "ja": "服 通販",
                    "vi": "shop quần áo online", "th": "ร้านเสื้อผ้าออนไลน์",
                    "id": "toko baju online", "tr": "online giyim mağazası",
                    "fr": ("boutique de vêtements en ligne", "f"),
                    "de": ("Kleidung Onlineshop", "m"),
                    "pt": ("loja de roupas online", "f"),
                    "es": ("tienda de ropa online", "f"),
                    "ar": ("متجر ملابس إلكتروني", "m")},
    "bag": {"en": "bag", "ja": "バッグ", "vi": "túi xách", "th": "กระเป๋า",
            "id": "tas", "tr": "çantası", "fr": ("sac", "m"),
            "de": ("Tasche", "f"), "pt": ("bolsa", "f"), "es": ("bolso", "m"),
            "ar": ("حقيبة", "f")},
    "sunglasses": {"en": "sunglasses", "ja": "サングラス", "vi": "kính râm",
                   "th": "แว่นกันแดด", "id": "kacamata hitam",
                   "tr": "güneş gözlüğü", "fr": ("lunettes de soleil", "fp"),
                   "de": ("Sonnenbrille", "f"), "pt": ("óculos de sol", "mp"),
                   "es": ("gafas de sol", "fp"), "ar": ("نظارات شمسية", "f")},
    "sneakers": {"en": "sneakers", "ja": "スニーカー", "vi": "giày sneaker",
                 "th": "รองเท้าผ้าใบ", "id": "sepatu sneakers",
                 "tr": "spor ayakkabı", "fr": ("baskets", "fp"),
                 "de": ("Sneaker", "p"), "pt": ("tênis", "mp"),
                 "es": ("zapatillas", "fp"), "ar": ("أحذية رياضية", "f")},
    "tshirt": {"en": "t-shirt", "ja": "Tシャツ", "vi": "áo thun", "th": "เสื้อยืด",
               "id": "kaos", "tr": "tişörtü", "fr": ("t-shirt", "m"),
               "de": ("T-Shirt", "n"), "pt": ("camiseta", "f"),
               "es": ("camiseta", "f"), "ar": ("تيشيرت", "m")},
    "jewelry": {"en": "jewelry", "ja": "アクセサリー", "vi": "trang sức",
                "th": "เครื่องประดับ", "id": "perhiasan", "tr": "takısı",
                "fr": ("bijoux", "mp"), "de": ("Schmuck", "m"),
                "pt": ("joias", "fp"), "es": ("joyería", "f"),
                "ar": ("مجوهرات", "f")},
    "hat": {"en": "hat", "ja": "帽子", "vi": "mũ", "th": "หมวก", "id": "topi",
            "tr": "şapkası", "fr": ("chapeau", "m"), "de": ("Mütze", "f"),
            "pt": ("chapéu", "m"), "es": ("sombrero", "m"), "ar": ("قبعة", "f")},
    "outerwear": {"en": "coat", "ja": "コート", "vi": "áo khoác", "th": "เสื้อโค้ท",
                  "id": "mantel", "tr": "montu", "fr": ("manteau", "m"),
                  "de": ("Mantel", "m"), "pt": ("casaco", "m"),
                  "es": ("abrigo", "m"), "ar": ("معطف", "m")},
}


def compose(lang: str, origin: str, noun_key: str) -> str:
    """원산지 x 명사 x 어순 -> 질의. 성 굴절 언어는 명사의 성에 맞춘다."""
    entry = NOUN[noun_key][lang]
    if isinstance(entry, tuple):
        noun, gender = entry
    else:
        noun, gender = entry, None

    adj = ORIGIN[lang][origin]
    if lang in GENDERED:
        # 독어는 복수를 p 로, 나머지 굴절 언어는 mp/fp 로 쓴다.
        key = gender or "m"
        if lang == "de" and key in ("mp", "fp"):
            key = "p"
        if lang != "de" and key == "p":
            key = "mp"
        adj = adj.get(key) or adj.get("m")

    tpl, sep = ORDER[lang]
    return (adj + sep + noun) if tpl == "AN" else (noun + sep + adj)


def selftest() -> list[str]:
    """조합기가 모든 (언어 x 명사) 를 만들 수 있는지 확인한다."""
    bad = []
    for nk in NOUN:
        for lg in LANGS:
            if lg not in NOUN[nk]:
                bad.append(f"{nk}/{lg} 명사 없음")
                continue
            try:
                if not compose(lg, "KR", nk).strip():
                    bad.append(f"{nk}/{lg} 빈 질의")
            except Exception as e:                       # noqa: BLE001
                bad.append(f"{nk}/{lg} {e}")
    for lg in LANGS:
        for og in ("KR", "JP", "CN", "TH", "FR", "IT"):
            if og not in ORIGIN[lg]:
                bad.append(f"origin {og}/{lg} 없음")
    return bad
