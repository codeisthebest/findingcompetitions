"""
獎金獵人競賽爬蟲
每週一自動抓取 bhuntr.com/tw/competitions
過濾條件：青年以上（社會人士 / 無限制），排除高中、大專院校、體育競技
"""

import requests
import json
import re
import os
import base64
import hashlib
import time
from datetime import datetime

import pytz

BASE_URL = "https://bhuntr.com"
TW_TZ = pytz.timezone("Asia/Taipei")

# ── 體育競技 / 音樂現場演奏排除關鍵字（標題中出現則排除）───────────────────
SPORTS_TITLE_KW = {
    # 體育競技
    "體育競技", "體育賽", "運動競技", "競技賽",
    "籃球", "足球", "羽球", "桌球", "排球",
    "游泳", "田徑", "棒球", "壘球", "網球", "撞球",
    "馬拉松", "鐵人三項", "武術", "跆拳道",
    "柔道", "空手道", "拳擊", "射箭", "舉重",
    "體操", "自行車競賽",
    "舞蹈比賽", "舞蹈大賽", "舞蹈競賽", "舞蹈錦標",
    "街舞", "大會舞", "Breaking", "嘻哈舞", "踢踏舞",
    "歌唱比賽", "歌唱大賽", "歌唱競賽",
    "歌手大賽", "歌手比賽", "歌手競賽",
    "歌王", "歌后", "唱歌比賽", "唱歌大賽",
    "定向越野", "越野跑", "跳繩", "躲避球",
    "飛鏢", "保齡球", "扯鈴", "踢毽",
    "手球", "曲棍球", "冰球", "橄欖球", "板球",
    "滑板", "攀岩", "划船", "帆船",
    # 音樂現場演奏
    "演奏賽", "演奏比賽", "演奏競賽",
    "音樂大賽", "音樂比賽", "音樂競賽", "音樂公開賽",
    "器樂大賽", "器樂比賽", "聲樂大賽", "聲樂比賽",
    "鋼琴大賽", "鋼琴比賽", "小提琴大賽", "大提琴大賽",
    "管樂大賽", "弦樂大賽", "打擊樂大賽",
    # 樂器演奏競賽（個別樂器名稱）
    "小提琴", "大提琴", "低音提琴", "中提琴",
    "鋼琴大賽", "鋼琴比賽",
    "吉他大賽", "吉他比賽",
    "長笛", "雙簧管", "單簧管", "低音管", "巴松管",
    "小號", "長號", "法國號", "大號",
    "豎琴", "手風琴", "口琴",
    "二胡大賽", "琵琶大賽", "古箏大賽", "古琴大賽",
    "爵士鼓", "爵士鼓大賽",
    # 音樂劇
    "音樂劇",
    # 演講 / 口語競賽
    "演講比賽", "演講大賽", "演講競賽",
    "辯論比賽", "辯論大賽", "辯論競賽",
    "朗讀比賽", "朗讀大賽", "朗誦比賽", "朗誦大賽",
    # 客語 / 原住民族語言相關
    "客語", "客家語",
    "原住民", "原民",
    "族語",
    # 身心障礙限定（標題）
    "適應運動", "身障者才藝", "身心障礙者技能",
    # 寫生
    "寫生比賽", "寫生大賽", "寫生競賽", "寫生嘉年華",
    # 書法
    "書法比賽", "書法大賽", "書法競賽", "書法展", "揮春",
    # 傳統繪畫媒材（限定類型）
    "油畫比賽", "油畫大賽", "油畫競賽",
    "水彩比賽", "水彩大賽", "水彩競賽",
    "素描大賽", "素描比賽", "素描競賽",
    "版畫展", "版畫三年展", "版畫比賽", "版畫大賽",
    "國畫大賽", "國畫比賽", "國畫競賽",
    "水墨大賽", "水墨比賽", "水墨競賽",
}

# ── 全文中若含以下關鍵字，代表禁止電繪，應排除 ───────────────────────────────
HANDRAW_ONLY_KW = {
    "不得以電腦繪", "不得使用電腦繪", "不得電繪",
    "禁止電繪", "禁止使用電腦繪", "僅限手繪",
    "不得以電腦或 AI 繪", "不得以電腦或AI繪",
}

# ── identifyLimitOther 中若含以下關鍵字，代表僅限學生，應排除 ─────────────────
STUDENT_ONLY_KW = {
    "小學", "國小", "小一", "小二", "小三", "小四", "小五", "小六",
    "國中生", "高中生", "高職生", "大學生", "大專生",
    "幼兒園", "幼稚園", "托兒所", "學齡前",
    "在校學生", "在學學生",
    # 補充：其他常見學生限定寫法（用複合詞避免誤判如「前學生」）
    "學生身份",     # ΔDesignArt 學生作品徵件
    "學生皆可",     # GAIP 保險創新競賽（大學…學生皆可）
    "年級學生",     # Cool English（五專一至三年級學生）
    "學測",         # 學測重考生（高中生相關）
    "幼童",         # 幼童組
    "幼兒組",       # 幼兒組（國小以下）
    "大專院校",     # 限大專院校（注意：大專校院 = 學校本身，大專院校 = 學生限定用法）
}

