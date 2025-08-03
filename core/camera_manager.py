# Location: project_v2/core/camera_manager.py
# Usage: 相機管理與畫面擷取

import cv2
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtGui import QImage
import os
from datetime import datetime


class CameraThread(QThread):
    """相機執行緒"""
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.is_running = False
        self.cap = None
        
    def run(self):
        """執行緒主迴圈"""
        try:
            # 使用 CAP_DSHOW 在 Windows 上可以加快相機開啟速度
            import platform
            if platform.system() == "Windows":
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(self.camera_index)
            
            # 🚀 FPS 優化：設定較小的緩衝區以減少延遲
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # 🚀 恢復高FPS：設定相機參數 - 支援高品質動畫
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            self.cap.set(cv2.CAP_PROP_FPS, 60)  #  恢復60 FPS支援流暢動畫
            
            # 🚀 FPS 優化：設定額外的相機優化參數
            try:
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*'MJPG'))  # 使用 MJPEG 壓縮
            except AttributeError:
                # 舊版本 OpenCV 相容性
                pass
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # 減少自動曝光計算
            
            if not self.cap.isOpened():
                self.error_occurred.emit("無法開啟相機")
                return
                
            self.is_running = True
            
            # 🚀 FPS 優化：減少預熱畫面數量
            for _ in range(3):  # 從 5 減少到 3
                self.cap.read()
            
            while self.is_running:
                ret, frame = self.cap.read()
                if ret:
                    # 不做裁切，保持原始比例
                    # 在顯示時再進行適當的縮放
                    self.frame_ready.emit(frame)
                else:
                    self.error_occurred.emit("讀取畫面失敗")
                    break
                    
                #  恢復60 FPS對應的睡眠時間 (1000ms / 60fps ≈ 16ms)
                self.msleep(16)  # 支援流暢動畫的60 FPS
                
        except Exception as e:
            self.error_occurred.emit(f"相機錯誤: {str(e)}")
        finally:
            if self.cap:
                self.cap.release()
                
    def stop(self):
        """停止執行緒"""
        self.is_running = False
        self.wait()


class CameraManager(QObject):
    """相機管理器"""
    frame_ready = pyqtSignal(np.ndarray)
    screenshot_saved = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.camera_thread = None
        self.current_frame = None
        self.camera_index = 0
        
        # 確保截圖目錄存在
        self.screenshot_dir = "webcam-shots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def start(self, camera_index=0):
        """啟動相機"""
        self.camera_index = camera_index
        
        if self.camera_thread and self.camera_thread.isRunning():
            self.stop()
            
        self.camera_thread = CameraThread(camera_index)
        self.camera_thread.frame_ready.connect(self._on_frame_ready)
        self.camera_thread.error_occurred.connect(self.error_occurred.emit)
        self.camera_thread.start()
        
    def stop(self):
        """停止相機"""
        if self.camera_thread:
            self.camera_thread.stop()
            self.camera_thread = None
            
    def _on_frame_ready(self, frame):
        """處理新畫面"""
        self.current_frame = frame.copy()
        self.frame_ready.emit(frame)
        
    def take_screenshot(self):
        """擷取當前畫面 - 使用與主視窗相同的裁切和尺寸"""
        if self.current_frame is None:
            self.error_occurred.emit("無可用畫面")
            return None
            
        # 💪 應用與主視窗相同的裁切邏輯
        processed_frame = self.crop_frame_to_portrait(self.current_frame)
            
        # 生成檔名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.jpg"
        filepath = os.path.join(self.screenshot_dir, filename)
        
        # 儲存處理後的圖片（與主視窗顯示一致）
        cv2.imwrite(filepath, processed_frame)
        self.screenshot_saved.emit(filepath)
        
        return filepath
    
    def crop_frame_to_portrait(self, frame):
        """裁切畫面為豎屏格式 - 與主視窗邏輯完全一致"""
        height, width = frame.shape[:2]
        
        # 快速檢查：如果已經是正確尺寸，直接返回
        if width == 1080 and height == 1920:
            return frame
        
        # 確保輸入是標準相機格式
        if width != 1920 or height != 1080:
            frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        # 💪 適應1080x1920螢幕比例
        # 目標比例 1080:1920 = 5:8
        # 從1080高度計算對應的5:8寬度：1080 * 5/8 = 675像素
        target_crop_width = 675  # 預計算，避免重複計算
        
        # 從1920x1080裁切出中間的675x1080區域
        crop_x = 622  # 預計算：(1920 - 675) // 2
        crop_y = 0
        
        # 🚀 使用更高效的切片操作
        cropped_frame = frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        
        # 縮放到目標尺寸1080x1920（保持正確比例，不會拉伸變形）
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
        
    @staticmethod
    def get_available_cameras():
        """取得可用相機列表"""
        cameras = []
        for i in range(10):  # 檢查前 10 個索引
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append((i, f"Camera {i}"))
                cap.release()
        return cameras
        
    @staticmethod
    def frame_to_qimage(frame):
        """將 OpenCV frame 轉換為 QImage"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        # BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        return QImage(rgb_frame.data, width, height, 
                     bytes_per_line, QImage.Format.Format_RGB888)