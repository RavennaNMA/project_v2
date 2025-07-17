# Location: project_v2/ui/startup_window.py
# Usage: 啟動視窗，提供相機預覽、ESP32連接檢測等設定

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QLabel, QComboBox, QPushButton, QCheckBox, 
                           QGroupBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QFont
import cv2
import numpy as np

from core.camera_manager import CameraManager
from core.esp32_controller import ESP32Controller
from utils import FontManager


class StartupWindow(QMainWindow):
    """啟動設定視窗"""
    
    start_requested = pyqtSignal(dict)  # 發送啟動參數
    
    def __init__(self):
        super().__init__()
        self.font_manager = FontManager()
        self.camera_manager = CameraManager()
        self.esp32_controller = ESP32Controller()
        
        # 預覽更新計時器 - 必須在 setup_ui 之前初始化
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        
        # ESP32狀態標籤
        self.esp32_status_labels = {}
        self.connection_timer = None
        
        # 初始化屬性
        self.is_loading = True
        self.current_frame = None
        self.camera_started = False
        
        self.setup_ui()
        self.load_devices()
        
        # 載入完成
        self.is_loading = False
        
        # 延遲啟動相機，讓視窗先顯示
        QTimer.singleShot(100, self.start_default_camera)
        
        # 啟動時自動測試ESP32連接
        QTimer.singleShot(500, self.test_esp32_connections)
        
        # 定期更新ESP32連接狀態
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.update_connection_status)
        self.connection_timer.start(2000)  # 每2秒更新一次
        
    def setup_ui(self):
        """設定 UI"""
        self.setWindowTitle("System v2 - 啟動設定")
        self.setFixedSize(1200, 800)  # 增加寬度，減少高度
        
        # 設定樣式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                border: 1px solid #666666;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: normal;
                border-radius: 6px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #777777;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
                border-color: #555555;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
                border-color: #444444;
            }
            QComboBox {
                font-size: 13px;
                padding: 6px 8px;
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 4px;
                color: white;
            }
            QComboBox:hover {
                border-color: #666666;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #555555;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #aaaaaa;
            }
            QCheckBox {
                font-size: 13px;
                color: white;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border: 1px solid #4a90e2;
                border-radius: 3px;
            }
            QGroupBox {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #4a90e2;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #2b2b2b;
            }
        """)
        
        # 主容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)  # 改為水平佈局
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 左側：相機預覽區
        preview_group = QGroupBox("相機預覽")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(15, 20, 15, 15)
        
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(400, 640)  # 5:8 豎屏比例預覽 (1080x1920的縮小版)
        self.preview_label.setStyleSheet("""
            border: 2px solid #555555; 
            background-color: #1a1a1a;
            border-radius: 8px;
        """)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("載入相機中...")
        preview_layout.addWidget(self.preview_label)
        
        main_layout.addWidget(preview_group)
        
        # 右側：設定區
        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setSpacing(15)
        
        # 標題
        title_label = QLabel("System v2")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #4a90e2;
            margin-bottom: 15px;
            padding: 10px;
        """)
        settings_layout.addWidget(title_label)
        
        # 硬體設定區
        hardware_group = QGroupBox("硬體設定")
        hardware_layout = QVBoxLayout(hardware_group)
        hardware_layout.setContentsMargins(15, 20, 15, 15)
        hardware_layout.setSpacing(12)
        
        # 相機選擇
        camera_layout = QHBoxLayout()
        camera_label = QLabel("選擇相機:")
        camera_label.setMinimumWidth(100)
        camera_label.setStyleSheet("font-weight: normal;")
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumHeight(32)
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)
        camera_layout.addWidget(camera_label)
        camera_layout.addWidget(self.camera_combo, 1)
        hardware_layout.addLayout(camera_layout)
        
        # 控制介面選擇（ESP32）
        control_layout = QHBoxLayout()
        control_label = QLabel("控制介面:")
        control_label.setMinimumWidth(100)
        control_label.setStyleSheet("font-weight: normal;")
        self.control_combo = QComboBox()
        self.control_combo.setMinimumHeight(32)
        self.control_combo.addItem("ESP32 TCP/IP Control", "ESP32_TCP")
        self.control_combo.setEnabled(False)  # 固定為ESP32
        control_layout.addWidget(control_label)
        control_layout.addWidget(self.control_combo, 1)
        hardware_layout.addLayout(control_layout)
        
        # 測試連接按鈕
        test_layout = QHBoxLayout()
        self.test_btn = QPushButton("測試ESP32連接")
        self.test_btn.setMaximumWidth(120)
        self.test_btn.clicked.connect(self.test_esp32_connections)
        test_layout.addWidget(self.test_btn)
        test_layout.addStretch()
        hardware_layout.addLayout(test_layout)
        
        settings_layout.addWidget(hardware_group)
        
        # ESP32 連接狀態群組
        esp32_group = QGroupBox("ESP32 連接狀態")
        esp32_layout = QVBoxLayout()
        esp32_layout.setContentsMargins(15, 20, 15, 15)
        esp32_layout.setSpacing(10)
        
        # ESP32 A 狀態
        esp_a_layout = QHBoxLayout()
        esp_a_label = QLabel("ESP32 A (武器控制):")
        esp_a_label.setMinimumWidth(160)
        esp_a_label.setStyleSheet("font-weight: normal;")
        self.esp32_status_labels['A'] = QLabel("未連接")
        self.esp32_status_labels['A'].setStyleSheet("color: #ff6b6b; font-weight: normal;")
        esp_a_layout.addWidget(esp_a_label)
        esp_a_layout.addWidget(self.esp32_status_labels['A'])
        esp_a_layout.addStretch()
        esp32_layout.addLayout(esp_a_layout)
        
        # ESP32 B 狀態
        esp_b_layout = QHBoxLayout()
        esp_b_label = QLabel("ESP32 B (SSR控制):")
        esp_b_label.setMinimumWidth(160)
        esp_b_label.setStyleSheet("font-weight: normal;")
        self.esp32_status_labels['B'] = QLabel("未連接")
        self.esp32_status_labels['B'].setStyleSheet("color: #ff6b6b; font-weight: normal;")
        esp_b_layout.addWidget(esp_b_label)
        esp_b_layout.addWidget(self.esp32_status_labels['B'])
        esp_b_layout.addStretch()
        esp32_layout.addLayout(esp_b_layout)
        
        # ESP32 C 狀態
        esp_c_layout = QHBoxLayout()
        esp_c_label = QLabel("ESP32 C (安裝控制):")
        esp_c_label.setMinimumWidth(160)
        esp_c_label.setStyleSheet("font-weight: normal;")
        self.esp32_status_labels['C'] = QLabel("未連接")
        self.esp32_status_labels['C'].setStyleSheet("color: #ff6b6b; font-weight: normal;")
        esp_c_layout.addWidget(esp_c_label)
        esp_c_layout.addWidget(self.esp32_status_labels['C'])
        esp_c_layout.addStretch()
        esp32_layout.addLayout(esp_c_layout)
        
        esp32_group.setLayout(esp32_layout)
        settings_layout.addWidget(esp32_group)
        
        # 系統設定群組
        system_group = QGroupBox("系統設定")
        system_layout = QVBoxLayout()
        system_layout.setContentsMargins(15, 20, 15, 15)
        system_layout.setSpacing(10)
        
        # 全螢幕選項
        self.fullscreen_check = QCheckBox("全螢幕模式")
        self.fullscreen_check.toggled.connect(self.on_fullscreen_toggled)
        system_layout.addWidget(self.fullscreen_check)
        
        # Mini 模式選項
        self.mini_mode_check = QCheckBox("Mini 模式（0.5x 縮放）")
        system_layout.addWidget(self.mini_mode_check)
        
        # Debug 模式選項
        self.debug_check = QCheckBox("顯示除錯資訊")
        self.debug_check.setChecked(True)
        system_layout.addWidget(self.debug_check)
        
        # No LLM 模式選項
        self.no_llm_check = QCheckBox("No LLM 模式（除錯用）")
        system_layout.addWidget(self.no_llm_check)
        
        system_group.setLayout(system_layout)
        settings_layout.addWidget(system_group)
        
        # 狀態顯示
        self.status_label = QLabel("請測試ESP32連接後啟動系統")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            color: #ffd93d;
            font-size: 12px;
            font-weight: normal;
            margin-top: 10px;
            padding: 8px;
            background-color: rgba(255, 217, 61, 0.1);
            border: 1px solid rgba(255, 217, 61, 0.3);
            border-radius: 4px;
        """)
        settings_layout.addWidget(self.status_label)
        
        # 啟動按鈕
        start_btn = QPushButton("啟動系統")
        start_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 8px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2d5f8f;
            }
        """)
        start_btn.clicked.connect(self.on_start_clicked)
        settings_layout.addWidget(start_btn)
        
        # 添加彈性空間
        settings_layout.addStretch()
        
        main_layout.addWidget(settings_container)
        
    def on_fullscreen_toggled(self, checked):
        """全螢幕選項切換時"""
        if checked:
            # 全螢幕模式時停用 mini mode
            self.mini_mode_check.setChecked(False)
            self.mini_mode_check.setEnabled(False)
        else:
            self.mini_mode_check.setEnabled(True)
            
    def start_default_camera(self):
        """啟動預設相機"""
        if self.camera_combo.count() > 0:
            camera_data = self.camera_combo.itemData(0)
            if camera_data is not None and camera_data >= 0:
                self.on_camera_changed(0)
                
    def load_devices(self):
        """載入可用裝置"""
        # 載入相機
        cameras = CameraManager.get_available_cameras()
        self.camera_combo.clear()
        if cameras:
            for idx, name in cameras:
                self.camera_combo.addItem(name, idx)
        else:
            self.camera_combo.addItem("未偵測到相機", -1)
            
    def on_camera_changed(self, index):
        """相機選擇變更"""
        if self.is_loading:
            return
            
        if index >= 0:
            camera_index = self.camera_combo.currentData()
            if camera_index is not None and camera_index >= 0:
                self.start_camera_preview(camera_index)
                
    def start_camera_preview(self, camera_index):
        """開始相機預覽"""
        # 停止現有相機
        if self.camera_started:
            self.camera_manager.stop()
            self.preview_timer.stop()
            
        self.camera_manager.frame_ready.connect(self.on_frame_ready)
        self.camera_manager.error_occurred.connect(self.on_camera_error)
        self.camera_manager.start(camera_index)
        self.preview_timer.start(33)  # ~30 FPS
        self.camera_started = True
        self.status_label.setText("相機預覽中")
        
    def on_frame_ready(self, frame):
        """更新預覽畫面"""
        self.current_frame = frame
        
    def update_preview(self):
        """更新預覽顯示"""
        if self.current_frame is not None:
            # 💪 恢復豎屏預覽，匹配主視窗的實際裁切格式
            # 使用與主視窗相同的裁切邏輯
            cropped_frame = self.crop_frame_to_portrait(self.current_frame)
            
            # 縮放到預覽尺寸（5:8豎屏，適配1080x1920）
            preview_width = 400
            preview_height = 640
            
            resized = cv2.resize(cropped_frame, (preview_width, preview_height), 
                               interpolation=cv2.INTER_LINEAR)
            
            # 轉換為 QPixmap
            qimage = CameraManager.frame_to_qimage(resized)
            pixmap = QPixmap.fromImage(qimage)
            self.preview_label.setPixmap(pixmap)
            
    def crop_frame_to_portrait(self, frame):
        """從1920x1080相機畫面裁切出中間的1080x1920豎屏區域（與main_window相同邏輯）"""
        height, width = frame.shape[:2]
        
        # 確保輸入是標準相機格式
        if width != 1920 or height != 1080:
            frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        # 💪 適應1080x1920螢幕比例
        # 目標比例 1080:1920 = 5:8
        # 從1080高度計算對應的5:8寬度：1080 * 5/8 = 675像素
        target_crop_width = int(1080 * 5 / 8)  # 675像素
        
        # 從1920x1080裁切出中間的675x1080區域
        crop_x = (1920 - target_crop_width) // 2  # 居中裁切
        crop_y = 0
        
        # 裁切出正確比例的區域
        cropped_frame = frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        
        # 縮放到目標尺寸1080x1920（保持正確比例，不會拉伸變形）
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
        
    def test_esp32_connections(self):
        """測試ESP32連接"""
        self.status_label.setText("正在測試ESP32連接...")
        self.test_btn.setEnabled(False)
        
        # 連接ESP32控制器
        self.esp32_controller.connect()
        
        # 等待連接結果
        QTimer.singleShot(1000, self.update_connection_status)
        
    def update_connection_status(self):
        """更新連接狀態顯示"""
        connections = self.esp32_controller.get_esp32_connections()
        
        all_connected = True
        for esp_name, is_connected in connections.items():
            if esp_name in self.esp32_status_labels:
                if is_connected:
                    self.esp32_status_labels[esp_name].setText("已連接 ✓")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #51cf66;")
                else:
                    self.esp32_status_labels[esp_name].setText("未連接 ✗")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #ff6b6b;")
                    all_connected = False
                    
        self.test_btn.setEnabled(True)
        
        if all_connected and connections:
            self.status_label.setText("所有ESP32已連接，可以啟動系統")
            self.status_label.setStyleSheet("color: #51cf66; font-size: 12px;")
        elif connections:
            self.status_label.setText("部分ESP32未連接，系統可能無法正常運作")
            self.status_label.setStyleSheet("color: #ffd93d; font-size: 12px;")
        else:
            self.status_label.setText("正在等待ESP32連接...")
            self.status_label.setStyleSheet("color: #ffd93d; font-size: 12px;")
        
    def on_camera_error(self, error):
        """處理相機錯誤"""
        self.status_label.setText(f"相機錯誤: {error}")
        self.preview_label.setText("相機錯誤")
        
    def on_start_clicked(self):
        """啟動按鈕點擊"""
        # 檢查相機
        camera_index = self.camera_combo.currentData()
        if camera_index is None or camera_index < 0:
            QMessageBox.warning(self, "警告", "請選擇有效的相機")
            return
            
        # 停止連接狀態更新計時器
        if self.connection_timer:
            self.connection_timer.stop()
            
        # 斷開測試連接
        self.esp32_controller.disconnect()
        
        # 收集啟動參數
        params = {
            'camera_index': camera_index,
            'arduino_port': 'ESP32_TCP',  # 兼容性
            'fullscreen': self.fullscreen_check.isChecked(),
            'debug_mode': self.debug_check.isChecked(),
            'no_llm_mode': self.no_llm_check.isChecked(),
            'mini_mode': self.mini_mode_check.isChecked()
        }
        
        # 停止預覽
        self.preview_timer.stop()
        self.camera_manager.stop()
        
        # 發送啟動信號
        self.start_requested.emit(params)
        self.close()
        
    def closeEvent(self, event):
        """關閉事件"""
        # 停止計時器
        if hasattr(self, 'preview_timer'):
            self.preview_timer.stop()
            
        if hasattr(self, 'connection_timer') and self.connection_timer:
            self.connection_timer.stop()
            
        # 停止相機
        if hasattr(self, 'camera_manager'):
            self.camera_manager.stop()
            
        # 斷開ESP32連接
        if hasattr(self, 'esp32_controller'):
            self.esp32_controller.disconnect()
            
        event.accept()