"""
獎金獵人競賽追蹤 - Streamlit 主程式
"""

import streamlit as st
import json
import os
import re
import urllib.parse
from datetime import datetime
from io import BytesIO

import pytz
from bs4 import BeautifulSoup, NavigableString, Tag
from icalendar import Calendar, Event, vText

# ── 時區 ──────────────────────────────────────────────────────────────────────
TW_TZ = pytz.timezone("Asia/Taipei")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
COMPETITIONS_FILE = os.path.join(DATA_DIR, "competitions.json")


# ─────────────────────────────────────────────────────────────────────────────
# 資料讀取
# ─────────────────────────────────────────────────────────────────────────────

def load_competitions() -> list[dict]:
    if os.path.exists(COMPETITIONS_FILE):
        with open(COMPETITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def ts_to_dt(ts) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=TW_TZ)
    except Exception:
        return None


def is_expired(comp: dict) -> bool:
    dt = ts_to_dt(comp.get("deadline"))
    if not dt:
        return False
    return dt < datetime.now(TW_TZ)


# ─────────────────────────────────────────────────────────────────────────────
# Google 行事曆 URL（單筆）
# ─────────────────────────────────────────────────────────────────────────────

def gcal_url(comp: dict) -> str:
    title = comp.get("title", "競賽")
    url   = comp.get("url", "")
    prize = comp.get("prize_top", 0)

    details = f"獎金：{prize:,} 元\n報名連結：{url}" if prize else f"報名連結：{url}"

    start_dt = ts_to_dt(comp.get("start_date"))
    end_dt   = ts_to_dt(comp.get("deadline"))
    now      = datetime.now(TW_TZ)

    if end_dt:
        end_str   = end_dt.strftime("%Y%m%dT235959")
        start_str = start_dt.strftime("%Y%m%dT000000") if start_dt else end_str
    else:
        start_str = end_str = now.strftime("%Y%m%dT000000")

    params = {
        "action":   "TEMPLATE",
        "text":     title,
        "dates":    f"{start_str}/{end_str}",
        "details":  details,
        "location": url,
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)


# ─────────────────────────────────────────────────────────────────────────────
# 產生 ICS 檔（多筆）
# ─────────────────────────────────────────────────────────────────────────────

