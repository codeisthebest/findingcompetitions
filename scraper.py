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
}

# ── identifyLimitOther 中若含以下關鍵字，代表僅限學生，應排除 ─────────────────
STUDENT_ONLY_KW = {
    "小學", "國小", "小一", "小二", "小三", "小四", "小五", "小六",
    "國中生", "高中生", "高職生", "大學生", "大專生",
    "幼兒園", "幼稚園", "托兒所", "學齡前",
    "在校學生", "在學學生",
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

    # ── 體育競技排除（標題 + 說明前 200 字）────────────────────────────────────
    # 只取說明前段避免誤殺（非運動競賽的說明文字可能偶爾提到運動）
    desc_preview = (comp.get("guideline") or comp.get("description") or "")[:200]
    combined = title + desc_preview
    for kw in SPORTS_TITLE_KW:
        if kw in combined:
            return False

    return True


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
        "deadline": comp.get("submitEndTime") or 0,       # Unix 秒
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
