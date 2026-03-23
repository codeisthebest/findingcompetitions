# 🏆 獎金獵人競賽追蹤

每週一自動從 [bhuntr.com/tw/competitions](https://bhuntr.com/tw/competitions) 抓取競賽資訊，
篩選 **青年以上**（社會人士 / 無限制）、排除高中、大專院校、體育競技，
並以 Streamlit 呈現，支援一鍵將競賽時程加入 Google 行事曆。

---

## 功能說明

| 功能 | 說明 |
|------|------|
| 🆕 本週新增競賽 | 本週首次出現的競賽，截止日未過 |
| 📌 進行中的競賽 | 舊有但尚未截止的競賽 |
| 📚 歷史紀錄 | 已過截止日的競賽 |
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

```
保留條件：identifyLimit.nonStudent == true  OR  identifyLimit.none == true
排除條件：標題含體育競技相關關鍵字
```

- **包含**：社會人士、無限制、青年、一般民眾
- **排除**：高中生、大學生專屬、籃球/足球/游泳等競技類

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