def generate_ics(competitions: list[dict]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//獎金獵人競賽追蹤//bhuntr.com//TW")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "獎金獵人競賽")
    cal.add("x-wr-timezone", "Asia/Taipei")

    for comp in competitions:
        ev = Event()
        ev.add("summary", comp.get("title", "競賽"))

        start_dt = ts_to_dt(comp.get("start_date"))
        end_dt   = ts_to_dt(comp.get("deadline"))
        now      = datetime.now(TW_TZ)

        ev.add("dtstart", start_dt or end_dt or now)
        ev.add("dtend",   end_dt or start_dt or now)

        url   = comp.get("url", "")
        prize = comp.get("prize_top", 0)
        detail = f"獎金：{prize:,} 元\n報名：{url}"
        ev.add("description", detail)
        if url:
            ev["url"] = vText(url)
        cal.add_component(ev)

    return cal.to_ical()


# ─────────────────────────────────────────────────────────────────────────────
# HTML → 可讀 Markdown 轉換（含 table 支援）
# ─────────────────────────────────────────────────────────────────────────────

INLINE_TAGS = {"span", "strong", "b", "em", "i", "a", "u", "s", "mark", "code"}


def _inline_text(node) -> str:
    """遞迴取出 inline 節點的純文字"""
    if isinstance(node, NavigableString):
        return str(node).replace("\xa0", " ")
    if node.name in INLINE_TAGS or node.name is None:
        return "".join(_inline_text(c) for c in node.children)
    return node.get_text(separator=" ")


def _table_to_md(table: Tag) -> str:
    """將 <table> 轉成 Markdown 表格"""
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(separator=" ", strip=True).replace("\xa0", " ")
                 for td in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""

    # 統一欄數
    max_cols = max(len(r) for r in rows)
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    lines = []
    # 第一列當標題
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * max_cols) + " |")
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def html_to_readable(raw: str) -> str:
    """HTML → 乾淨 Markdown（保留結構，支援 table）"""
    if not raw or not raw.strip():
        return ""
    if "<" not in raw:
        return raw.strip()

    soup = BeautifulSoup(raw, "html.parser")
    lines: list[str] = []
    buf:   list[str] = []

    def flush():
        text = "".join(buf).replace("\xa0", " ").strip()
        buf.clear()
        if text:
            lines.append(text)

    def process(node, indent=0, in_list=False):
        if isinstance(node, NavigableString):
            buf.append(str(node).replace("\xa0", " "))
            return

        tag = node.name or ""

        if tag in ("h1", "h2"):
            flush()
            text = node.get_text(separator="", strip=True).replace("\xa0", " ").strip()
            if text:
                lines.append("")
                lines.append(f"**{text}**")
            return

        if tag in ("h3", "h4", "h5"):
            flush()
            text = node.get_text(separator="", strip=True).replace("\xa0", " ").strip()
            if text:
                lines.append("")
                lines.append(f"**▸ {text}**")
            return

        if tag == "hr":
            flush()
            lines.append("")
            lines.append("---")
            return

        if tag == "br":
            flush()
            lines.append("")
            return

        if tag == "p":
            flush()
            lines.append("")
            for child in node.children:
                process(child, indent)
            flush()
            return

        if tag == "li":
            flush()
            # 若 li 內含巢狀 ul/ol，遞迴處理
            has_nested = any(getattr(c, "name", "") in ("ul", "ol") for c in node.children)
            if has_nested:
                text_parts = []
                for child in node.children:
                    if getattr(child, "name", "") in ("ul", "ol"):
                        flush()
                        lines.append(("  " * indent) + f"- {''.join(text_parts).strip()}")
                        text_parts = []
                        process(child, indent + 1, in_list=True)
                    else:
                        text_parts.append(_inline_text(child) if isinstance(child, Tag) else str(child).replace("\xa0", " "))
                if text_parts:
                    t = "".join(text_parts).strip()
                    if t:
                        lines.append(("  " * indent) + f"- {t}")
            else:
                text = node.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
                if text:
                    lines.append(("  " * indent) + f"- {text}")
            return

        if tag in ("ul", "ol"):
            flush()
            lines.append("")
            for child in node.children:
                if getattr(child, "name", None) == "li":
                    process(child, indent + (1 if in_list else 0), in_list=True)
            return

        if tag == "table":
            flush()
            lines.append("")
            lines.append(_table_to_md(node))
            lines.append("")
            return

        if tag in ("thead", "tbody", "tfoot", "tr", "th", "td"):
            return  # 已由 _table_to_md 處理

        if tag in INLINE_TAGS:
            buf.append(_inline_text(node))
            return

        for child in node.children:
            process(child, indent, in_list)

    process(soup)
    flush()

    result: list[str] = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ""
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return "\n".join(result).strip()


# ─────────────────────────────────────────────────────────────────────────────
# 五大區塊萃取：參賽資格、活動時程、活動獎勵、評分標準、評審規範
# ─────────────────────────────────────────────────────────────────────────────

# 關鍵字對應（順序代表優先匹配）
SECTION_KW: dict[str, list[str]] = {
    "eligibility": [
        "參賽資格", "報名資格", "參賽對象", "徵選對象", "資格條件", "適用對象",
        "參加資格", "報名條件", "資格及徵件", "徵件辦法", "報名須知",
        "報名方式", "投稿方式", "徵件對象", "活動辦法", "參賽規則", "參賽規範",
        "報名辦法", "投稿辦法", "徵件規範", "申請資格", "申請對象",
        "稿件規範", "稿件格式", "投稿規定", "作品規定", "繳件規範",
    ],
    "schedule":    [
        "活動時程", "活動日程", "報名時程", "賽程時程", "時程表", "重要日期",
        "活動時間", "報名時間", "競賽時程", "日程", "流程時間", "徵選活動流程",
        "活動期程", "徵件期間", "收件期限", "競賽日程", "時程規劃",
    ],
    "prizes":      [
        "活動獎勵", "獎勵辦法", "獎項設置", "獎項說明", "獎金設置", "得獎獎勵",
        "獎品", "頒獎", "獎勵", "獎勵機制", "獎項",
        "投稿贈獎", "得獎名單", "獎金說明",
    ],
    "criteria":    [
        "評分標準", "評審標準", "評選標準", "評分方式", "評選構面",
        "評審構面", "評選基準", "評分項目",
    ],
    "judges":      [
        "評審規範", "評選流程", "評審流程", "評審委員", "評審說明",
        "評審資格", "評審團", "裁判規範", "徵選方式", "評審作業",
        "評審過程", "審查方式", "審查程序",
    ],
}

SECTION_META: dict[str, tuple[str, str]] = {
    "eligibility": ("👤", "參賽資格"),
    "schedule":    ("📅", "活動時程"),
    "prizes":      ("🏆", "活動獎勵"),
    "criteria":    ("📊", "評分標準"),
    "judges":      ("⚖️", "評審規範"),
}


