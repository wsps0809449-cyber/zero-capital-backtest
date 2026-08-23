# 0本金回測系統 — 建置模式使用說明

## 方案 A：丟進 Grok 建置模式（推薦產生公開連結）

1. 下載或從本 repo clone
2. 主要入口檔：
   - **網頁互動版**：`frontend/index.html`（純前端，手機可直接開）
   - **完整計算版**：`app.py`（Streamlit，需 Python 環境）

若建置模式支援 Python / Streamlit：
```
主檔：app.py
依賴：requirements.txt
啟動：streamlit run app.py --server.address 0.0.0.0
```

若建置模式只支援前端：
```
主檔：frontend/index.html
（資金計算已內建 JS，可離線使用）
```

## 方案 B：本機執行（有電腦時）

```bash
git clone https://github.com/wsps0809449-cyber/zero-capital-backtest.git
cd zero-capital-backtest
pip install -r requirements.txt
streamlit run app.py
```

手機連同一 Wi-Fi，用電腦顯示的 Network URL 開啟。

## 方案 C：純命令列回測

```bash
python3 run_backtest.py
```

結果在 `output/` 資料夾。

## 核心檔案說明

| 檔案 | 用途 |
|------|------|
| app.py | Streamlit 完整互動 App |
| frontend/index.html | 手機靜態 UI + 資金即時計算 |
| engine/funding.py | 本金/房貸/保單/循環再質押 |
| engine/dividend.py | 歷史配息實算 |
| engine/backtest.py | 主回測 + 壓力情境 |
| engine/data_fetcher.py | 資料抓取與快取 |
| engine/report.py | Excel 輸出 |
| run_backtest.py | 一鍵命令列回測 |

## 注意

- 完整歷史回測需要網路抓取 yfinance 資料
- 首次執行會較慢，之後有本地 cache
- 境外基金請自行確認正確 Yahoo 代碼
