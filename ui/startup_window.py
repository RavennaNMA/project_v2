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
    
    start_requested = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.font_manager = FontManager()
        self.camera_manager = CameraManager()
        self.esp32_controller = ESP32Controller()
        
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        
        self.esp32_status_labels = {}
        self.connection_timer = None
        
        self.is_loading = True
        self.current_frame = None
        self.camera_started = False
        
        self.setup_ui()
        self.load_devices()
        
        self.is_loading = False
        
        QTimer.singleShot(100, self.start_default_camera)
        QTimer.singleShot(500, self.test_esp32_connections)
        
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.update_connection_status)
        self.connection_timer.start(2000)
        
    def setup_ui(self):
        """設定 UI"""
        self.setWindowTitle("System v2 - 啟動設定")
        self.setFixedSize(1200, 800)
        
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
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #4a90e2;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QComboBox {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555555;
                padding: 5px;
                font-size: 13px;
                border-radius: 3px;
            }
            QCheckBox {
                color: white;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QGroupBox {
                color: #4a90e2;
                font-size: 14px;
                font-weight: bold;
                border: 2px solid #3a3a3a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 左側：相機預覽區
        preview_group = QGroupBox("相機預覽")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(15, 20, 15, 15)
        
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(400, 640)
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
        self.control_combo.setEnabled(False)
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
        
        # 模式設定區
        mode_group = QGroupBox("模式設定")
        mode_layout = QVBoxLayout()
        mode_layout.setContentsMargins(15, 20, 15, 15)
        mode_layout.setSpacing(10)
        
        # 模式選項
        self.fullscreen_check = QCheckBox("全螢幕模式")
        self.fullscreen_check.setChecked(True)
        mode_layout.addWidget(self.fullscreen_check)
        
        self.debug_check = QCheckBox("顯示偵錯資訊")
        self.debug_check.setChecked(False)
        mode_layout.addWidget(self.debug_check)
        
        self.no_llm_check = QCheckBox("No LLM 模式（測試用）")
        self.no_llm_check.setChecked(False)
        mode_layout.addWidget(self.no_llm_check)
        
        self.mini_mode_check = QCheckBox("Mini 模式（縮小視窗）")
        self.mini_mode_check.setChecked(False)
        mode_layout.addWidget(self.mini_mode_check)
        
        self.tts_check = QCheckBox("啟用語音朗讀")
        self.tts_check.setChecked(False)
        mode_layout.addWidget(self.tts_check)
        
        # 新增：無ESP32模式
        self.no_esp32_check = QCheckBox("無ESP32模式（跳過硬體控制）")
        self.no_esp32_check.setChecked(False)
        self.no_esp32_check.toggled.connect(self.on_no_esp32_toggled)
        mode_layout.addWidget(self.no_esp32_check)
        
        mode_group.setLayout(mode_layout)
        settings_layout.addWidget(mode_group)
        
        # 啟動按鈕
        settings_layout.addStretch()
        
        self.start_btn = QPushButton("啟動系統")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5ba0f2;
            }
            QPushButton:pressed {
                background-color: #3a80d2;
            }
        """)
        self.start_btn.clicked.connect(self.on_start_clicked)
        settings_layout.addWidget(self.start_btn)
        
        settings_layout.addSpacing(20)
        main_layout.addWidget(settings_container)
        
    def on_no_esp32_toggled(self, checked):
        """無ESP32模式切換"""
        if checked:
            # 禁用ESP32相關控制
            self.test_btn.setEnabled(False)
            self.test_btn.setText("無ESP32模式")
            
            # 更新狀態顯示
            for esp_name in ['A', 'B', 'C']:
                self.esp32_status_labels[esp_name].setText("跳過")
                self.esp32_status_labels[esp_name].setStyleSheet("color: #ffa500; font-weight: normal;")
        else:
            # 啟用ESP32相關控制
            self.test_btn.setEnabled(True)
            self.test_btn.setText("測試ESP32連接")
            
            # 重新測試連接
            self.test_esp32_connections()
            
    def load_devices(self):
        """載入可用裝置"""
        # 載入相機
        for i in range(3):
            self.camera_combo.addItem(f"相機 {i}", i)
            
    def start_default_camera(self):
        """啟動預設相機"""
        if not self.camera_started:
            self.camera_manager.start(0)
            self.camera_manager.frame_ready.connect(self.on_frame_ready)
            self.preview_timer.start(30)
            self.camera_started = True
            
    def on_camera_changed(self, index):
        """相機切換"""
        if self.is_loading or index < 0:
            return
            
        camera_index = self.camera_combo.itemData(index)
        if camera_index is not None:
            self.camera_manager.stop()
            self.camera_manager.start(camera_index)
            
    def on_frame_ready(self, frame):
        """更新相機畫面"""
        self.current_frame = frame
        
    def update_preview(self):
        """更新預覽畫面"""
        if self.current_frame is not None:
            height, width = self.current_frame.shape[:2]
            
            # 計算縮放比例以適應預覽區域
            target_width = 400
            target_height = 640
            scale = min(target_width/width, target_height/height)
            
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # 縮放畫面
            resized = cv2.resize(self.current_frame, (new_width, new_height))
            
            # 轉換為RGB並顯示
            rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            
            from PyQt6.QtGui import QImage
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.preview_label.setPixmap(QPixmap.fromImage(qt_image))
            
    def test_esp32_connections(self):
        """測試ESP32連接"""
        if self.no_esp32_check.isChecked():
            print("無ESP32模式，跳過連接測試")
            return
            
        print("測試ESP32連接...")
        
        # 測試連接
        try:
            if not hasattr(self, 'esp32_controller'):
                self.esp32_controller = ESP32Controller()
                
            connections = self.esp32_controller.test_all_connections()
            
            for esp_name, is_connected in connections.items():
                if is_connected:
                    self.esp32_status_labels[esp_name].setText("已連接")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #4ae24a; font-weight: normal;")
                else:
                    self.esp32_status_labels[esp_name].setText("未連接")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #ff6b6b; font-weight: normal;")
                    
        except Exception as e:
            print(f"ESP32連接測試錯誤: {e}")
            for esp_name in ['A', 'B', 'C']:
                self.esp32_status_labels[esp_name].setText("錯誤")
                self.esp32_status_labels[esp_name].setStyleSheet("color: #ff6b6b; font-weight: normal;")
                
    def update_connection_status(self):
        """定期更新連接狀態"""
        if not self.no_esp32_check.isChecked() and hasattr(self, 'esp32_controller'):
            connections = self.esp32_controller.get_esp32_connections()
            
            for esp_name, is_connected in connections.items():
                if is_connected:
                    self.esp32_status_labels[esp_name].setText("已連接")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #4ae24a; font-weight: normal;")
                else:
                    self.esp32_status_labels[esp_name].setText("未連接")
                    self.esp32_status_labels[esp_name].setStyleSheet("color: #ff6b6b; font-weight: normal;")
                    
    def on_start_clicked(self):
        """啟動按鈕點擊"""
        # 檢查ESP32連接（如果不是無ESP32模式）
        if not self.no_esp32_check.isChecked():
            all_connected = True
            if hasattr(self, 'esp32_controller'):
                connections = self.esp32_controller.get_esp32_connections()
                for esp_name, is_connected in connections.items():
                    if not is_connected:
                        all_connected = False
                        break
            else:
                all_connected = False
                
            if not all_connected:
                reply = QMessageBox.question(
                    self, 
                    'ESP32未連接',
                    'ESP32尚未完全連接，是否仍要啟動系統？',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return
                    
        # 收集啟動參數
        params = {
            'camera_index': self.camera_combo.currentData(),
            'arduino_port': 'ESP32_TCP' if not self.no_esp32_check.isChecked() else None,
            'fullscreen': self.fullscreen_check.isChecked(),
            'debug_mode': self.debug_check.isChecked(),
            'no_llm_mode': self.no_llm_check.isChecked(),
            'mini_mode': self.mini_mode_check.isChecked(),
            'tts_enabled': self.tts_check.isChecked(),
            'no_esp32_mode': self.no_esp32_check.isChecked(),
            'debug_text_size': 16,
            'caption_text_size': 28
        }
        
        # 停止預覽
        self.preview_timer.stop()
        self.camera_manager.stop()
        
        if self.connection_timer:
            self.connection_timer.stop()
            
        # 發送啟動信號
        self.start_requested.emit(params)
        
        # 關閉視窗
        self.close()
        
    def closeEvent(self, event):
        """關閉事件"""
        self.preview_timer.stop()
        self.camera_manager.stop()
        
        if self.connection_timer:
            self.connection_timer.stop()
            
        if hasattr(self, 'esp32_controller'):
            self.esp32_controller.disconnect()
            
        event.accept()