def _match_section(heading_text: str) -> str | None:
    """回傳 heading 對應的 section key，若無匹配回傳 None"""
    for key, keywords in SECTION_KW.items():
        for kw in keywords:
            if kw in heading_text:
                return key
    return None


def extract_sections(html: str) -> dict[str, str]:
    """
    從 guideline HTML 中找出五大區塊，回傳 {section_key: markdown_content}。
    找不到的區塊值為空字串。
    """
    result = {k: "" for k in SECTION_KW}
    if not html or "<" not in html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # 只以 h1/h2 作為區塊切割點；h3/h4 留在內容中不切割
    heading_tags = ("h1", "h2")

    def _is_pseudo_heading(node) -> bool:
        """
        判斷 <p> 是否為偽標題：
        內容幾乎全在 <strong> 裡，且文字含有節標識（冒號結尾或對應關鍵字）。
        例：<p><span><strong>資格及徵件辦法：</strong></span></p>
        """
        if getattr(node, "name", None) != "p":
            return False
        text = node.get_text(strip=True).replace("\xa0", " ")
        if not text or len(text) > 30:          # 偽標題通常很短
            return False
        strong_text = "".join(s.get_text() for s in node.find_all("strong"))
        # strong 文字佔整體 80% 以上，且結尾有冒號或符合區塊關鍵字
        ratio = len(strong_text.strip()) / len(text) if text else 0
        return ratio >= 0.8 and (text.endswith("：") or text.endswith(":") or _match_section(text))

    # 取得頂層節點列表（soup 的直接子節點或 body 的子節點）
    container = soup.body if soup.body else soup
    nodes = list(container.children)

    # 將節點依 heading 分組
    current_key = None
    current_nodes: list = []
    groups: list[tuple[str | None, list]] = []

    for node in nodes:
        tag = getattr(node, "name", None)
        is_heading = tag in heading_tags
        is_pseudo  = _is_pseudo_heading(node)

        if is_heading or is_pseudo:
            heading_text = node.get_text(strip=True).replace("\xa0", " ")
            matched = _match_section(heading_text)
            groups.append((current_key, current_nodes))
            current_key = matched
            current_nodes = []
        else:
            current_nodes.append(node)
    groups.append((current_key, current_nodes))

    # 轉換各組內容
    for key, group_nodes in groups:
        if key is None or not group_nodes:
            continue
        # 只取尚未填入的區塊（若有重複 heading 取第一個）
        if result[key]:
            continue
        # 重新組合為 HTML 再呼叫 html_to_readable
        fragment = "".join(str(n) for n in group_nodes)
        md = html_to_readable(fragment)
        if md.strip():
            result[key] = md.strip()

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 競賽卡片 UI
# ─────────────────────────────────────────────────────────────────────────────

