#!/bin/bash
cd "$(dirname "$0")"
echo "啟動 0本金回測系統..."
echo "手機請用瀏覽器開啟下方 Network / External URL"
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
