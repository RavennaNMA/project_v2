# Location: project_v2/debug_detection_fixed.py
# Usage: 修正比例後的檢測調試工具 - 使用正確的 607:1080 比例

import sys
import cv2
import numpy as np
import time
import random
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont

class CameraSimulator(QThread):
    """攝像頭模擬器 - 使用正確比例"""
    
    frame_ready = pyqtSignal(np.ndarray, list)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.use_camera = False
        self.camera = None
        self.frame_count = 0
        
        # 模擬人臉檢測數據
        self.simulate_faces = True
        self.face_positions = []
        self.init_face_movement()
        
        # 啟動時嘗試自動開啟攝像頭
        self.try_enable_camera()
        
    def init_face_movement(self):
        """初始化人臉移動參數"""
        self.face_center_x = 540  # 屏幕中心
        self.face_center_y = 960
        self.face_velocity_x = random.uniform(-2, 2)  # 移動速度
        self.face_velocity_y = random.uniform(-2, 2)
        
    def try_enable_camera(self):
        """嘗試啟用攝像頭"""
        try:
            test_camera = cv2.VideoCapture(0)
            if test_camera.isOpened():
                ret, _ = test_camera.read()
                if ret:
                    self.camera = test_camera
                    self.use_camera = True
                    print("🎥 攝像頭自動啟用成功 - 使用正確比例 607:1080")
                else:
                    test_camera.release()
                    print("📹 攝像頭無法讀取畫面，使用模擬模式")
            else:
                test_camera.release()
                print("📹 攝像頭不可用，使用模擬模式")
        except Exception as e:
            print(f"📹 攝像頭初始化失敗: {e}，使用模擬模式")
        
    def generate_moving_face(self):
        """生成移動的人臉位置"""
        # 更新人臉位置（讓它緩慢移動）
        self.face_center_x += self.face_velocity_x
        self.face_center_y += self.face_velocity_y
        
        # 邊界檢測和反彈
        if self.face_center_x < 200 or self.face_center_x > 880:
            self.face_velocity_x *= -1
        if self.face_center_y < 300 or self.face_center_y > 1600:
            self.face_velocity_y *= -1
            
        # 保持在邊界內
        self.face_center_x = max(200, min(880, self.face_center_x))
        self.face_center_y = max(300, min(1600, self.face_center_y))
        
        # 生成人臉矩形
        size = 150  # 固定大小便於測試
        x = int(self.face_center_x - size/2)
        y = int(self.face_center_y - size/2)
        self.face_positions = [(x, y, size, size)]
        
        if hasattr(self, '_last_logged_frame') and self.frame_count - self._last_logged_frame > 300:
            print(f"人臉位置: ({int(self.face_center_x)}, {int(self.face_center_y)})")
            self._last_logged_frame = self.frame_count
    
    def toggle_camera(self):
        """切換攝像頭/模擬模式"""
        if self.use_camera:
            # 切換到模擬模式
            if self.camera:
                self.camera.release()
                self.camera = None
            self.use_camera = False
            print("切換到模擬模式")
        else:
            # 嘗試開啟攝像頭
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                self.use_camera = True
                print("切換到攝像頭模式")
            else:
                print("無法開啟攝像頭，保持模擬模式")
                self.camera = None
    
    def run(self):
        self.running = True
        
        while self.running:
            if self.use_camera and self.camera and self.camera.isOpened():
                # 真實攝像頭模式
                ret, frame = self.camera.read()
                if ret:
                    frame = self.process_camera_frame(frame)
                    faces = []  # 暫時空的，可以整合實際檢測
                else:
                    frame = self.generate_test_frame()
                    faces = self.face_positions if self.simulate_faces else []
            else:
                # 模擬模式
                frame = self.generate_test_frame()
                faces = self.face_positions if self.simulate_faces else []
            
            self.frame_ready.emit(frame, faces)
            
            # 每幀更新人臉位置（讓人臉移動）
            if self.simulate_faces:
                self.generate_moving_face()
            
            self.frame_count += 1
            self.msleep(16)  # ~60 FPS
    
    def process_camera_frame(self, raw_frame):
        """處理攝像頭畫面 - 使用修正後的正確比例"""
        height, width = raw_frame.shape[:2]
        
        # 快速檢查：如果已經是正確尺寸，直接返回
        if width == 1080 and height == 1920:
            return raw_frame
        
        # 確保輸入是標準相機格式 (1920x1080)
        if width != 1920 or height != 1080:
            raw_frame = cv2.resize(raw_frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        # 使用正確的比例計算（修正後）
        target_crop_width = 607  # 正確比例：1080 * (1080/1920) = 607
        crop_x = 656  # 正確位置：(1920 - 607) // 2 = 656
        crop_y = 0
        
        # 裁切畫面：從1920x1080裁切出中間的607x1080區域（正確比例）
        cropped_frame = raw_frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        
        # 縮放到目標尺寸1080x1920（保持正確比例，不會拉伸變形）
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        # 添加比例修正標記
        cv2.putText(portrait_frame, "FIXED RATIO: 607:1080", (20, 1850), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(portrait_frame, "No more face stretching!", (20, 1880), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return portrait_frame
    
    def generate_test_frame(self):
        """生成測試畫面 - 使用修正後的正確比例處理"""
        # 先生成標準攝像頭格式的測試畫面
        raw_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        
        # 創建漸變背景
        for y in range(1080):
            intensity = int(50 + 30 * np.sin(y * 0.005 + self.frame_count * 0.02))
            raw_frame[y, :] = [intensity//3, intensity//2, intensity]
        
        # 添加網格背景
        for i in range(0, 1920, 100):
            cv2.line(raw_frame, (i, 0), (i, 1080), (60, 60, 60), 1)
        for i in range(0, 1080, 100):
            cv2.line(raw_frame, (0, i), (1920, i), (60, 60, 60), 1)
        
        # 標記裁切區域
        # 舊的錯誤裁切區域（紅色）
        old_x, old_w = 622, 675
        cv2.rectangle(raw_frame, (old_x, 0), (old_x + old_w, 1080), (0, 0, 255), 3)
        cv2.putText(raw_frame, "OLD: 675px", (old_x, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # 新的正確裁切區域（綠色）
        new_x, new_w = 656, 607
        cv2.rectangle(raw_frame, (new_x, 0), (new_x + new_w, 1080), (0, 255, 0), 3)
        cv2.putText(raw_frame, "NEW: 607px", (new_x, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 現在使用正確的裁切處理
        return self.process_camera_frame(raw_frame)
    
    def toggle_face_simulation(self):
        """切換人臉模擬"""
        self.simulate_faces = not self.simulate_faces
        if self.simulate_faces:
            self.init_face_movement()
        print(f"人臉模擬: {'開啟' if self.simulate_faces else '關閉'}")
    
    def stop(self):
        self.running = False
        if self.camera:
            self.camera.release()


class FixedDetectionWindow(QMainWindow):
    """修正比例後的檢測窗口"""
    
    def __init__(self):
        super().__init__()
        self.setupUI()
        self.setupCamera()
        
    def setupUI(self):
        """設置UI"""
        self.setWindowTitle("Fixed Ratio Detection Tool - 607:1080")
        
        # 使用與main.py相同的窗口尺寸 1080x1920
        self.window_width = 1080
        self.window_height = 1920
        self.setFixedSize(self.window_width, self.window_height)
        
        # 中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 攝像頭顯示標籤
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(self.window_width, self.window_height)
        self.camera_label.setStyleSheet("background-color: black;")
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.camera_label)
        central_widget.setLayout(layout)
        
        # 設置窗口樣式
        self.setStyleSheet("""
            QMainWindow {
                background-color: black;
            }
            QLabel {
                color: white;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            }
        """)
        
    def setupCamera(self):
        """設置攝像頭模擬器"""
        self.camera_simulator = CameraSimulator()
        self.camera_simulator.frame_ready.connect(self.update_frame)
        self.camera_simulator.start()
        
        print("🔧 修正比例檢測工具已初始化")
        print(f"📊 窗口尺寸: {self.window_width}x{self.window_height}")
        print("🎯 比例修正:")
        print("  🔴 舊版本: 675:1080 = 0.625 (太寬，人臉被拉瘦)")
        print("  🟢 新版本: 607:1080 = 0.5625 (正確的9:16比例)")
        print("  📐 修正差異: 68像素，完全解決拉伸問題")
        print("\n🎮 控制鍵:")
        print("  Space  - 切換人臉模擬")
        print("  C      - 切換攝像頭/模擬模式")
        print("  Q/ESC  - 退出")
        
    def update_frame(self, frame, faces):
        """更新畫面"""
        try:
            # 添加調試信息
            self.draw_debug_info(frame, faces)
            
            # 繪製模擬人臉框
            if faces:
                for x, y, w, h in faces:
                    # 檢測框（藍色）
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 3)
                    cv2.putText(frame, "SIMULATED FACE", (x, y-15), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            
            # 轉換為Qt格式並顯示
            self.display_frame(frame)
            
        except Exception as e:
            print(f"更新畫面時發生錯誤: {e}")
    
    def draw_debug_info(self, frame, faces):
        """繪製調試信息"""
        # 時間戳
        timestamp = time.strftime("%H:%M:%S")
        cv2.putText(frame, timestamp, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
        
        # 比例信息
        cv2.putText(frame, "FIXED RATIO DEBUG", (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
        cv2.putText(frame, "Crop: 607x1080 -> 1080x1920", (20, 140), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, "Ratio: 0.5625 (9:16)", (20, 170), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # 攝像頭狀態
        mode_text = "Camera Mode" if self.camera_simulator.use_camera else "Simulation Mode"
        cv2.putText(frame, mode_text, (20, 220), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        # 人臉狀態
        face_text = f"Faces: {'ON' if self.camera_simulator.simulate_faces else 'OFF'} ({len(faces)})"
        cv2.putText(frame, face_text, (20, 260), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        
        # 控制提示
        controls = [
            "SPACE: Toggle Face Simulation",
            "C: Toggle Camera Mode", 
            "Q/ESC: Quit"
        ]
        
        y_offset = frame.shape[0] - 150
        for i, control in enumerate(controls):
            cv2.putText(frame, control, (20, y_offset + i*30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
    
    def display_frame(self, frame):
        """顯示畫面"""
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        # 轉換為QImage
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        
        # 轉換為QPixmap並顯示
        pixmap = QPixmap.fromImage(q_image)
        self.camera_label.setPixmap(pixmap)
    
    def keyPressEvent(self, event):
        """鍵盤事件處理"""
        key = event.key()
        
        if key == Qt.Key.Key_Space:
            # 切換人臉模擬
            self.camera_simulator.toggle_face_simulation()
            
        elif key == Qt.Key.Key_C:
            # 切換攝像頭模式
            self.camera_simulator.toggle_camera()
            
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            # 退出
            self.close()
        
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """關閉事件"""
        print("正在關閉修正比例調試工具...")
        self.camera_simulator.stop()
        self.camera_simulator.wait()
        event.accept()


def main():
    """主函數"""
    print("🔍 修正比例檢測調試工具")
    print("=" * 50)
    print("📐 問題: 主程序使用錯誤比例 675:1080 = 0.625")
    print("📐 修正: 使用正確比例 607:1080 = 0.5625")
    print("🎯 效果: 完全解決人臉拉伸變形問題")
    print("=" * 50)
    
    app = QApplication(sys.argv)
    
    # 設置應用程序樣式
    app.setStyle('Fusion')
    
    # 創建並顯示調試窗口
    debug_window = FixedDetectionWindow()
    debug_window.show()
    
    print("✅ 修正比例調試工具已啟動")
    print("📱 窗口尺寸: 1080x1920")
    print("🎥 攝像頭處理: 使用正確比例 607:1080")
    print("🎯 現在人臉不會再被拉瘦了！")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 