def render_card(comp: dict, badge: str = ""):
    cid      = comp["id"]
    deadline = ts_to_dt(comp.get("deadline"))
    start    = ts_to_dt(comp.get("start_date"))
    now      = datetime.now(TW_TZ)

    col_cb, col_body = st.columns([0.04, 0.96])

    with col_cb:
        checked = st.checkbox(
            "",
            key=f"cb_{cid}",
            value=cid in st.session_state.selected,
            label_visibility="collapsed",
        )
        if checked:
            st.session_state.selected.add(cid)
        else:
            st.session_state.selected.discard(cid)

    with col_body:
        # ── 標題列 ────────────────────────────────────────────────────────────
        title = comp.get("title", "（無標題）")
        st.markdown(f"#### {badge + ' ' if badge else ''}{title}")

        # ── 摘要資訊列（3欄） ─────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)

        with m1:
            if deadline:
                days_left = (deadline - now).days
                if days_left > 0:
                    label = f"⏰ 還有 {days_left} 天"
                    color = "normal" if days_left > 7 else "inverse"
                elif days_left == 0:
                    label = "⏰ 今日截止"
                    color = "off"
                else:
                    label = "⏰ 已截止"
                    color = "off"
                st.metric("截止日期", deadline.strftime("%Y-%m-%d"), label)
            else:
                st.metric("截止日期", "未公告", "")

        with m2:
            prize = comp.get("prize_top", 0)
            st.metric("最高獎金", f"{prize:,} 元" if prize else "未公告", "")

        with m3:
            organizer = comp.get("organizer", "")
            st.metric("主辦單位", organizer[:16] if organizer else "未公告", "")

        # ── 五大分頁 ──────────────────────────────────────────────────────────
        desc = comp.get("description", "")
        if desc:
            sections = extract_sections(desc)

            tab_labels = [
                f"{SECTION_META[k][0]} {SECTION_META[k][1]}"
                for k in SECTION_KW
            ]
            tabs = st.tabs(tab_labels)

            for tab, key in zip(tabs, SECTION_KW):
                icon, label = SECTION_META[key]
                content = sections.get(key, "")
                with tab:
                    if content:
                        st.markdown(content)
                    else:
                        st.caption(f"此競賽未提供「{label}」相關說明，請至官方頁面查閱。")

        # ── 行動按鈕 ──────────────────────────────────────────────────────────
        url = comp.get("url", "")
        if url:
            b1, b2, _ = st.columns([1, 1.6, 3])
            with b1:
                st.link_button("🔗 競賽頁面", url, use_container_width=True)
            with b2:
                st.link_button("📅 加入 Google 行事曆", gcal_url(comp), use_container_width=True)

    st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="獎金獵人競賽追蹤",
        page_icon="🏆",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "selected" not in st.session_state:
        st.session_state.selected = set()

    st.title("🏆 獎金獵人競賽追蹤")
    st.caption("每週一自動抓取 bhuntr.com 最新競賽，篩選青年以上（社會人士／無限制）、排除高中大專體育競技")

    all_comps = load_competitions()
    if not all_comps:
        st.info("📭 尚無競賽資料。請先執行 `python scraper.py` 或等待每週一 GitHub Actions 自動更新。")
        st.stop()

    now = datetime.now(TW_TZ)

    new_active = [c for c in all_comps if c.get("is_new") and not is_expired(c)]
    old_active = [c for c in all_comps if not c.get("is_new") and not is_expired(c)]
    history    = [c for c in all_comps if is_expired(c)]

    key_fn = lambda c: c.get("deadline") or 0
    new_active.sort(key=key_fn)
    old_active.sort(key=key_fn)
    history.sort(key=key_fn, reverse=True)

    # ── 側邊欄 ────────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📅 行事曆操作")
        selected_comps = [c for c in all_comps if c["id"] in st.session_state.selected]

        if selected_comps:
            st.success(f"已選 **{len(selected_comps)}** 個競賽")
            ics_bytes = generate_ics(selected_comps)
            st.download_button(
                label="📥 一鍵全部加入行事曆",
                data=ics_bytes,
                file_name="competitions.ics",
                mime="text/calendar",
                use_container_width=True,
                help="下載後在 Google 行事曆 → 設定 → 匯入與匯出 → 匯入",
            )
            st.markdown("---")
            st.markdown("**已選競賽：**")
            for c in selected_comps:
                dl = ts_to_dt(c.get("deadline"))
                dl_str = dl.strftime("%Y-%m-%d") if dl else "未知"
                st.markdown(f"- {c['title'][:20]}…  \n  截止：{dl_str}")
            st.markdown("---")
            if st.button("🗑️ 清除選擇", use_container_width=True):
                st.session_state.selected = set()
                st.rerun()
        else:
            st.info("勾選競賽後可一鍵加入 Google 行事曆。")

        st.markdown("---")
        st.markdown(
            "**使用說明**\n"
            "1. 勾選想加入的競賽\n"
            "2. 點「一鍵全部加入行事曆」\n"
            "3. 下載 .ics 後在 Google 行事曆匯入\n\n"
            "或點每筆「📅 加入 Google 行事曆」逐筆新增。"
        )
        st.markdown("---")
        active_count = len(new_active) + len(old_active)
        st.caption(
            f"進行中：{active_count} 筆　歷史：{len(history)} 筆\n\n"
            f"資料來源：bhuntr.com　每週一更新"
        )

    # ── 本週新增 ──────────────────────────────────────────────────────────────
    if new_active:
        st.header(f"🆕 本週新增競賽（{len(new_active)} 個）")
        for comp in new_active:
            render_card(comp, badge="🆕")
    else:
        st.header("🆕 本週新增競賽")
        st.info("本週尚無新增競賽，請等待下次（週一）自動更新。")

    # ── 進行中 ────────────────────────────────────────────────────────────────
    if old_active:
        st.header(f"📌 進行中的競賽（{len(old_active)} 個）")
        for comp in old_active:
            render_card(comp)

    # ── 歷史紀錄 ──────────────────────────────────────────────────────────────
    if history:
        with st.expander(f"📚 歷史紀錄（已截止，共 {len(history)} 個）", expanded=False):
            for comp in history:
                render_card(comp, badge="✅")


if __name__ == "__main__":
    main()