# ── identifyLimitOther 中若含以下關鍵字，代表僅限身心障礙者，應排除 ────────────
DISABILITY_ONLY_KW = {
    "身心障礙", "身障", "視障", "聽障", "肢障",
}

# ─────────────────────────────────────────────────────────────────────────────

def make_id(comp: dict) -> str:
    key = str(comp.get("alias") or comp.get("id") or comp.get("title", ""))
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def should_include(comp: dict) -> bool:
    """
    保留規則
    ① identifyLimit.nonStudent == True（社會人士可報名）
       OR  identifyLimit.none == True（無限制）
       OR  identifyLimit.other == True 且 identifyLimitOther 不含「僅限學生」關鍵字
    ② 標題不含體育競技關鍵字
    """
    identify: dict = comp.get("identifyLimit") or {}
    other_text: str = comp.get("identifyLimitOther") or ""
    title: str = comp.get("title", "")

    # ── 身份限制檢查 ──────────────────────────────────────────────────────────
    open_to_public = identify.get("nonStudent", False) or identify.get("none", False)

    if not open_to_public:
        # 嘗試 other 類別：確認 identifyLimitOther 不是純學生限定
        if identify.get("other", False):
            if any(kw in other_text for kw in STUDENT_ONLY_KW):
                return False   # other 但限定學生 → 排除
            open_to_public = True  # other 且非純學生 → 接受

    if not open_to_public:
        return False

    # ── 身心障礙限定排除（other_text 含身心障礙關鍵字，即使 nonStudent=True）─────
    if any(kw in other_text for kw in DISABILITY_ONLY_KW):
        return False

    # ── 體育競技 / 音樂劇排除（標題 + 說明前 200 字）──────────────────────────
    desc_preview = (comp.get("guideline") or comp.get("description") or "")[:200]
    combined = title + desc_preview
    for kw in SPORTS_TITLE_KW:
        if kw in combined:
            return False

    # ── 手繪限定排除（全文搜尋）──────────────────────────────────────────────
    full_desc = comp.get("guideline") or comp.get("description") or ""
    for kw in HANDRAW_ONLY_KW:
        if kw in full_desc:
            return False

    return True


def parse_deadline_from_text(html: str) -> int:
    """
    當 submitEndTime 為空時，嘗試從說明文字中解析繳交/報名截止日。
    支援：
      - 民國年：115年06月18日  (115 + 1911 = 2026)
      - 西元年：2026年5月31日
    策略：找所有「截止」關鍵字附近的日期，取最晚的一筆。
    """
    if not html:
        return 0

    from bs4 import BeautifulSoup
    text = BeautifulSoup(html, "html.parser").get_text(" ")

    # 截止關鍵字：往後 60 字內找日期
    DEADLINE_KW = ["截止", "報名截止", "繳交截止", "繳件截止", "作品截止", "收件截止"]

    # 日期 pattern：(年份)(月)(日)
    DATE_RE = re.compile(r"(\d{3,4})年\s*(\d{1,2})月\s*(\d{1,2})日")

    candidates: list[int] = []

    for kw in DEADLINE_KW:
        for m in re.finditer(re.escape(kw), text):
            # 往前 80 字（處理「日期 截止」），往後 60 字（處理「截止 日期」）
            window = text[max(0, m.start()-80): m.end()+60]
            for dm in DATE_RE.finditer(window):
                y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                if y < 1000:          # 民國年 → 西元
                    y += 1911
                if 2020 <= y <= 2040:
                    try:
                        dt = datetime(y, mo, d, 23, 59, 59,
                                      tzinfo=TW_TZ)
                        candidates.append(int(dt.timestamp()))
                    except ValueError:
                        pass

    return max(candidates) if candidates else 0


