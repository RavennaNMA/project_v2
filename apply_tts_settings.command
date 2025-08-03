#!/bin/bash
# ComfyUI TTS Studio 設置快速應用工具

echo "ComfyUI TTS Studio 設置應用"
echo "═══════════════════════════════"

# 激活虛擬環境
echo "激活虛擬環境..."
source venv/bin/activate

# 應用 ComfyUI 設置到主程序
echo "應用 TTS Studio 設置到主程序..."
python3 scripts/apply_comfyui_settings.py

echo ""
echo " 設置應用完成！"
echo "
echo "1. 運行主程序測試語音效果: python3 main.py"
echo "2. 繼續在 ComfyUI Studio 中調整設置"
echo "3. 重新運行此腳本同步新設置"
echo ""

read -p "是否立即啟動主程序測試？(y/n): " choice
if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
    echo ""
    echo " 啟動主程序..."
    python3 main.py
fi 