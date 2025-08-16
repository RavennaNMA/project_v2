#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試檢測框修復的簡單腳本
驗證檢測框只追蹤裁切區域內的人臉
"""

import cv2
import numpy as np
import sys
import os

# 添加項目路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_cropped_detection():
    """測試裁切後的人臉檢測"""
    print("🧪 測試裁切後的人臉檢測")
    
    # 模擬原始相機畫面 (1920x1080)
    original_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    # 在原始畫面中繪製一個人臉（在裁切區域外）
    cv2.rectangle(original_frame, (100, 500), (200, 600), (255, 255, 255), -1)
    cv2.putText(original_frame, "Face Outside", (100, 480), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # 在原始畫面中繪製一個人臉（在裁切區域內）
    cv2.rectangle(original_frame, (700, 500), (800, 600), (0, 255, 0), -1)
    cv2.putText(original_frame, "Face Inside", (700, 480), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    # 模擬裁切過程
    crop_x = 622
    crop_width = 675
    cropped_frame = original_frame[:, crop_x:crop_x + crop_width]
    
    # 縮放到目標尺寸 (1080x1920)
    target_frame = cv2.resize(cropped_frame, (1080, 1920))
    
    print(f"原始畫面尺寸: {original_frame.shape}")
    print(f"裁切區域: x={crop_x}, width={crop_width}")
    print(f"裁切後尺寸: {cropped_frame.shape}")
    print(f"目標尺寸: {target_frame.shape}")
    
    # 模擬檢測結果（在裁切區域內的人臉）
    mock_detection = {
        'x': 78,  # 在裁切區域內的相對位置
        'y': 500,
        'width': 100,
        'height': 100,
        'confidence': 0.9
    }
    
    # 測試座標調整函數
    from ui.main_window import MainWindow
    
    # 創建一個模擬的 MainWindow 實例
    class MockMainWindow:
        def __init__(self):
            self.startup_params = {'debug_mode': True}
            
        def adjust_detection_coordinates_for_cropped_frame(self, detection_result, cropped_shape, display_width, display_height):
            """🔧 新增：專門處理裁切後畫面的座標調整"""
            # 安全檢查
            if not detection_result or not isinstance(detection_result, dict):
                return None
                
            # 檢查必要的鍵是否存在
            if not all(key in detection_result for key in ['x', 'y', 'width', 'height']):
                return None
            
            # 裁切後的畫面尺寸（通常是1080x1920）
            cropped_height, cropped_width = cropped_shape[:2]
            
            # 檢查偵測框是否在裁切畫面範圍內
            face_left = detection_result['x']
            face_right = detection_result['x'] + detection_result['width']
            face_top = detection_result['y']
            face_bottom = detection_result['y'] + detection_result['height']
            
            # 如果人臉完全在畫面外，返回None
            if (face_right < 0 or face_left > cropped_width or 
                face_bottom < 0 or face_top > cropped_height):
                return None
            
            # 裁剪偵測框到畫面範圍內
            adjusted_x = max(0, min(face_left, cropped_width))
            adjusted_y = max(0, min(face_top, cropped_height))
            adjusted_width = min(detection_result['width'], cropped_width - adjusted_x)
            adjusted_height = min(detection_result['height'], cropped_height - adjusted_y)
            
            # 如果調整後的尺寸太小，忽略這個檢測
            if adjusted_width < 10 or adjusted_height < 10:
                return None
            
            # 最終縮放到顯示尺寸
            scale_x = display_width / cropped_width
            scale_y = display_height / cropped_height
            
            final_result = {
                'x': adjusted_x * scale_x,
                'y': adjusted_y * scale_y,
                'width': adjusted_width * scale_x,
                'height': adjusted_height * scale_y,
                'confidence': detection_result.get('confidence', 0)
            }
            
            return final_result
    
    mock_window = MockMainWindow()
    
    # 測試座標調整
    result = mock_window.adjust_detection_coordinates_for_cropped_frame(
        mock_detection, target_frame.shape, 1080, 1920)
    
    if result:
        print(f"✅ 檢測框座標調整成功:")
        print(f"   原始檢測: x={mock_detection['x']}, y={mock_detection['y']}")
        print(f"   調整後: x={result['x']:.1f}, y={result['y']:.1f}, w={result['width']:.1f}, h={result['height']:.1f}")
    else:
        print("❌ 檢測框座標調整失敗")
    
    # 保存測試圖片
    cv2.imwrite("test_original_frame.png", original_frame)
    cv2.imwrite("test_cropped_frame.png", cropped_frame)
    cv2.imwrite("test_target_frame.png", target_frame)
    
    print("📸 測試圖片已保存:")
    print("   test_original_frame.png - 原始畫面")
    print("   test_cropped_frame.png - 裁切後畫面")
    print("   test_target_frame.png - 目標尺寸畫面")

if __name__ == "__main__":
    test_cropped_detection() 