#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡單的 Cal Windows 動畫測試
"""

import sys
import os
import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QImage, QPixmap

# 添加項目根目錄到路徑
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 直接導入需要的模組
from ui.cal_windows_effect import (
    ImprovedCalWindow, 
    ImprovedDetectionWindowEffect,
    update_global_frame_count, 
    get_global_frame_count,
    pde_noise
)
from utils.anim_config_loader import AnimConfigLoader

class SimpleAnimationTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUI()
        self.setupTest()
        
    def setupUI(self):
        self.setWindowTitle("簡單的 Cal Windows 動畫測試")
        self.setFixedSize(1080, 1920)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.display_label = QLabel()
        self.display_label.setFixedSize(1080, 1920)
        self.display_label.setStyleSheet("background-color: black;")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.display_label)
        central_widget.setLayout(layout)
        
    def setupTest(self):
        # 初始化配置
        self.config = AnimConfigLoader()
        
        # 初始化窗口效果
        self.window_effect = ImprovedDetectionWindowEffect(
            screen_width=1080, 
            screen_height=1920, 
            config=self.config
        )
        
        # 模擬人臉檢測結果
        self.test_faces = [
            (400, 800, 200, 200),  # 模擬一個人臉
        ]
        
        # 設置定時器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)  # 約60 FPS
        
        self.frame_count = 0
        
    def update_frame(self):
        self.frame_count += 1
        
        # 更新全域幀計數
        update_global_frame_count()
        
        # 創建測試幀
        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        
        # 添加一些背景效果
        for y in range(1920):
            intensity = int(30 + 20 * np.sin(y * 0.01 + self.frame_count * 0.02))
            frame[y, :] = [intensity//3, intensity//2, intensity]
        
        # 模擬人臉移動
        if self.frame_count > 100:  # 延遲開始動畫
            # 更新人臉位置（簡單的圓周運動）
            center_x = 540 + int(100 * np.cos(self.frame_count * 0.02))
            center_y = 960 + int(100 * np.sin(self.frame_count * 0.015))
            self.test_faces = [(center_x - 100, center_y - 100, 200, 200)]
        
        # 模擬檢測框狀態（state 3）
        face_states = {0: 3}  # 假設檢測框已達到 state 3
        
        # 更新窗口效果
        self.window_effect.update_faces(self.test_faces, face_states)
        
        # 繪製窗口
        color_bgr = (255, 255, 255)
        self.window_effect.draw_all_windows(frame, color_bgr)
        
        # 顯示幀
        self.display_frame(frame)
        
        # 每100幀打印一次狀態
        if self.frame_count % 100 == 0:
            global_frame = get_global_frame_count()
            window_count = self.window_effect.get_total_window_count()
            print(f"幀 {self.frame_count}: 全域幀={global_frame}, 窗口數={window_count}")
            
            # 測試噪聲函數
            noise_val = pde_noise(0, global_frame * 0.1)
            print(f"噪聲值: {noise_val:.3f}")
    
    def display_frame(self, frame):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_image)
        self.display_label.setPixmap(pixmap)

def main():
    app = QApplication(sys.argv)
    
    # 測試全域幀計數
    print("測試全域幀計數...")
    for i in range(10):
        update_global_frame_count()
        print(f"全域幀計數: {get_global_frame_count()}")
    
    # 測試噪聲函數
    print("測試噪聲函數...")
    for i in range(5):
        noise_val = pde_noise(i, i * 0.1)
        print(f"噪聲({i}, {i*0.1}): {noise_val:.3f}")
    
    # 創建測試窗口
    test_window = SimpleAnimationTestWindow()
    test_window.show()
    
    print("簡單動畫測試開始，按 Ctrl+C 退出")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 