def normalize(comp: dict) -> dict:
    alias = comp.get("alias", "")
    cover = comp.get("coverImage") or {}
    image_url = ""
    if isinstance(cover, dict):
        image_url = cover.get("url", cover.get("src", ""))
    elif isinstance(cover, str):
        image_url = cover

    return {
        "id": make_id(comp),
        "raw_id": comp.get("id", ""),
        "title": comp.get("title", "（無標題）"),
        "alias": alias,
        "url": f"{BASE_URL}/tw/competitions/{alias}" if alias else "",
        "description": comp.get("guideline", comp.get("description", "")),
        "deadline": (comp.get("submitEndTime") or 0) or
                    parse_deadline_from_text(comp.get("guideline", comp.get("description", ""))),
        "start_date": comp.get("submitStartTime") or 0,   # Unix 秒
        "categories": comp.get("categories", []),
        "identify_limit": comp.get("identifyLimit") or {},
        "identify_limit_other": comp.get("identifyLimitOther", ""),
        "image_url": image_url,
        "prize_top": comp.get("prizeTop", 0),
        "organizer": comp.get("organizerTitle", comp.get("organizer", "")),
        "location": comp.get("location", ""),
        "scraped_at": datetime.now(TW_TZ).isoformat(),
        "first_seen": "",   # 由 run_scraper() 填入
        "is_new": False,    # 由 run_scraper() 填入
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTTP 抓取
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 資料嵌在 window._<數字> = '<base64>' 中
_WIN_DATA_RE = re.compile(r"window\._\d+\s*=\s*'([A-Za-z0-9+/=]+)'")


def fetch_page_data(page: int) -> tuple[list[dict], dict]:
    """
    回傳 (競賽列表, page_info)。
    page_info 格式：{'first':1, 'last':2271, 'prev':1, 'next':2, 'current':1}
    """
    url = f"{BASE_URL}/tw/competitions" + (f"?page={page}" if page > 1 else "")
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            m = _WIN_DATA_RE.search(resp.text)
            if not m:
                print(f"  [警告] 第{page}頁找不到嵌入資料（網站結構可能已改變）")
                return [], {}
            raw = base64.b64decode(m.group(1)).decode("utf-8")
            data = json.loads(raw)
            contest_result = data.get("bypass", {}).get("contestResult", {})
            return contest_result.get("list", []), contest_result.get("page", {})
        except Exception as e:
            print(f"  [fetch] 第{page}頁第{attempt+1}次失敗：{e}")
            time.sleep(3)
    return [], {}


def fetch_all_competitions(max_pages: int = 15) -> list[dict]:
    """
    從第1頁開始抓，直到：
    - 整頁競賽的截止日全部已過（代表之後都是舊資料）
    - 或達到 max_pages 上限
    """
    now_ts = datetime.now(TW_TZ).timestamp()
    all_items: list[dict] = []
    seen_raw_ids: set = set()

    page = 1
    while page <= max_pages:
        print(f"  正在抓取第 {page} 頁…")
        items, page_info = fetch_page_data(page)

        if not items:
            break

        new_count = 0
        all_expired = True
        for item in items:
            rid = str(item.get("id", "") or item.get("alias", ""))
            if rid and rid in seen_raw_ids:
                continue
            seen_raw_ids.add(rid)
            all_items.append(item)
            new_count += 1

            deadline = item.get("submitEndTime") or 0
            if deadline > now_ts:
                all_expired = False

        print(f"    新增 {new_count} 筆，累計 {len(all_items)} 筆")

        # 若整頁都已截止，停止抓取
        if all_expired:
            print("  整頁競賽皆已截止，停止分頁抓取。")
            break

        last_page = page_info.get("last", 1)
        if page >= last_page:
            break

        page += 1
        time.sleep(1)   # 禮貌延遲

    return all_items


# ─────────────────────────────────────────────────────────────────────────────
# 資料持久化
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
COMPETITIONS_FILE = os.path.join(DATA_DIR, "competitions.json")
SEEN_IDS_FILE = os.path.join(DATA_DIR, "seen_ids.json")


def _load(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────────────

def run_scraper() -> list[dict]:
    print(f"\n=== 開始抓取 {datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M')} ===")

    seen_ids: set = set(_load(SEEN_IDS_FILE, []))
    existing: list[dict] = _load(COMPETITIONS_FILE, [])
    existing_map: dict = {c["id"]: c for c in existing}

    # 抓取原始資料
    raw_items = fetch_all_competitions(max_pages=15)
    print(f"  共抓到 {len(raw_items)} 筆原始資料（過濾前）")

    # 過濾 + 標準化
    filtered = [normalize(c) for c in raw_items if should_include(c)]
    print(f"  過濾後剩餘 {len(filtered)} 筆")

    # 舊資料一律設 is_new=False，本次才決定哪些是新的
    for c in existing_map.values():
        c["is_new"] = False

    now_iso = datetime.now(TW_TZ).isoformat()
    new_count = 0

    for comp in filtered:
        cid = comp["id"]
        if cid not in seen_ids:
            comp["is_new"] = True
            comp["first_seen"] = now_iso
            existing_map[cid] = comp
            seen_ids.add(cid)
            new_count += 1
        else:
            old = existing_map.get(cid, {})
            comp["first_seen"] = old.get("first_seen", now_iso)
            comp["is_new"] = False
            existing_map[cid] = comp

    all_comps = list(existing_map.values())
    _save(COMPETITIONS_FILE, all_comps)
    _save(SEEN_IDS_FILE, list(seen_ids))

    print(f"  本次新增：{new_count} 筆 / 累計：{len(all_comps)} 筆")
    print("=== 抓取完成 ===\n")

    return [c for c in all_comps if c.get("is_new")]


if __name__ == "__main__":
    run_scraper()
