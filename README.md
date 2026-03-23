# 🏆 獎金獵人競賽追蹤

每週一自動從 [bhuntr.com/tw/competitions](https://bhuntr.com/tw/competitions) 抓取競賽資訊，
篩選**社會人士 / 無限制**身分，排除學生限定、身心障礙限定、體育競技、演講辯論、書法繪畫等類別，
並以 Streamlit 呈現，支援一鍵將競賽時程加入 Google 行事曆。

🌐 **線上網址**：[findingcompetitions.streamlit.app](https://findingcompetitions.streamlit.app)

---

## 功能說明

| 功能 | 說明 |
|------|------|
| 🆕 本週新增競賽 | 本週首次出現的競賽，截止日未過 |
| 📌 進行中的競賽 | 舊有但尚未截止的競賽 |
| 📚 歷史紀錄 | 已過截止日的競賽 |
| 🗂️ 七大資訊分頁 | 每筆競賽展開後顯示活動主題、參賽資格、報名方式、活動時程、活動獎勵、評分標準、評審規範 |
| 📅 加入 Google 行事曆 | 逐筆加入，或勾選後一鍵匯入 ICS |
| 🔄 每週一自動更新 | GitHub Actions 自動抓取並 commit |

---

## 快速上手（本機）

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 手動執行一次爬蟲（產生初始資料）
python scraper.py

# 3. 啟動 Streamlit 網站
streamlit run app.py
```

---

## 部署到 Streamlit Cloud

1. 將此 repo push 到 GitHub（設為 Public 或 Private 皆可）
2. 前往 [share.streamlit.io](https://share.streamlit.io) 登入
3. New app → 選擇此 repo → Main file: `app.py` → Deploy
4. Streamlit Cloud 會自動讀取 `data/competitions.json`

> **注意**：Streamlit Cloud 本身不會執行爬蟲，資料由 GitHub Actions 每週更新後自動同步。

---

## GitHub Actions 設定

`.github/workflows/weekly_scrape.yml` 已設定：

- **排程**：每週一 UTC 00:00（台灣時間週一 08:00）
- **手動觸發**：在 Actions 頁面點「Run workflow」
- 自動 commit 更新後的 `data/competitions.json` 與 `data/seen_ids.json`

Streamlit Cloud 部署後，每次 commit 都會觸發重新讀取最新資料。

---

## 一鍵加入 Google 行事曆（ICS）

1. 在網頁上勾選想加入的競賽（可多選）
2. 點選左側「📥 一鍵全部加入行事曆」
3. 下載 `competitions.ics` 檔案
4. 開啟 [Google 行事曆](https://calendar.google.com) → 右上角 ⚙️ → **設定**
5. 左側選單 → **匯入與匯出** → **選擇檔案** → 選 `competitions.ics` → **匯入**
6. 所有選取的競賽截止日將一次建立為行程 ✅

---

## 過濾邏輯

**保留條件（身分）**

- `identifyLimit.nonStudent == true`（社會人士可報名）
- 或 `identifyLimit.none == true`（無限制）
- 或 `identifyLimit.other == true` 且說明文字不含學生 / 身心障礙限定關鍵字

**排除條件（標題 + 說明前 200 字）**

| 類別 | 排除關鍵字範例 |
|------|--------------|
| 體育競技 | 籃球、足球、馬拉松、跆拳道、攀岩… |
| 舞蹈 | 舞蹈比賽、街舞、Breaking… |
| 音樂演奏 | 鋼琴比賽、小提琴、演奏賽、音樂大賽… |
| 歌唱 | 歌唱比賽、歌手大賽、唱歌比賽… |
| 音樂劇 | 音樂劇 |
| 書法 / 傳統繪畫 | 書法比賽、揮春、油畫、水彩、素描、版畫、國畫、水墨、寫生 |
| 演講 / 辯論 / 朗讀 | 演講比賽、辯論比賽、朗誦大賽… |
| 客語 / 原住民族語 | 客語、客家語、原住民、族語 |
| 身心障礙限定 | 適應運動、身障者才藝（標題）；other_text 含身心障礙/視障/聽障 |

**排除條件（全文）**

- 說明文字含禁止電繪關鍵字（僅限手繪）

---

## 競賽資訊七大分頁

每筆競賽展開後以分頁呈現結構化說明：

| 分頁 | 對應標題關鍵字範例 |
|------|-----------------|
| 🎯 活動主題 | 活動主題、活動宗旨、前言、活動說明 |
| 👤 參賽資格 | 參賽資格、報名資格、申請對象、徵件對象 |
| 📝 報名方式 | 報名方式、投稿方式、稿件規範、繳件規範 |
| 📅 活動時程 | 活動時程、時程表、徵件期間、收件期限 |
| 🏆 活動獎勵 | 活動獎勵、獎項說明、獎金設置 |
| 📊 評分標準 | 評分標準、評審標準、評選基準 |
| ⚖️ 評審規範 | 評審委員、評審流程、審查方式 |

---

## 檔案結構

```
├── app.py                          # Streamlit 主程式
├── scraper.py                      # 爬蟲（每週由 GitHub Actions 執行）
├── requirements.txt
├── .gitignore
├── .github/
│   └── workflows/
│       └── weekly_scrape.yml       # 每週一自動執行
└── data/
    ├── competitions.json           # 所有競賽資料（自動更新）
    └── seen_ids.json               # 已抓過的 ID（避免重複）
```
