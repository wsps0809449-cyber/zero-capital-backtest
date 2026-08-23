# 0本金回測系統

本金／房貸／保單質押 × 配息組合回測

## 快速開始

```bash
pip install -r requirements.txt
streamlit run app.py
# 或
python3 run_backtest.py
```

## 專案結構

```
├── app.py                 # Streamlit 完整 App
├── frontend/index.html    # 手機靜態 UI
├── engine/
│   ├── funding.py         # 資金來源計算
│   ├── dividend.py        # 配息歷史實算
│   ├── backtest.py        # 主回測引擎
│   ├── data_fetcher.py    # 資料抓取
│   └── report.py          # Excel 報表
├── run_backtest.py
└── requirements.txt
```

## 功能

- 本金／房貸（含寬限期）／保單質押／循環再質押（利息疊加）
- 歷史配息實算（權重 × 每月配息 × 當年匯率 − 管理費）
- 總報酬、CAGR、最大回撤、夏普、淨現金流
- 壓力情境切片、斷頭警示
- Excel 多工作表輸出
