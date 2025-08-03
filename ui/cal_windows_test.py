# Location: project_v2/ui/cal_windows_test.py
# Usage: 科技感窗口效果測試示例

import cv2
import numpy as np
import time
from cal_windows_effect import DetectionWindowEffect

def test_standalone_mode():
    """測試獨立模式（LLM載入時使用）"""
    
    # 創建效果管理器
    effect = DetectionWindowEffect(screen_width=1280, screen_height=720)
    
    # 啟用獨立模式
    effect.enable_standalone_mode(True)
    
    # 創建測試畫面
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    print("開始獨立模式測試...")
    print("按 'q' 退出，按 's' 切換獨立模式")
    
    while True:
        # 清空畫面
        frame.fill(0)
        
        # 更新獨立模式窗口
        effect.update_standalone_mode()
        
        # 繪製所有窗口
        effect.draw_all_windows(frame, (0, 255, 255))  # 青色
        
        # 顯示信息
        cv2.putText(frame, f"Total Windows: {effect.get_total_window_count()}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Standalone Mode: {'ON' if effect.standalone_mode else 'OFF'}", 
                   (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0) if effect.standalone_mode else (0, 0, 255), 2)
        cv2.putText(frame, "Press 'q' to quit, 's' to toggle standalone mode", 
                   (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        # 繪製中心點（調試用）
        for i, (cx, cy) in enumerate(effect.standalone_center_points):
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)
            cv2.putText(frame, f"C{i+1}", (cx+10, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        cv2.imshow('Cal Windows Effect Test', frame)
        
        key = cv2.waitKey(16) & 0xFF  # ~60 FPS
        if key == ord('q'):
            break
        elif key == ord('s'):
            effect.enable_standalone_mode(not effect.standalone_mode)
    
    cv2.destroyAllWindows()

def test_with_fake_faces():
    """測試帶有模擬人臉檢測的效果"""
    
    effect = DetectionWindowEffect(screen_width=1280, screen_height=720)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # 模擬人臉位置
    fake_faces = [
        (300, 200, 150, 150),  # (x, y, w, h)
        (800, 300, 120, 120)
    ]
    
    print("開始人臉檢測模式測試...")
    print("按 'q' 退出，按 'f' 切換人臉檢測，按 's' 切換獨立模式")
    
    show_faces = True
    
    while True:
        frame.fill(0)
        
        # 更新效果
        if show_faces:
            effect.update_faces(fake_faces)
        else:
            effect.update_faces([])
        
        effect.update_standalone_mode()
        
        # 繪製人臉框（如果啟用）
        if show_faces:
            for x, y, w, h in fake_faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, "FACE", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # 繪製窗口效果
        effect.draw_all_windows(frame, (0, 255, 255))
        
        # 顯示信息
        info_text = [
            f"Total Windows: {effect.get_total_window_count()}",
            f"Face Detection: {'ON' if show_faces else 'OFF'}",
            f"Standalone Mode: {'ON' if effect.standalone_mode else 'OFF'}",
            "Press 'q' to quit, 'f' for faces, 's' for standalone"
        ]
        
        for i, text in enumerate(info_text):
            cv2.putText(frame, text, (10, 30 + i*30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        cv2.imshow('Cal Windows Effect Test', frame)
        
        key = cv2.waitKey(16) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('f'):
            show_faces = not show_faces
        elif key == ord('s'):
            effect.enable_standalone_mode(not effect.standalone_mode)
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Cal Windows Effect 測試程序")
    print("1. 獨立模式測試（LLM載入效果）")
    print("2. 人臉檢測模式測試")
    
    choice = input("請選擇測試模式 (1 或 2): ").strip()
    
    if choice == "1":
        test_standalone_mode()
    elif choice == "2":
        test_with_fake_faces()
    else:
        print("無效選擇，退出...") 