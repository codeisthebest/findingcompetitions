"""
獎金獵人競賽追蹤 - Streamlit 主程式
"""

import streamlit as st
import json
import os
import urllib.parse
from datetime import datetime
from io import BytesIO

import pytz
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
    url = comp.get("url", "")
    desc = comp.get("description", "")
    prize = comp.get("prize_top", 0)

    details_lines = []
    if desc:
        details_lines.append(desc[:500])  # 避免 URL 過長
    if prize:
        details_lines.append(f"獎金：{prize:,} 元")
    if url:
        details_lines.append(f"報名連結：{url}")
    details = "\n".join(details_lines)

    start_dt = ts_to_dt(comp.get("start_date"))
    end_dt = ts_to_dt(comp.get("deadline"))
    now = datetime.now(TW_TZ)

    if end_dt:
        end_str = end_dt.strftime("%Y%m%dT235959")
        start_str = start_dt.strftime("%Y%m%dT000000") if start_dt else end_str
    else:
        start_str = end_str = now.strftime("%Y%m%dT000000")

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "details": details,
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
        end_dt = ts_to_dt(comp.get("deadline"))
        now = datetime.now(TW_TZ)

        ev.add("dtstart", start_dt or end_dt or now)
        ev.add("dtend", end_dt or start_dt or now)

        url = comp.get("url", "")
        desc = comp.get("description", "")
        prize = comp.get("prize_top", 0)
        detail = f"{desc[:400]}\n\n獎金：{prize:,} 元\n報名：{url}" if desc else f"獎金：{prize:,} 元\n報名：{url}"
        ev.add("description", detail)
        if url:
            ev["url"] = vText(url)

        cal.add_component(ev)

    return cal.to_ical()


# ─────────────────────────────────────────────────────────────────────────────
# 競賽卡片 UI
# ─────────────────────────────────────────────────────────────────────────────

def render_card(comp: dict, badge: str = ""):
    cid = comp["id"]
    deadline = ts_to_dt(comp.get("deadline"))
    now = datetime.now(TW_TZ)

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
        title = comp.get("title", "（無標題）")
        header = f"{badge} {title}" if badge else title
        st.markdown(f"#### {header}")

        # 截止日 + 倒數
        if deadline:
            days_left = (deadline - now).days
            if days_left > 0:
                deadline_str = f"⏰ 截止日：{deadline.strftime('%Y-%m-%d')}（還有 **{days_left}** 天）"
            elif days_left == 0:
                deadline_str = f"⏰ 截止日：{deadline.strftime('%Y-%m-%d')}（**今日截止**）"
            else:
                deadline_str = f"⏰ 截止日：{deadline.strftime('%Y-%m-%d')}（已截止）"
            st.caption(deadline_str)

        # 獎金 / 主辦
        meta_parts = []
        prize = comp.get("prize_top", 0)
        if prize:
            meta_parts.append(f"💰 獎金：{prize:,} 元")
        organizer = comp.get("organizer", "")
        if organizer:
            meta_parts.append(f"🏢 主辦：{organizer}")
        if meta_parts:
            st.caption("　　".join(meta_parts))

        # 詳情
        desc = comp.get("description", "")
        if desc:
            with st.expander("📄 查看詳情"):
                st.write(desc[:1000] + ("…（詳見原頁面）" if len(desc) > 1000 else ""))

        # 連結按鈕
        url = comp.get("url", "")
        if url:
            btn_col1, btn_col2, _ = st.columns([1, 1, 4])
            with btn_col1:
                st.link_button("🔗 競賽頁面", url, use_container_width=True)
            with btn_col2:
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

    # ── Session State ─────────────────────────────────────────────────────────
    if "selected" not in st.session_state:
        st.session_state.selected = set()

    # ── 標題 ──────────────────────────────────────────────────────────────────
    st.title("🏆 獎金獵人競賽追蹤")
    st.caption("每週一自動抓取 bhuntr.com 最新競賽，篩選青年以上（社會人士／無限制）、排除高中大專體育競技")

    # ── 讀取資料 ──────────────────────────────────────────────────────────────
    all_comps = load_competitions()

    if not all_comps:
        st.info("📭 尚無競賽資料。\n\n請先在本機執行 `python scraper.py` 產生初始資料，或等待每週一 GitHub Actions 自動更新。")
        st.stop()

    now = datetime.now(TW_TZ)

    # ── 分類 ──────────────────────────────────────────────────────────────────
    new_active = [c for c in all_comps if c.get("is_new") and not is_expired(c)]
    old_active = [c for c in all_comps if not c.get("is_new") and not is_expired(c)]
    history = [c for c in all_comps if is_expired(c)]

    # 依截止日排序（最近截止優先）
    def sort_key(c):
        return c.get("deadline") or 0

    new_active.sort(key=sort_key)
    old_active.sort(key=sort_key)
    history.sort(key=sort_key, reverse=True)

    # ── 側邊欄：行事曆操作 ──────────────────────────────────────────────────
    with st.sidebar:
        st.header("📅 行事曆操作")

        selected_comps = [c for c in all_comps if c["id"] in st.session_state.selected]

        if selected_comps:
            st.success(f"已選 **{len(selected_comps)}** 個競賽")

            # 一鍵全部加入（ICS 下載）
            ics_bytes = generate_ics(selected_comps)
            st.download_button(
                label="📥 一鍵全部加入行事曆",
                data=ics_bytes,
                file_name="competitions.ics",
                mime="text/calendar",
                use_container_width=True,
                help="下載 ICS 檔案後，在 Google 行事曆 → 設定 → 匯入，即可一次建立所有行程",
            )

            st.markdown("---")
            st.markdown("**已選競賽清單：**")
            for c in selected_comps:
                deadline = ts_to_dt(c.get("deadline"))
                dl_str = deadline.strftime("%Y-%m-%d") if deadline else "未知"
                st.markdown(f"- {c['title'][:22]}…  \n  截止：{dl_str}")

            st.markdown("---")
            if st.button("🗑️ 清除所有選擇", use_container_width=True):
                st.session_state.selected = set()
                st.rerun()

        else:
            st.info("請在右側勾選競賽後，即可一鍵加入 Google 行事曆。")

        st.markdown("---")
        st.markdown(
            "**使用說明**\n"
            "1. 勾選想加入的競賽\n"
            "2. 點選「一鍵全部加入行事曆」\n"
            "3. 下載 .ics 檔案\n"
            "4. 開啟 Google 行事曆 → 設定（⚙️）→ 匯入與匯出 → 匯入\n\n"
            "也可直接點每筆右側「📅 加入 Google 行事曆」逐筆新增。"
        )

        st.markdown("---")
        st.caption(f"資料筆數：{len(all_comps)} 筆\n\n最後更新：從 data/competitions.json")

    # ── 主區塊：本週新增 ─────────────────────────────────────────────────────
    if new_active:
        st.header(f"🆕 本週新增競賽（{len(new_active)} 個）")
        for comp in new_active:
            render_card(comp, badge="🆕")
    else:
        st.header("🆕 本週新增競賽")
        st.info("本週尚無新增競賽，請等待下次（週一）自動更新。")

    # ── 進行中（舊有）────────────────────────────────────────────────────────
    if old_active:
        st.header(f"📌 進行中的競賽（{len(old_active)} 個）")
        for comp in old_active:
            render_card(comp)

    # ── 歷史紀錄 ─────────────────────────────────────────────────────────────
    if history:
        with st.expander(f"📚 歷史紀錄（已截止，共 {len(history)} 個）", expanded=False):
            for comp in history:
                render_card(comp, badge="✅")


if __name__ == "__main__":
    main()
