#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

def test_font_loading():
    """測試字型載入"""
    app = QApplication(sys.argv)
    
    # 測試字型檔案是否存在
    font_path = os.path.join("fonts", "NotoSansCJKtc-Regular.otf")
    print(f"字型檔案路徑: {font_path}")
    print(f"檔案是否存在: {os.path.exists(font_path)}")
    
    if os.path.exists(font_path):
        print(f"檔案大小: {os.path.getsize(font_path)} bytes")
    
    # 測試字型載入
    try:
        from utils.font_manager import FontManager
        font_manager = FontManager()
        print(f"字型載入狀態: {font_manager.font_loaded}")
        print(f"字型家族: {font_manager.font_family}")
        
        # 測試字型渲染
        test_font = font_manager.get_font(16)
        print(f"測試字型: {test_font.family()}")
        
        # 創建測試視窗
        window = QWidget()
        window.setWindowTitle("字型測試")
        window.resize(400, 200)
        
        layout = QVBoxLayout()
        
        # 測試中文字型
        label1 = QLabel("測試中文字型：你好世界")
        label1.setFont(test_font)
        layout.addWidget(label1)
        
        # 測試英文字型
        label2 = QLabel("Test English Font: Hello World")
        label2.setFont(test_font)
        layout.addWidget(label2)
        
        window.setLayout(layout)
        window.show()
        
        print("字型測試視窗已顯示，請檢查文字是否正確顯示")
        print("按 Ctrl+C 退出測試")
        
        return app.exec()
        
    except Exception as e:
        print(f"測試字型時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_font_loading()) 