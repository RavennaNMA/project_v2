#!/bin/bash
# Location: project_v2/scripts/st_mac.command
# Usage: Mac 啟動指令檔（可雙擊執行）

# 取得腳本所在目錄並移動到項目根目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$DIR")"
cd "$PROJECT_ROOT"

echo "================================"
echo "防禦偵測系統 - Mac 版 v2"
echo "================================"
echo "工作目錄: $(pwd)"

# 檢查 Python 版本
echo "檢查 Python 版本..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "錯誤：找不到 Python！"
    echo "請先安裝 Python 3.8 或以上版本"
    echo "建議使用 Homebrew 安裝: brew install python3"
    echo "或從官網下載: https://www.python.org/downloads/"
    read -p "按 Enter 鍵結束..."
    exit 1
fi

# 顯示 Python 版本
echo "Python 版本: $($PYTHON_CMD --version)"

# 檢查虛擬環境
if [ -d "venv" ]; then
    echo "找到虛擬環境，啟動中..."
    source venv/bin/activate
else
    echo "建立虛擬環境..."
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    
    echo "升級 pip..."
    pip install --upgrade pip
    
    echo "安裝相依套件（Mac 版本）..."
    # 為 Mac 安裝特定版本的依賴項
    pip install -r requirements.txt
    
    echo "檢查 Mac 特定依賴項..."
    # 確保 torch 使用 Mac 優化版本
    if [[ $(uname -m) == "arm64" ]]; then
        echo "檢測到 Apple Silicon (M1/M2/M3)，使用優化版本..."
        pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || echo "警告: torch 安裝失敗，將使用預設版本"
    fi
fi

# 建立必要目錄
echo "建立必要目錄..."
mkdir -p webcam-shots
mkdir -p weapons_img
mkdir -p fonts
mkdir -p config

# 檢查字型檔案
if [ ! -f "fonts/NotoSansCJKtc-Regular.otf" ]; then
    echo ""
    echo "警告：找不到中文字型檔案"
    echo "請將 NotoSansCJKtc-Regular.otf 放入 fonts/ 目錄"
    echo "程式將使用系統預設字型 (PingFang TC)"
    echo ""
fi

# 檢查必要配置文件
echo "檢查配置文件..."
if [ ! -d "config" ]; then
    echo "錯誤：找不到 config 目錄"
    exit 1
fi

# 檢查相機權限
echo "注意：程式需要相機權限"
echo "如果系統提示，請允許相機存取權限"
echo ""

# 啟動程式
echo "啟動防禦偵測系統 v2..."
echo ""
python main.py

# 如果程式異常結束，保持視窗開啟
if [ $? -ne 0 ]; then
    echo ""
    echo "程式異常結束"
    echo "常見問題解決方案："
    echo "1. 確保已允許相機權限"
    echo "2. 檢查虛擬環境是否正確安裝"
    echo "3. 執行: pip install -r requirements.txt"
    read -p "按 Enter 鍵關閉..."
fi