#!/bin/bash
# Location: project_v2/scripts/st_mac.command
# Usage: Mac 啟動指令檔（增強版）

# 取得腳本所在目錄並移動到項目根目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$DIR")"
cd "$PROJECT_ROOT"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "================================"
echo -e "${GREEN}防禦偵測系統 - Mac 版 v2 (偵錯模式)${NC}"
echo "================================"
echo "工作目錄: $(pwd)"

# 檢查 Python 版本
echo -e "${BLUE}檢查 Python 版本...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo -e "${RED}錯誤：找不到 Python！${NC}"
    echo "請先安裝 Python 3.8 或以上版本"
    echo "建議使用 Homebrew 安裝: brew install python3"
    echo "或從官網下載: https://www.python.org/downloads/"
    read -p "按 Enter 鍵結束..."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version)
echo -e "${GREEN}✅ Python 版本: $PYTHON_VERSION${NC}"

# 檢查虛擬環境
if [ -d "venv" ]; then
    echo -e "${BLUE}找到虛擬環境，啟動中...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}建立虛擬環境...${NC}"
    $PYTHON_CMD -m venv venv
    source venv/bin/activate
    
    echo "升級 pip..."
    pip install --upgrade pip
    
    echo "安裝相依套件（Mac 版本）..."
    pip install -r requirements.txt
    
    echo -e "${BLUE}檢查 Mac 特定依賴項...${NC}"
    if [[ $(uname -m) == "arm64" ]]; then
        echo -e "${GREEN}✅ 檢測到 Apple Silicon (M1/M2/M3/M4)${NC}"
        echo "使用優化版本的 PyTorch..."
        pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu || echo -e "${YELLOW}⚠️ torch 安裝失敗，將使用預設版本${NC}"
    else
        echo -e "${GREEN}✅ 檢測到 Intel Mac${NC}"
    fi
fi

# 建立必要目錄
echo -e "${BLUE}建立必要目錄...${NC}"
mkdir -p webcam-shots
mkdir -p weapons_img
mkdir -p fonts
mkdir -p config

# 檢查字型檔案
if [ ! -f "fonts/NotoSansCJKtc-Regular.otf" ]; then
    echo ""
    echo -e "${YELLOW}⚠️ 警告：找不到中文字型檔案${NC}"
    echo "請將 NotoSansCJKtc-Regular.otf 放入 fonts/ 目錄"
    echo "程式將使用系統預設字型 (PingFang TC)"
    echo ""
fi

# 檢查必要配置文件
echo -e "${BLUE}檢查配置文件...${NC}"
if [ ! -d "config" ]; then
    echo -e "${RED}❌ 錯誤：找不到 config 目錄${NC}"
    exit 1
fi

# 檢查相機可用性
echo -e "${BLUE}檢查相機設備...${NC}"
CAMERA_COUNT=$(system_profiler SPCameraDataType 2>/dev/null | grep -c "Camera")
if [ "$CAMERA_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ 找到 $CAMERA_COUNT 個相機設備${NC}"
else
    echo -e "${YELLOW}⚠️ 未檢測到相機設備，程式可能無法正常運作${NC}"
    echo "請確保：1) 相機已連接 2) 相機權限已允許"
fi

# 檢查 Arduino 連接（可選）
echo -e "${BLUE}檢查 Arduino 連接...${NC}"
if ls /dev/cu.usb* 2>/dev/null >/dev/null; then
    echo -e "${GREEN}✅ 檢測到 USB 設備，可能包含 Arduino${NC}"
    ls /dev/cu.usb* 2>/dev/null
else
    echo -e "${YELLOW}⚠️ 未檢測到 Arduino USB 連接${NC}"
    echo "SSR 控制功能將不可用（僅影響硬體控制）"
fi

# 檢查系統權限
echo -e "${BLUE}檢查系統權限...${NC}"
echo -e "${YELLOW}💡 程式需要以下權限：${NC}"
echo "• 相機存取權限（必需）"
echo "• 麥克風權限（用於 TTS 播放）"
echo "• 檔案系統權限（用於儲存截圖）"
echo ""

# SSL 警告處理
echo -e "${BLUE}檢查 SSL 環境...${NC}"
if python3 -c "import ssl; print('SSL version:', ssl.OPENSSL_VERSION)" 2>/dev/null | grep -q "LibreSSL"; then
    echo -e "${YELLOW}⚠️ 檢測到 LibreSSL，可能會有相容性警告（不影響功能）${NC}"
    export PYTHONHTTPSVERIFY=0  # 暫時解決 SSL 警告
fi

# 啟動程式（偵錯模式）
echo ""
echo -e "${GREEN}🚀 啟動防禦偵測系統 v2（偵錯模式）...${NC}"
echo -e "${YELLOW}💡 提示：如果出現相機權限提示，請選擇「允許」${NC}"
echo ""

# 記錄啟動時間
START_TIME=$(date)
echo "啟動時間: $START_TIME"

# 啟動程式並捕捉錯誤
# macOS 沒有 timeout 命令，使用 background process 替代
python main.py &
MAIN_PID=$!

# 等待程式執行
wait $MAIN_PID
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 程式正常結束${NC}"
else
    echo ""
    echo -e "${RED}❌ 程式異常結束 (Exit Code: $EXIT_CODE)${NC}"
    
    echo ""
    echo -e "${YELLOW}🔧 偵錯資訊：${NC}"
    echo "啟動時間: $START_TIME"
    echo "結束時間: $(date)"
    echo "工作目錄: $(pwd)"
    echo "Python 版本: $PYTHON_VERSION"
    echo "系統資訊: $(uname -a)"
    
    echo ""
    echo -e "${BLUE}💡 常見問題解決方案：${NC}"
    echo "1. 相機問題："
    echo "   • 檢查相機是否被其他應用程式佔用"
    echo "   • 重新授予相機權限：系統偏好設定 > 安全性與隱私 > 相機"
    echo "   • 嘗試重新連接外接相機"
    echo ""
    echo "2. 權限問題："
    echo "   • 確保允許了所有系統權限提示"
    echo "   • 可能需要在系統偏好設定中手動授權"
    echo ""
    echo "3. 依賴套件問題："
    echo "   • 執行: pip install -r requirements.txt --force-reinstall"
    echo "   • 刪除 venv 目錄後重新執行此腳本"
    echo ""
    echo "4. 如果問題持續："
    echo "   • 查看上方錯誤訊息的詳細內容"
    echo "   • 檢查 webcam-shots 目錄是否可寫入"
    echo "   • 確認所有配置檔案完整"
    
    # 提供重新啟動選項
    echo ""
    read -p "是否要重新啟動程式？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}重新啟動中...${NC}"
        exec "$0"  # 重新執行腳本
    fi
fi

echo ""
read -p "按 Enter 鍵關閉..."