# Location: project_v2/ui/main_window.py
# Usage: 主視窗，整合所有功能模組

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QPixmap, QFont, QFontDatabase, QCursor
import os
import cv2
import numpy as np
import time

from core import StateMachine, SystemState, CameraManager, FaceDetector, ESP32Controller
from core.ssr_controller import SSRController
from core.osc_controller import OSCController  # 新增OSC控制器
from ui.detection_overlay import DetectionOverlay
from ui.caption_widget import CaptionWidget
from services import OllamaService, ImageService, TTSService
from utils import ConfigLoader, FontManager


class MainWindow(QMainWindow):
    """主程式視窗"""
    
    def __init__(self, startup_params):
        super().__init__()
        self.startup_params = startup_params
        
        # 設定縮放因子和視窗尺寸
        self.scale_factor = 0.5 if startup_params.get('mini_mode', False) else 1.0
        
        if startup_params.get('fullscreen', False):
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                self.window_width = screen_geometry.width()
                self.window_height = screen_geometry.height()
            else:
                self.window_width = 1080
                self.window_height = 1920
        else:
            base_width = 1080
            base_height = 1920
            self.window_width = int(base_width * self.scale_factor)
            self.window_height = int(base_height * self.scale_factor)
        
        print(f"視窗尺寸設定: {self.window_width}x{self.window_height} (縮放: {self.scale_factor})")
        
        # 載入設定
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_period_config()
        self.weapon_config = self.config_loader.load_weapon_config()
        
        print(f"已載入 weapon_config.csv: {len(self.weapon_config)} 個武器")
        if self.startup_params['no_llm_mode']:
            print(f"No-LLM調試模式將使用以下武器配置:")
            for weapon_id, info in self.weapon_config.items():
                print(f"   武器{weapon_id}: {info['name']} (Pin: {info['pin']}, Image: {info['image_path']})")
        
        # 初始化元件
        self.init_components()
        self.setup_ui()
        self.connect_signals()
        
        # 啟動系統 - 延遲啟動相機以避免黑屏
        QTimer.singleShot(100, self.start_system)
        
    def init_components(self):
        """初始化系統元件"""
        from utils import AnimConfigLoader
        self.anim_config_loader = AnimConfigLoader()
        
        self.state_machine = StateMachine(self.config, self.anim_config_loader)
        self.camera_manager = CameraManager()
        self.face_detector = FaceDetector(self.config)
        
        # ESP32 控制器
        self.esp32_controller = None
        self.no_esp32_mode = self.startup_params.get('no_esp32_mode', False)
        
        if not self.no_esp32_mode and self.startup_params['arduino_port']:
            self.esp32_controller = ESP32Controller()
            self.esp32_controller.connect()
        elif self.no_esp32_mode:
            print("無ESP32模式啟用 - 跳過硬體連接")
            
        # OSC控制器
        self.osc_controller = OSCController(self)
        self.osc_controller.start()
        
        # 燈光控制器 (新版)
        from core.ssr_controller import LightingController
        self.lighting_controller = LightingController(
            self.esp32_controller, 
            self.osc_controller,
            no_esp32_mode=self.no_esp32_mode
        )
        
        # 兼容性別名
        self.ssr_controller = self.lighting_controller
        
        # 連接燈光控制器信號到debug顯示
        self.lighting_controller.status_changed.connect(self.on_lighting_status_changed)
        self.lighting_controller.debug_message.connect(self.on_lighting_debug_message)
        
        # 用於debug顯示的燈光指令記錄
        self.recent_light_commands = []
        
        # 服務
        self.ollama_service = OllamaService()
        self.image_service = ImageService()
        
        tts_enabled = self.startup_params.get('tts_enabled', True)
        self.tts_service = TTSService(enabled=tts_enabled)
        
        if self.tts_service.is_available():
            print(f"TTS 服務已啟用")
        
        # 狀態
        self.current_screenshot_path = None
        self.current_weapons = []
        self.weapon_display_index = 0
        self.robot_mode = False  # 新增：機器人模式標記
        
        # 狀態完成追蹤
        self.caption_completed = False
        self.tts_completed = True
        self.wait_timer_completed = False
        self.caption_displayed = False
        
        # FPS 計算
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)
        self.frame_count = 0
        self.current_fps = 0
        
        # ESP32 C計時器
        self.esp32_c_timer = QTimer()
        self.esp32_c_timer.timeout.connect(self.on_esp32_c_timeout)
        
        # 兼容性別名
        self.arduino_controller = self.esp32_controller
        
    def setup_ui(self):
        """設定 UI"""
        title = "DefenseSystem" + (" - Mini Mode" if self.startup_params.get('mini_mode', False) else "")
        self.setWindowTitle(title)
        
        # 設定視窗大小和隱藏游標
        if self.startup_params['fullscreen']:
            self.showFullScreen()
            # 隱藏滑鼠游標
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            # 移除macOS攝像頭指示燈（綠點）
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | 
                               Qt.WindowType.WindowStaysOnTopHint |
                               Qt.WindowType.NoDropShadowWindowHint)
            # 設定窗口屬性以避免系統級UI元素
            self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            # 確保窗口在最前
            self.raise_()
            self.activateWindow()
        else:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.resize(self.window_width, self.window_height)
            # 視窗模式也隱藏游標
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
        
        # 中央元件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet("background-color: black;")
        
        # 相機顯示
        self.camera_label = QLabel(self.central_widget)
        self.camera_label.resize(self.window_width, self.window_height)
        self.camera_label.setScaledContents(True)
        
        # 載入提示
        self.loading_label = QLabel("系統啟動中...", self.central_widget)
        self.loading_label.setStyleSheet(f"""
            color: white;
            font-size: {int(20 * self.scale_factor)}px;
            background-color: rgba(0, 0, 0, 128);
            padding: {int(10 * self.scale_factor)}px;
        """)
        self.loading_label.adjustSize()
        self.loading_label.move(
            (self.window_width - self.loading_label.width()) // 2,
            (self.window_height - self.loading_label.height()) // 2
        )
        
        # 偵測動畫覆蓋層
        self.detection_overlay = DetectionOverlay(self.central_widget)
        self.detection_overlay.resize(self.window_width, self.window_height)
        self.detection_overlay.hide()
        
        # 截圖顯示
        self.screenshot_label = QLabel(self.central_widget)
        self.screenshot_label.resize(self.window_width, self.window_height)
        self.screenshot_label.setScaledContents(True)
        self.screenshot_label.hide()
        
        # 字幕顯示
        caption_text_size = self.startup_params.get('caption_text_size', 28)
        self.caption_widget = CaptionWidget(self.central_widget, self.scale_factor, caption_text_size)
        self.caption_widget.resize(self.window_width, self.window_height)
        self.caption_widget.hide()
        
        # 武器圖片顯示
        self.weapon_label = QLabel(self.central_widget)
        self.weapon_label.resize(self.window_width, self.window_height)
        self.weapon_label.setScaledContents(True)
        self.weapon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weapon_label.hide()
        
        # 黑屏遮罩
        self.black_overlay = QLabel(self.central_widget)
        self.black_overlay.resize(self.window_width, self.window_height)
        self.black_overlay.setStyleSheet("background-color: black;")
        self.black_overlay.hide()
        
        # Debug 顯示
        if self.startup_params['debug_mode']:
            self.debug_label = QLabel(self.central_widget)
            self.debug_label.move(int(5 * self.scale_factor), int(5 * self.scale_factor))
            self.debug_label.resize(int(450 * self.scale_factor), int(800 * self.scale_factor))
            debug_font_size = int(self.startup_params.get('debug_text_size', 16) * self.scale_factor)
            self.debug_label.setStyleSheet(f"""
                color: white;
                background-color: rgba(0, 0, 0, 192);
                padding: {int(8 * self.scale_factor)}px;
                font-family: monospace;
                font-size: {debug_font_size}px;
                font-weight: bold;
            """)
            self.debug_label.raise_()
            self.debug_label.show()
            
    def connect_signals(self):
        """連接信號"""
        # 狀態機信號
        self.state_machine.state_changed.connect(self.on_state_changed)
        self.state_machine.screenshot_requested.connect(self.take_screenshot)
        self.state_machine.llm_analysis_requested.connect(self.start_llm_analysis)
        self.state_machine.cal_window_fade_requested.connect(self.on_cal_window_fade_requested)
        self.state_machine.detect_frame_fade_requested.connect(self.on_detect_frame_fade_requested)
        self.state_machine.caption_display_requested.connect(self.display_caption)
        self.state_machine.spotlight_requested.connect(self.on_spotlight_requested)
        self.state_machine.weapon_display_requested.connect(self.display_weapons)
        self.state_machine.reset_requested.connect(self.reset_system)
        
        # 🔥 新增：狀態燈光控制信號
        self.state_machine.state_lighting_requested.connect(self.lighting_controller.handle_state_lighting)
        
        # 相機信號
        self.camera_manager.frame_ready.connect(self.process_frame)
        
        # 人臉偵測信號
        self.face_detector.face_detected.connect(self.on_face_detected)
        
        # Ollama 服務信號
        self.ollama_service.analysis_complete.connect(self.on_llm_complete)
        
        # 字幕完成信號
        self.caption_widget.typing_complete.connect(self.on_caption_typing_complete)
        self.caption_widget.tc_typing_complete.connect(self.on_tc_typing_complete)
        self.caption_widget.en_typing_complete.connect(self.on_en_typing_complete)
        
        # TTS 信號連接
        if hasattr(self, 'tts_service') and self.tts_service is not None:
            self.tts_service.tts_started.connect(self.on_tts_started)
            self.tts_service.tts_finished.connect(self.on_tts_finished)
            self.tts_service.tts_error.connect(self.on_tts_error)
            self.tts_service.tts_progress.connect(self.on_tts_progress)
            self.tts_service.tts_progress.connect(self.caption_widget.update_tts_progress)
            self.tts_service.tts_word_progress.connect(self.on_tts_word_progress)
        
        # SSR控制器信號
        self.ssr_controller.spotlight_ready.connect(self.on_spotlight_ready)
        self.ssr_controller.caption_lighting_ready.connect(self.on_caption_lighting_ready)
        
    def on_robot_arrive(self):
        """處理機器人到達事件（從OSC觸發）"""
        if self.state_machine.current_state not in [SystemState.CAPTION, SystemState.IMG_SHOW]:
            print("收到/robotarrive OSC指令，進入機器人模式")
            self.robot_mode = True
            # 強制觸發截圖和分析流程
            self.state_machine.transition_to(SystemState.SCREENSHOT_TRIGGER)
            
    def take_screenshot(self):
        """擷取螢幕截圖"""
        # 無論哪種模式都擷取真實的webcam截圖
        screenshot_path = self.camera_manager.take_screenshot()
        if screenshot_path:
            self.current_screenshot_path = screenshot_path
            print(f"Screenshot saved: {screenshot_path}")
            
            if self.startup_params['no_llm_mode']:
                if hasattr(self, 'config_loader'):
                    debug_response = self.config_loader.get_debug_response()
                    self.state_machine.on_llm_complete(debug_response)
            else:
                self.start_llm_analysis(screenshot_path)
        else:
            print("錯誤：無法擷取webcam截圖")
                    
    def start_llm_analysis(self, image_path):
        """開始 AI 分析"""
        weapon_list = self.config_loader.get_weapon_list()
        llm_timeout = self.config.get('llm_response_timeout', 10)
        
        # 根據模式選擇不同的prompt和圖片
        if self.robot_mode:
            # 載入機器人專用prompt
            self.ollama_service.load_robot_prompt()
            # 在機器人模式下，使用robot.png而不是webcam截圖進行LLaVA分析
            robot_image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'robot_img', 'robot.png')
            analysis_image_path = robot_image_path
            print(f"機器人模式：使用robot.png進行LLaVA分析: {robot_image_path}")
        else:
            # 使用正常prompt
            self.ollama_service.load_normal_prompt()
            analysis_image_path = image_path
            
        print(f"開始LLM分析: 超時設定 = {llm_timeout}秒, 模式 = {'機器人' if self.robot_mode else '正常'}")
        self.ollama_service.analyze_image(analysis_image_path, weapon_list, llm_timeout)
        
    def display_weapons(self, weapon_ids):
        """顯示武器"""
        print(f"display_weapons() called with weapon_ids: {weapon_ids}")
        
        if not weapon_ids:
            print("武器列表為空，直接完成")
            self.state_machine.on_weapon_display_complete()
            return
            
        print(f"開始顯示 {len(weapon_ids)} 個武器: {weapon_ids}")
        
        self.caption_widget.hide()
        self.screenshot_label.hide()
        self.black_overlay.show()
        
        if hasattr(self, 'debug_label') and self.debug_label.isVisible():
            self.debug_label.raise_()
            
        self.weapon_display_index = 0
        self.current_weapons = weapon_ids
        self.display_next_weapon()
        
    def display_next_weapon(self):
        """顯示下一個武器"""
        if self.weapon_display_index >= len(self.current_weapons):
            self.black_overlay.hide()
            # 武器顯示完成，返回偵測狀態燈光
            self.lighting_controller.set_detecting_lighting()
            self.state_machine.on_weapon_display_complete()
            return
            
        weapon_id = self.current_weapons[self.weapon_display_index]
        weapon_info = self.weapon_config.get(weapon_id)
        
        print(f"Displaying weapon - ID: {weapon_id}, Index: {self.weapon_display_index}")
        
        if weapon_info:
            # 顯示武器圖片
            self.show_weapon_image(weapon_info)
            
            # 控制 ESP32 A (武器) 和燈光
            if not self.no_esp32_mode and self.esp32_controller and weapon_info['pin']:
                print(f"ESP32 A Control: Pin {weapon_info['pin']} -> HIGH for {weapon_info['high_time']}ms")
                self.esp32_controller.control_pin(
                    weapon_info['pin'],
                    weapon_info['wait_before'],
                    weapon_info['high_time'],
                    weapon_info['wait_after']
                )
            
            # 🔥 修復：不論是否為no_esp32_mode，都使用LightingController來處理武器燈光
            # LightingController已經內建支援no_esp32_mode的模擬顯示和OSC發送
            self.lighting_controller.activate_weapon_light(weapon_id, weapon_info['high_time'])
                    
            self.weapon_display_index += 1
            total_time = weapon_info.get('wait_before', 0) + weapon_info.get('high_time', 1000) + weapon_info.get('wait_after', 500)
            QTimer.singleShot(total_time, self.display_next_weapon)
        else:
            self.weapon_display_index += 1
            self.display_next_weapon()
            
    # 舊的武器燈光控制方法已移除，現在使用 LightingController
        
    def on_state_changed(self, state):
        """狀態變更處理"""
        print(f"State changed to: {state.value}")
        
        if state == SystemState.DETECTING:
            # 🔥 重新顯示攝影機即時畫面
            self.camera_label.show()
            
            # 隱藏其他覆蓋層
            self.screenshot_label.hide()
            self.caption_widget.hide()
            self.weapon_label.hide()
            self.black_overlay.hide()
            
            # ESP32 C控制
            if not self.no_esp32_mode and self.esp32_controller:
                self.esp32_controller.set_esp32_pin_state('C', 4, 'HIGH', 0)
                # 啟動10秒計時器
                self.esp32_c_timer.stop()
                self.esp32_c_timer.start(self.config.get('esp32_c_timeout', 10000))
                
        elif state in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
            # 在這些狀態中清除檢測動畫
            self.detection_overlay.clear_detections()
            
            if hasattr(self, 'debug_label') and self.debug_label.isVisible():
                self.debug_label.raise_()
                
        # SPOTLIGHT狀態的燈光控制已由LightingController處理
                
        elif state == SystemState.RESET:
            self.reset_system()
            
    def on_esp32_c_timeout(self):
        """ESP32 C超時處理"""
        if self.state_machine.current_state == SystemState.DETECTING:
            if not self.no_esp32_mode and self.esp32_controller:
                print("ESP32 C timeout - turning OFF")
                self.esp32_controller.set_esp32_pin_state('C', 4, 'LOW', 0)
        self.esp32_c_timer.stop()
        
    def reset_system(self):
        """重置系統"""
        print("System reset")
        
        # 重置機器人模式
        self.robot_mode = False
        
        # 🔥 重新顯示攝影機畫面
        self.camera_label.show()
        
        # 隱藏所有覆蓋層
        self.detection_overlay.clear_detections()
        self.screenshot_label.hide()
        self.caption_widget.hide()
        self.weapon_label.hide()
        self.black_overlay.hide()
        
        # 重置 cal windows fade 狀態
        if hasattr(self.detection_overlay, 'window_effect'):
            self.detection_overlay.window_effect.reset_fade_state()
            print("重置 Cal Windows fade 狀態")
        
        # 清除狀態
        self.current_screenshot_path = None
        self.current_weapons = []
        
        # 重置狀態追蹤
        self.caption_completed = False
        self.tts_completed = True
        self.wait_timer_completed = False
        self.caption_displayed = False
        self.pending_caption_response = None
        
        # 使用新的燈光控制器重置燈光
        print("🔄 重置燈光系統")
        self.lighting_controller.reset_lighting()
    
    def on_lighting_status_changed(self, status):
        """處理燈光狀態變化"""
        import time
        timestamp = time.strftime("%H:%M:%S")
        
        # 記錄最近的燈光指令
        self.recent_light_commands.append(f"[{timestamp}] {status}")
        
        # 只保留最近10條記錄
        if len(self.recent_light_commands) > 10:
            self.recent_light_commands.pop(0)
    
    def on_lighting_debug_message(self, message):
        """🔥 新增：處理燈光控制器的 debug 訊息"""
        import time
        timestamp = time.strftime("%H:%M:%S")
        
        # 記錄最近的燈光指令
        self.recent_light_commands.append(f"[{timestamp}] {message}")
        
        # 只保留最近15條記錄（增加顯示數量）
        if len(self.recent_light_commands) > 15:
            self.recent_light_commands.pop(0)
            
    def update_debug_info(self):
        """更新 Debug 資訊"""
        if hasattr(self, 'debug_label'):
            detection_time = self.state_machine.get_detection_time()
            
            if self.no_esp32_mode:
                esp32_status = "No ESP32 Mode"
            else:
                esp32_status = "Connected" if self.esp32_controller and self.esp32_controller.is_connected else "Not connected"
                
            llm_mode = "No LLM" if self.startup_params['no_llm_mode'] else "Normal"
            mode = "Mini Mode" if self.startup_params.get('mini_mode', False) else "Full Mode"
            robot_status = "Robot Mode" if self.robot_mode else "Human Mode"
            
            weapons_display = "None"
            if hasattr(self, 'current_weapons') and self.current_weapons:
                weapons_display = f"[{', '.join(self.current_weapons)}]"
            
            ssr_status = "Off"
            if hasattr(self, 'ssr_controller'):
                if self.state_machine.current_state in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
                    ssr_status = "Active"
            
            debug_text = f"""State: {self.state_machine.current_state.value}
FPS: {self.current_fps}
Detection Time: {detection_time:.1f}s
Mode: {robot_status}
Controller: {esp32_status}
SSR: {ssr_status}
LLM Mode: {llm_mode}
Display: {mode}
Weapons: {weapons_display}
Window: {self.window_width}x{self.window_height}
OSC: A={self.osc_controller.get_status()}"""

            if not self.no_esp32_mode and self.esp32_controller:
                esp32_connections = self.esp32_controller.get_esp32_connections()
                esp32_status_lines = []
                for esp_name, is_connected in esp32_connections.items():
                    status = "✓" if is_connected else "✗"
                    esp32_status_lines.append(f"ESP32 {esp_name}: {status}")
                debug_text += "\n\n=== ESP32 連接狀態 ===\n" + "\n".join(esp32_status_lines)
                
                # 添加真實ESP32腳位狀態
                all_pin_states = self.esp32_controller.get_esp32_pin_states()
                esp32_pin_lines = []
                
                # ESP32 A (武器控制)
                if 'A' in all_pin_states:
                    pins_a = []
                    for weapon_id, weapon_info in self.weapon_config.items():
                        if weapon_info['pin']:
                            arduino_pin = weapon_info['pin']
                            if arduino_pin in range(2, 12):
                                esp_pin_map = {2:4, 3:5, 4:12, 5:13, 6:14, 7:16, 8:17, 9:18, 10:19, 11:21}
                                if arduino_pin in esp_pin_map:
                                    esp_pin = esp_pin_map[arduino_pin]
                                    state = all_pin_states['A'].get(esp_pin, 'LOW')
                                    pins_a.append(f"{weapon_info['name']}(D{arduino_pin}/G{esp_pin}):{state}")
                    if pins_a:
                        esp32_pin_lines.append("ESP32 A 武器:")
                        esp32_pin_lines.extend([f"  {p}" for p in pins_a])
                
                # ESP32 B (SSR控制)
                if 'B' in all_pin_states:
                    esp32_pin_lines.append("ESP32 B SSR:")
                    ssr1_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23]
                    ssr1_states = []
                    for pin in ssr1_pins:
                        state = all_pin_states['B'].get(pin, 'LOW')
                        ssr1_states.append(f"G{pin}:{state}")
                    
                    for i in range(0, len(ssr1_states), 4):
                        esp32_pin_lines.append(f"  SSR1: {' '.join(ssr1_states[i:i+4])}")
                    
                    ssr2_state = all_pin_states['B'].get(25, 'LOW')
                    esp32_pin_lines.append(f"  SSR2(G25):{ssr2_state}")

                # ESP32 C (安裝控制)
                if 'C' in all_pin_states:
                    install_state = all_pin_states['C'].get(4, 'LOW')
                    esp32_pin_lines.append("ESP32 C:")
                    esp32_pin_lines.append(f"  Installation(G4):{install_state}")
                
                if esp32_pin_lines:
                    debug_text += "\n\n=== ESP32 腳位狀態 ===\n" + "\n".join(esp32_pin_lines)
                    
            elif self.no_esp32_mode:
                debug_text += "\n\n=== 無ESP32模式 ===\n模擬硬體控制"
                
                # 🔥 修正：直接讀取燈光控制器的模擬狀態
                virtual_pin_lines = []
                simulated_states = self.lighting_controller.simulated_states
                
                # 虛擬 ESP32 A (武器控制)
                virtual_pin_lines.append("虛擬 ESP32 A 武器:")
                for weapon_id, weapon_info in self.weapon_config.items():
                    if weapon_info['pin']:
                        arduino_pin = weapon_info['pin']
                        if arduino_pin in range(2, 12):
                            esp_pin_map = {2:4, 3:5, 4:12, 5:13, 6:14, 7:16, 8:17, 9:18, 10:19, 11:21}
                            if arduino_pin in esp_pin_map:
                                esp_pin = esp_pin_map[arduino_pin]
                                virtual_state = simulated_states['A'].get(esp_pin, 'LOW')
                                virtual_pin_lines.append(f"  {weapon_info['name']}(D{arduino_pin}/G{esp_pin}):{virtual_state}")
                
                # 虛擬 ESP32 B (SSR控制)
                virtual_pin_lines.append("虛擬 ESP32 B SSR:")
                esp32b_pins = self.lighting_controller.all_esp32b_pins
                ssr1_states = []
                for pin in esp32b_pins:
                    virtual_state = simulated_states['B'].get(pin, 'LOW')
                    ssr1_states.append(f"G{pin}:{virtual_state}")
                
                # 分行顯示（每行4個）
                for i in range(0, len(ssr1_states), 4):
                    virtual_pin_lines.append(f"  {' '.join(ssr1_states[i:i+4])}")

                # 虛擬 ESP32 C (安裝控制)
                install_virtual_state = simulated_states['C'].get(4, 'LOW')
                virtual_pin_lines.append("虛擬 ESP32 C:")
                virtual_pin_lines.append(f"  Installation(G4):{install_virtual_state}")
                
                debug_text += "\n\n=== 虛擬腳位狀態 ===\n" + "\n".join(virtual_pin_lines)
            
            # 添加最近的燈光指令記錄
            if hasattr(self, 'recent_light_commands') and self.recent_light_commands:
                debug_text += "\n\n=== 最近燈光指令 ==="
                for cmd in self.recent_light_commands[-5:]:  # 顯示最近5條
                    debug_text += f"\n{cmd}"
                
            self.debug_label.setText(debug_text)
            self.debug_label.raise_()
            
    def process_frame(self, frame):
        """處理相機畫面 - 恢復完整的裁切和檢測邏輯"""
        self.frame_count += 1
        
        # 更新全域幀計數（用於 cal windows 動畫）
        try:
            from ui.cal_windows_effect import update_global_frame_count
            update_global_frame_count()
        except ImportError:
            pass  # 如果模組不可用，忽略錯誤
        
        # 隱藏載入提示
        if not hasattr(self, 'first_frame_received'):
            self.first_frame_received = False
        if not self.first_frame_received:
            self.first_frame_received = True
            self.loading_label.hide()
        
        cropped_frame = self.crop_frame_to_portrait_fast(frame)
        
        # 根據 mini mode 進行縮放
        if self.startup_params.get('mini_mode', False):
            target_width = int(1080 * 0.5)
            target_height = int(1920 * 0.5)
        else:
            target_width = 1080
            target_height = 1920
        
        if cropped_frame.shape[1] != target_width or cropped_frame.shape[0] != target_height:
            cropped_frame = cv2.resize(cropped_frame, (target_width, target_height), 
                                     interpolation=cv2.INTER_LINEAR)  # 已經是最快的品質插值

        try:
            # 🔧 修復：在裁切後的畫面上進行人臉檢測，而不是原始完整畫面
            detection_result = self.face_detector.process_frame(cropped_frame)
            current_state = self.state_machine.current_state
            
            faces = []
            if detection_result:
                # 由於現在在裁切後的畫面上檢測，座標已經是正確的
                # 只需要進行最終的縮放調整
                adjusted_bbox = self.adjust_detection_coordinates_for_cropped_frame(
                    detection_result, cropped_frame.shape, target_width, target_height)
                
                if adjusted_bbox:
                    self.last_detection_bbox = adjusted_bbox
                    
                    # 只在 DETECTING 狀態更新狀態機
                    if current_state == SystemState.DETECTING:
                        self.state_machine.update_face_detection(True)
                    
                    if current_state not in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
                        # 從週期配置獲取底部偏移參數
                        bottom_offset_ratio = self.config.get('detect_frame_bottom_offset', 0.2)
                        
                        # 將檢測框向上偏移（根據配置的底部偏移比例）
                        frame_offset_y = int(adjusted_bbox['height'] * bottom_offset_ratio)
                        adjusted_y = int(adjusted_bbox['y']) - frame_offset_y
                        
                        # 確保Y座標不會超出畫面邊界
                        adjusted_y = max(0, adjusted_y)
                        
                        face_rect = (int(adjusted_bbox['x']), adjusted_y, 
                                   int(adjusted_bbox['width']), int(adjusted_bbox['height']))
                        faces.append(face_rect)
                else:
                    self.last_detection_bbox = None
                    if current_state == SystemState.DETECTING:
                        self.state_machine.update_face_detection(False)
            else:
                self.last_detection_bbox = None
                if current_state == SystemState.DETECTING:
                    self.state_machine.update_face_detection(False)
                    
        except Exception as e:
            print(f"Face detection processing error: {e}")
            faces = []
            self.last_detection_bbox = None
            if hasattr(self, 'state_machine'):
                current_state = self.state_machine.current_state
                if current_state == SystemState.DETECTING:
                    self.state_machine.update_face_detection(False)
        
        # 按照參考代碼：在主循環中更新視覺矩形
        if hasattr(self.detection_overlay, 'update_visual_rects_main_loop'):
            self.detection_overlay.update_visual_rects_main_loop(faces)
        else:
            # 兼容性調用
            self.detection_overlay.update_faces(faces)
        
        # 在幀上繪製檢測框
        final_frame = self.detection_overlay.draw_on_frame(cropped_frame)
        
        # 顯示畫面 - 使用正確的QImage轉換
        qimage = CameraManager.frame_to_qimage(final_frame)
        pixmap = QPixmap.fromImage(qimage)
        self.camera_label.setPixmap(pixmap)
        
    def crop_frame_to_portrait_fast(self, frame):
        """FPS 優化：快速版本的豎屏裁切"""
        height, width = frame.shape[:2]
        
        # 快速檢查：如果已經是正確尺寸，直接返回
        if width == 1080 and height == 1920:
            return frame
        
        # 確保輸入是標準相機格式
        if width != 1920 or height != 1080:
            frame = cv2.resize(frame, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            height, width = 1080, 1920
        
        target_crop_width = 675  # 預計算，避免重複計算
        
        crop_x = 622  # 預計算：(1920 - 675) // 2
        crop_y = 0
        
        cropped_frame = frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        
        # 縮放到目標尺寸1080x1920（保持正確比例，不會拉伸變形）
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
        
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
        
    def adjust_detection_for_crop(self, detection_result, frame_shape):
        """調整偵測結果以適應裁切後的畫面"""
        original_height, original_width = frame_shape[:2]
        display_width = self.window_width
        display_height = self.window_height
        
        aspect_ratio_original = original_width / original_height
        aspect_ratio_display = display_width / display_height
        
        if aspect_ratio_original > aspect_ratio_display:
            scale = display_height / original_height
            cropped_width = int(display_width / scale)
            cropped_height = original_height
            crop_x = (original_width - cropped_width) // 2
            crop_y = 0
        else:
            scale = display_width / original_width
            cropped_width = original_width
            cropped_height = int(display_height / scale)
            crop_x = 0
            crop_y = (original_height - cropped_height) // 2
            
        face_left = detection_result['x'] - crop_x
        face_top = detection_result['y'] - crop_y
        
        if face_left + detection_result['width'] < 0 or face_left > cropped_width:
            return None
        if face_top + detection_result['height'] < 0 or face_top > cropped_height:
            return None
        
        adjusted_x = max(0, min(face_left, cropped_width))
        adjusted_y = max(0, min(face_top, cropped_height))
        adjusted_width = min(detection_result['width'], cropped_width - adjusted_x)
        adjusted_height = min(detection_result['height'], cropped_height - adjusted_y)
        
        if adjusted_width < 10 or adjusted_height < 10:
            return None
        
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
        
    def on_face_detected(self, detected):
        """人臉偵測回調"""
        if hasattr(self.state_machine, 'update_face_detection'):
            self.state_machine.update_face_detection(detected)
            
    def on_llm_complete(self, response):
        """AI 分析完成"""
        print(f"LLM分析完成，回應類型: {type(response)}")
        print(f"回應內容: {response}")
        print(f"當前狀態機狀態: {self.state_machine.current_state.value}")
        self.state_machine.on_llm_complete(response)
        
    def display_caption(self, response):
        """顯示字幕和截圖"""
        print(f"display_caption 被調用:")
        print(f"   回應類型: {type(response)}")
        print(f"   回應內容: {response}")
        print(f"   當前模式: {'No-LLM' if self.startup_params['no_llm_mode'] else 'Normal'}")
        
        self.caption_displayed = True
        self.caption_completed = False
        self.tts_completed = False
        self.wait_timer_completed = False
        self.pending_caption_response = response
        
        print("=== CAPTION STATE: Starting SSR1 (caption lighting) ===")
        self.ssr_controller.start_caption_lighting()
        self.ssr_controller.print_debug_status()
        
        esp32_connected = not self.no_esp32_mode and self.esp32_controller and self.esp32_controller.is_connected
        
        if not esp32_connected or self.startup_params.get('no_llm_mode', False):
            QTimer.singleShot(500, self.on_caption_lighting_ready)
        else:
            print("正常模式，等待SSR1信號")
            
    def on_caption_lighting_ready(self):
        """SSR1燈光準備完成，現在可以顯示字幕"""
        print("=== SSR1 READY: Now displaying caption and screenshot ===")
        
        if not hasattr(self, 'pending_caption_response') or not self.pending_caption_response:
            print("沒有待處理的字幕回應")
            return
            
        response = self.pending_caption_response
        
        # 🔥 清除偵測動畫但保留即時攝影機畫面作為背景
        self.detection_overlay.clear_detections()
        # 不隱藏 camera_label，讓截圖淡入顯示在其上方
        
        # 🔥 顯示截圖（取代即時攝影機畫面）- 使用淡入效果
        if self.current_screenshot_path and os.path.exists(self.current_screenshot_path):
            print(f"📸 顯示截圖: {self.current_screenshot_path}")
            print(f"   檔案大小: {os.path.getsize(self.current_screenshot_path)} bytes")
            
            pixmap = QPixmap(self.current_screenshot_path)
            print(f"   QPixmap 載入狀態: isNull={pixmap.isNull()}, size={pixmap.width()}x{pixmap.height()}")
            
            if not pixmap.isNull():
                self.screenshot_label.setPixmap(pixmap)
                self.screenshot_label.raise_()  # 確保截圖在最上層
                
                # 🔧 清除任何樣式，保持純淨顯示
                self.screenshot_label.setStyleSheet("")
                
                # 🔥 新增：使用淡入效果顯示截圖
                screenshot_fade_duration = int(self.config.get('screenshot_fade_in', 1.0) * 1000)
                print(f"📸 截圖將以 {screenshot_fade_duration}ms 淡入效果顯示")
                self.fade_in_widget(self.screenshot_label, screenshot_fade_duration)
                
                print("📸 截圖設置完成（含淡入效果）")
            else:
                print("❌ QPixmap 載入失敗，圖片可能損壞")
        else:
            print(f"⚠️ 截圖檔案問題:")
            print(f"   current_screenshot_path: {self.current_screenshot_path}")
            print(f"   檔案存在: {os.path.exists(self.current_screenshot_path) if self.current_screenshot_path else 'N/A'}")
            
        # 解析回應
        if isinstance(response, dict):
            caption_tc = response.get('caption_tc', '')
            caption_en = response.get('caption_en', '') or response.get('caption', '')
            weapons = response.get('weapons', [])
        else:
            caption_tc = response
            caption_en = response
            weapons = []
            
        self.current_weapons = weapons
        
        typing_speed = self.config.get('caption_typing_speed', 50)
        
        print(f"準備顯示字幕:")
        print(f"   中文: {caption_tc[:50]}..." if caption_tc else "   中文: (無)")
        print(f"   英文: {caption_en[:50]}..." if caption_en else "   英文: (無)")
        print(f"   打字速度: {typing_speed}ms/字")
        
        if caption_tc or caption_en:
            # TTS 相關處理
            tts_enabled = self.startup_params.get('tts_enabled', False)
            no_llm_mode = self.startup_params.get('no_llm_mode', False)
            tts_skip_reason = ""
            
            # 🔥 修復：機器人模式應該要有完整的TTS和字幕功能，不受no_llm_mode影響
            robot_mode_override = getattr(self, 'robot_mode', False)
            
            if not tts_enabled:
                tts_skip_reason = "TTS已禁用"
            elif no_llm_mode and not robot_mode_override:
                tts_skip_reason = "No-LLM模式"
            elif not caption_en:
                tts_skip_reason = "無英文字幕"
                
            # 配置字幕打字效果
            # 🔥 機器人模式下即使no_llm_mode為True也要啟用TTS
            should_enable_tts = tts_enabled and caption_en and hasattr(self, 'tts_service') and (not no_llm_mode or robot_mode_override)
            if should_enable_tts:
                # TTS模式：字幕與語音同步
                print("啟用TTS同步字幕顯示")
                self.caption_widget.enable_tts_sync(caption_en)
                
                # 估算TTS時長並設定超時保護
                words = caption_en.split()
                effective_wpm = 140  # 有效WPM（考慮標點和停頓）
                estimated_duration = len(words) / effective_wpm * 60 if effective_wpm > 0 else 10
                timeout_duration = max(estimated_duration * 1.5, 8.0)  # 至少8秒，最多1.5倍預估時間
                print(f"設定TTS超時保護: {timeout_duration:.1f}秒")
                
                # 設定備用完成計時器
                self.tts_timeout_timer = QTimer()
                self.tts_timeout_timer.setSingleShot(True)
                self.tts_timeout_timer.timeout.connect(self.on_tts_timeout)
                self.tts_timeout_timer.start(int(timeout_duration * 1000))
                
                # 啟動TTS
                self.tts_service.speak_text(caption_en)
            else:
                if robot_mode_override and no_llm_mode:
                    print(f"機器人模式覆蓋: 原本會跳過TTS因為{tts_skip_reason}，但機器人模式需要TTS功能")
                print(f"跳過TTS播放: {tts_skip_reason}")
                self.tts_completed = True
            
            # 🔧 確保字幕元件可見並在最上層
            self.caption_widget.show()
            self.caption_widget.raise_()  # 確保字幕元件在最上層

            # 🔧 確保 debug 標籤始終在最上層
            if hasattr(self, 'debug_label') and self.debug_label.isVisible():
                self.debug_label.raise_()

            print(f"📺 字幕元件狀態:")
            print(f"   可見: {self.caption_widget.isVisible()}")
            print(f"   位置: {self.caption_widget.pos()}")
            print(f"   大小: {self.caption_widget.size()}")
            
            # 顯示字幕
            if caption_tc and caption_en:
                print(" 顯示雙語字幕")
                self.caption_widget.is_bilingual_mode = True  # 強制重置
                print(f"主程式呼叫 show_bilingual_caption, typing_speed={typing_speed}")
                self.caption_widget.show_bilingual_caption(caption_tc, caption_en, typing_speed)
                print(f"主程式: 計時器狀態: {self.caption_widget.display_timer.isActive()}")
            elif caption_en:
                print(" 顯示英文字幕")
                self.caption_widget.show_caption(caption_en, typing_speed)
            elif caption_tc:
                print(" 顯示中文字幕")
                self.caption_widget.show_caption(caption_tc, typing_speed)
                
            # 強制更新顯示
            self.caption_widget.update()
            QApplication.processEvents()  # 處理待處理的事件
        else:
            # 沒有字幕
            print("⚠️ 沒有字幕內容")
            self.caption_completed = True
            self.tts_completed = True  # 沒有TTS需要完成
            self.wait_timer_completed = True  # 沒有等待計時器需要完成
            self.check_caption_completion()
            
        # 清除待處理的回應數據
        self.pending_caption_response = None
            
    def on_caption_typing_complete(self):
        """字幕打字完成"""
        print("字幕打字完成")
        self.caption_completed = True
        
        # 啟動等待計時器（與舊版邏輯一致）
        wait_time = self.config.get('caption_wait_after', 2.0) * 1000
        print(f"字幕打字完成，等待 {wait_time}ms 後繼續")
        QTimer.singleShot(int(wait_time), self.on_wait_timer_complete)
        
        self.check_caption_completion()
        
    def on_tc_typing_complete(self):
        """中文字幕打字完成"""
        print("中文字幕打字完成")
        
    def on_en_typing_complete(self):
        """英文字幕打字完成"""
        print("英文字幕打字完成")
        
    def check_caption_completion(self):
        """檢查字幕是否完全完成"""
        if self.caption_completed and self.tts_completed and self.wait_timer_completed:
            print("所有字幕相關任務完成，通知狀態機")
            self.state_machine.on_caption_complete()
            
    def on_tts_started(self):
        """TTS開始播放"""
        print("TTS開始播放")
        self.tts_completed = False
        
    def on_tts_finished(self):
        """TTS播放完成"""
        print("TTS播放完成")
        self.tts_completed = True
        
        if hasattr(self, 'tts_timeout_timer'):
            self.tts_timeout_timer.stop()
            
        # TTS完成後直接檢查完成狀態，等待計時器已在打字完成時啟動
        self.check_caption_completion()
        
    def on_wait_timer_complete(self):
        """等待計時器完成"""
        print("等待計時器完成")
        self.wait_timer_completed = True
        self.check_caption_completion()
        
    def on_tts_timeout(self):
        """TTS超時處理"""
        if not self.tts_completed:
            print("⚠️ TTS超時，強制完成字幕狀態")
            
            if hasattr(self, 'tts_service'):
                self.tts_service.stop()
                
            # 如果TTS同步還在進行，禁用它
            if hasattr(self.caption_widget, 'disable_tts_sync'):
                self.caption_widget.disable_tts_sync()
                
            # 停止超時計時器
            if hasattr(self, 'tts_timeout_timer'):
                self.tts_timeout_timer.stop()
                
            self.tts_completed = True
            self.check_caption_completion()
        
    def on_tts_error(self, error):
        """TTS錯誤處理"""
        print(f"TTS錯誤: {error}")
        self.on_tts_finished()
        
    def on_tts_progress(self, progress):
        """TTS播放進度"""
        pass
        
    def on_tts_word_progress(self, word, index, total):
        """TTS單詞進度"""
        pass
        
    def on_cal_window_fade_requested(self):
        """Cal Window消失請求"""
        if hasattr(self.detection_overlay, 'window_effect'):
            self.detection_overlay.window_effect.start_fade_out()
            
    def on_detect_frame_fade_requested(self):
        """Detect Frame消失請求"""
        if hasattr(self.detection_overlay, 'frame_effect'):
            self.detection_overlay.frame_effect.fade_out()
            
    def on_spotlight_requested(self):
        """聚光燈請求"""
        print("Spotlight requested - starting SSR spotlight")
        self.ssr_controller.start_spotlight()
                
    def on_spotlight_ready(self):
        """聚光燈準備完成"""
        print("Spotlight ready")
        if hasattr(self.state_machine, 'on_spotlight_ready'):
            self.state_machine.on_spotlight_ready()
            
    def show_weapon_image(self, weapon_info):
        """顯示武器圖片"""
        image_path = os.path.join("weapons_img", weapon_info['image_path'])
        
        print(f"📷 準備顯示武器圖片: {image_path}")
        print(f"   檔案存在: {os.path.exists(image_path)}")
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            print(f"   QPixmap載入狀態: isNull={pixmap.isNull()}, size={pixmap.width()}x{pixmap.height()}")
            
            if not pixmap.isNull():
                self.weapon_label.setPixmap(pixmap)
                
                # 🔥 確保武器圖片顯示在最上層
                self.weapon_label.raise_()
                
                fade_in_duration = int(weapon_info.get('image_fade_in', 1.0) * 1000)
                display_duration = int(weapon_info.get('image_display', 3.0) * 1000)
                fade_out_duration = int(weapon_info.get('image_fade_out', 1.0) * 1000)
                
                self.fade_in_widget(self.weapon_label, fade_in_duration)
                
                total_display_time = fade_in_duration + display_duration
                
                print(f"武器圖片時序: 淡入{fade_in_duration}ms + 顯示{display_duration}ms + 淡出{fade_out_duration}ms = 總計{total_display_time}ms")
                
                QTimer.singleShot(total_display_time, 
                                lambda: self.fade_out_widget(self.weapon_label, fade_out_duration))
            else:
                print(f"❌ QPixmap載入失敗，圖片可能損壞")
        else:
            print(f"❌ 找不到武器圖片: {image_path}")
            print(f"   當前工作目錄: {os.getcwd()}")
            print(f"   完整路徑: {os.path.abspath(image_path)}")
            
    def fade_in_widget(self, widget, duration=None):
        """淡入效果"""
        if duration is None:
            duration = int(self.config.get('screenshot_fade_in', 1.0) * 1000)
            
        effect = QGraphicsOpacityEffect()
        widget.setGraphicsEffect(effect)
        widget.show()
        
        self.fade_animation = QPropertyAnimation(effect, b"opacity")
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(0)
        self.fade_animation.setEndValue(1)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.start()
        
    def fade_out_widget(self, widget, duration=None):
        """淡出效果"""
        if duration is None:
            duration = int(self.config.get('screenshot_fade_out', 1.0) * 1000)
            
        effect = widget.graphicsEffect()
        if not effect:
            effect = QGraphicsOpacityEffect()
            widget.setGraphicsEffect(effect)
            
        self.fade_out_animation = QPropertyAnimation(effect, b"opacity")
        self.fade_out_animation.setDuration(duration)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_out_animation.finished.connect(widget.hide)
        self.fade_out_animation.start()
        
    def update_fps(self):
        """更新 FPS"""
        self.current_fps = self.frame_count
        self.frame_count = 0
        
        if self.startup_params['debug_mode']:
            self.update_debug_info()
            
    def start_system(self):
        """啟動系統"""
        self.state_machine.set_no_llm_mode(self.startup_params['no_llm_mode'])
        
        camera_index = self.startup_params.get('camera_index', 0)
        self.camera_manager.start(camera_index)
        
        self.first_frame_received = False
        self.state_machine.start()
        
    def closeEvent(self, event):
        """關閉事件"""
        self.state_machine.stop()
        self.camera_manager.stop()
        self.face_detector.release()
        
        if self.esp32_controller:
            self.esp32_controller.disconnect()
        
        if hasattr(self, 'ssr_controller'):
            self.ssr_controller.cleanup()
        
        if hasattr(self, 'tts_service'):
            print("Shutting down TTS service...")
            self.tts_service.shutdown()
            
        if hasattr(self, 'osc_controller'):
            self.osc_controller.stop()
            
        event.accept()

