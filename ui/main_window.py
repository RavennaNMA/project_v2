# Location: project_v2/ui/main_window.py
# Usage: 主視窗，整合所有功能模組

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QPixmap, QFont, QFontDatabase
import os
import cv2
import numpy as np

from core import StateMachine, SystemState, CameraManager, FaceDetector, ArduinoController
from core.ssr_controller import SSRController  # 新增SSR控制器
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
        
        # 修正視窗尺寸：恢復豎屏格式1080x1920，適配直立螢幕
        if startup_params.get('fullscreen', False):
            # 全螢幕模式使用螢幕尺寸
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.geometry()
                self.window_width = screen_geometry.width()
                self.window_height = screen_geometry.height()
            else:
                # 備用尺寸（您的螢幕尺寸）
                self.window_width = 1080
                self.window_height = 1920
        else:
            # 視窗模式使用豎屏比例，適合您的1080x1920直立螢幕
            base_width = 1080   # 您的螢幕寬度
            base_height = 1920  # 您的螢幕高度  
            self.window_width = int(base_width * self.scale_factor)
            self.window_height = int(base_height * self.scale_factor)
        
        print(f"🖥️ 視窗尺寸設定: {self.window_width}x{self.window_height} (縮放: {self.scale_factor})")
        
        # 載入設定
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load_period_config()
        self.weapon_config = self.config_loader.load_weapon_config()
        
        # 新增：顯示武器配置載入信息（對no-llm調試很重要）
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
        # 核心元件 - 傳遞config_loader以支持調試模式
        self.state_machine = StateMachine(self.config, self.config_loader)
        self.camera_manager = CameraManager()
        self.face_detector = FaceDetector(self.config)
        
        # Arduino (選配)
        self.arduino_controller = None
        if self.startup_params['arduino_port']:
            self.arduino_controller = ArduinoController()
            self.arduino_controller.connect(self.startup_params['arduino_port'])
            
        # SSR控制器
        self.ssr_controller = SSRController(self.arduino_controller)
        
        # 服務
        self.ollama_service = OllamaService()
        self.image_service = ImageService()
        
        # TTS 服務 - 根據配置啟用
        tts_enabled = self.startup_params.get('tts_enabled', True)
        self.tts_service = TTSService(enabled=tts_enabled)
        
        # 設定TTS參數
        if self.tts_service.is_available():
            print(f"TTS 服務已啟用")
        
        # 狀態
        self.current_screenshot_path = None
        self.current_weapons = []
        self.weapon_display_index = 0
        
        # 狀態完成追蹤
        self.caption_completed = False
        self.tts_completed = True
        self.wait_timer_completed = False
        
        # 防止重複顯示字幕
        self.caption_displayed = False
        
        # FPS 計算
        self.fps_timer = QTimer()
        self.fps_timer.timeout.connect(self.update_fps)
        self.fps_timer.start(1000)
        self.frame_count = 0
        self.current_fps = 0
        
    def setup_ui(self):
        """設定 UI"""
        title = "DefenseSystem" + (" - Mini Mode" if self.startup_params.get('mini_mode', False) else "")
        self.setWindowTitle(title)
        
        # 設定視窗大小
        if self.startup_params['fullscreen']:
            self.showFullScreen()
        else:
            # 💪 修復視窗大小：移除邊框和標題欄，真正填滿螢幕
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.setFixedSize(self.window_width, self.window_height)
            
            # 確保視窗填滿螢幕（移動到左上角）
            self.move(0, 0)
            
        # 設定黑色背景
        self.setStyleSheet("background-color: black;")
        
        # 主容器
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 相機顯示
        self.camera_label = QLabel(self.central_widget)
        self.camera_label.resize(self.window_width, self.window_height)
        self.camera_label.setScaledContents(False)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #111;")
        
        # 載入中提示
        self.loading_label = QLabel("Loading camera...", self.central_widget)
        loading_font_size = int(self.startup_params.get('loading_text_size', 24) * self.scale_factor)
        self.loading_label.setStyleSheet("""
            color: white;
            font-size: %dpx;
            background-color: transparent;
        """ % loading_font_size)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.resize(self.window_width, 100)
        self.loading_label.move(0, self.window_height // 2 - 50)
        
        # 偵測動畫層
        self.detection_overlay = DetectionOverlay(self.central_widget)
        self.detection_overlay.resize(self.window_width, self.window_height)
        
        # 連接檢測狀態信號
        self.detection_overlay.detection_updated.connect(self.on_detection_state_changed)
        
        # 截圖顯示層
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
        self.weapon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.weapon_label.setScaledContents(False)
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
            self.debug_label.resize(int(450 * self.scale_factor), int(600 * self.scale_factor))
            debug_font_size = int(self.startup_params.get('debug_text_size', 16) * self.scale_factor)
            self.debug_label.setStyleSheet("""
                color: white;
                background-color: rgba(0, 0, 0, 192);
                padding: %dpx;
                font-family: monospace;
                font-size: %dpx;
                font-weight: bold;
            """ % (int(8 * self.scale_factor), debug_font_size))
            self.debug_label.show()
            
    def connect_signals(self):
        """連接信號"""
        # 狀態機信號
        self.state_machine.state_changed.connect(self.on_state_changed)
        self.state_machine.screenshot_requested.connect(self.take_screenshot)
        self.state_machine.llm_analysis_requested.connect(self.start_llm_analysis)
        self.state_machine.caption_display_requested.connect(self.display_caption)
        self.state_machine.spotlight_requested.connect(self.on_spotlight_requested)  # 新增
        self.state_machine.weapon_display_requested.connect(self.display_weapons)
        self.state_machine.reset_requested.connect(self.reset_system)
        
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
        
        # TTS 信號連接 - 確保即時字幕同步
        if hasattr(self, 'tts_service') and self.tts_service is not None:
            print("連接 TTS 服務信號以支援即時字幕同步...")
            
            # 連接 TTS 生命週期信號
            self.tts_service.tts_started.connect(self.on_tts_started)
            self.tts_service.tts_finished.connect(self.on_tts_finished)
            self.tts_service.tts_error.connect(self.on_tts_error)
            
            # 連接進度信號 - 這是即時打字效果的關鍵
            self.tts_service.tts_progress.connect(self.on_tts_progress)
            self.tts_service.tts_progress.connect(self.caption_widget.update_tts_progress)
            
            # 連接文字片段信號 - 提供更精細的同步
            self.tts_service.tts_word_progress.connect(self.on_tts_word_progress)
            
            print("TTS 即時字幕同步信號已連接")
            
        # SSR控制器信號
        self.ssr_controller.spotlight_ready.connect(self.on_spotlight_ready)
        self.ssr_controller.caption_lighting_ready.connect(self.on_caption_lighting_ready)  # 新增SSR1完成信號
        
    def start_system(self):
        """啟動系統"""
        # 設定 No LLM 模式
        self.state_machine.set_no_llm_mode(self.startup_params['no_llm_mode'])
        
        # 啟動相機
        self.camera_manager.start(self.startup_params['camera_index'])
        
        # 第一個畫面到達時隱藏載入提示
        self.first_frame_received = False
        
        # 啟動狀態機
        self.state_machine.start()
        
    def process_frame(self, frame):
        """處理相機畫面 - 修正檢測和動畫更新邏輯，完全匹配參考代碼"""
        self.frame_count += 1
        
        # 隱藏載入提示
        if not self.first_frame_received:
            self.first_frame_received = True
            self.loading_label.hide()
        
        # 🚀 FPS 優化：使用更快的裁切和縮放
        cropped_frame = self.crop_frame_to_portrait_fast(frame)
        
        # 根據 mini mode 進行縮放
        if self.startup_params.get('mini_mode', False):
            target_width = int(1080 * 0.5)
            target_height = int(1920 * 0.5)
        else:
            target_width = 1080
            target_height = 1920
        
        # 🚀 FPS 優化：只在必要時縮放，使用更快的插值
        if cropped_frame.shape[1] != target_width or cropped_frame.shape[0] != target_height:
            cropped_frame = cv2.resize(cropped_frame, (target_width, target_height), 
                                     interpolation=cv2.INTER_LINEAR)  # 已經是最快的品質插值

        try:
            detection_result = self.face_detector.process_frame(frame)
            current_state = self.state_machine.current_state
            
            faces = []
            if detection_result:
                # 調整偵測結果座標
                adjusted_bbox = self.adjust_detection_coordinates_fast(detection_result, frame.shape, target_width, target_height)
                if adjusted_bbox:
                    self.last_detection_bbox = adjusted_bbox
                    
                    # 只在 DETECTING 狀態更新狀態機
                    if current_state == SystemState.DETECTING:
                        self.state_machine.update_face_detection(True)
                    
                    if current_state not in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
                        # 將檢測框向上偏移一點（約框高度的20%）
                        frame_offset_y = int(adjusted_bbox['height'] * 0.2)
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
        self.detection_overlay.update_visual_rects_main_loop(faces)
        
        # 在幀上繪製檢測框
        final_frame = self.detection_overlay.draw_on_frame(cropped_frame)
        
        # 顯示畫面
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
        
        # 🚀 使用更高效的切片操作
        cropped_frame = frame[crop_y:crop_y + 1080, crop_x:crop_x + target_crop_width]
        
        # 縮放到目標尺寸1080x1920（保持正確比例，不會拉伸變形）
        portrait_frame = cv2.resize(cropped_frame, (1080, 1920), interpolation=cv2.INTER_LINEAR)
        
        return portrait_frame
        
    def adjust_detection_coordinates_fast(self, detection_result, original_shape, display_width, display_height):
        """ FPS 優化：快速版本的偵測座標調整"""
        # 安全檢查
        if not detection_result or not isinstance(detection_result, dict):
            return None
            
        # 檢查必要的鍵是否存在
        if not all(key in detection_result for key in ['x', 'y', 'width', 'height']):
            return None
        
        crop_x_offset = 622  # 預計算：(1920 - 675) // 2
        
        # 檢查偵測框是否在裁切區域內
        face_left = detection_result['x']
        face_right = detection_result['x'] + detection_result['width']
        
        # 如果人臉完全在裁切區域外，返回None
        if face_right < crop_x_offset or face_left > crop_x_offset + 675:
            return None
        
        # 調整X座標（減去裁切偏移）
        adjusted_x = max(0, detection_result['x'] - crop_x_offset)
        adjusted_width = min(detection_result['width'], 675 - adjusted_x)
        
        # Y座標不變（沒有Y方向裁切）
        adjusted_y = detection_result['y']
        adjusted_height = detection_result['height']
        
        # 步驟2：從675x1080縮放到1080x1920的座標調整（預計算比例）
        scale_y = 1.777777778  # 預計算：1920 / 1080
        final_y = adjusted_y * scale_y
        final_height = adjusted_height * scale_y
        
        # 步驟3：最終縮放到顯示尺寸（預計算比例）
        final_scale_x = display_width / 675  # 更精確的比例
        final_scale_y = display_height / 1920
        
        final_result = {
            'x': adjusted_x * final_scale_x,
            'y': final_y * final_scale_y,
            'width': adjusted_width * final_scale_x,
            'height': final_height * final_scale_y,
            'confidence': detection_result.get('confidence', 0)
        }
        
        return final_result
            
    def on_face_detected(self, detected, bbox):
        """處理人臉偵測結果"""
        pass
    
    def on_detection_state_changed(self, has_faces):
        """處理檢測狀態變化"""
        if self.startup_params['debug_mode']:
            print(f"Detection state changed: {'Face detected' if has_faces else 'No face'}")
            
    def on_state_changed(self, state):
        """處理狀態變更"""
        print(f"State changed to: {state.value}")
        
        # 更新 debug 顯示
        if self.startup_params['debug_mode']:
            self.update_debug_info()
            
    def take_screenshot(self):
        """擷取畫面"""
        self.current_screenshot_path = self.camera_manager.take_screenshot()
        
        if self.current_screenshot_path:
            if self.startup_params['no_llm_mode']:
                # 💡 新增：使用可配置的調試模式回應
                debug_response = self.config_loader.get_debug_response()
                print(f"🔧 No LLM Debug Mode - 使用 nollmdebug.csv 配置:")
                print(f"   英文字幕: {debug_response['caption'][:50]}...")
                print(f"   中文字幕: {debug_response['caption_tc'][:30]}...")
                print(f"   調試武器: {debug_response['weapons']}")
                print(f"   ⚡ 這些武器將使用 weapon_config.csv 中的真實配置數據")
                
                self.state_machine.on_llm_complete(debug_response)
            else:
                self.state_machine.llm_analysis_requested.emit(self.current_screenshot_path)
                
    def start_llm_analysis(self, image_path):
        """開始 AI 分析"""
        weapon_list = self.config_loader.get_weapon_list()
        # 從配置獲取LLM回應超時時間
        llm_timeout = self.config.get('llm_response_timeout', 10)
        print(f"🤖 開始LLM分析: 超時設定 = {llm_timeout}秒")
        self.ollama_service.analyze_image(image_path, weapon_list, llm_timeout)
        
    def on_llm_complete(self, response):
        """AI 分析完成"""
        self.state_machine.on_llm_complete(response)
        
    def display_caption(self, response):
        """顯示字幕和截圖"""
        # 防止重複顯示
        if self.caption_displayed:
            print("Warning: Caption already displayed, skipping")
            return
            
        self.caption_displayed = True
        
        # 重置完成狀態
        self.caption_completed = False
        self.tts_completed = False  # 修正：初始應為 False
        self.wait_timer_completed = False
        
        # 🔥 NEW: 儲存回應數據，等待 SSR1 完成後再顯示
        self.pending_caption_response = response
        
        # 啟動SSR1（字幕燈光）- 現在會等待配置的時間
        print("=== CAPTION STATE: Starting SSR1 (caption lighting) ===")
        print("SSR1 will wait for configured time before triggering caption display...")
        self.ssr_controller.start_caption_lighting()
        self.ssr_controller.print_debug_status()
        
        # 🔥 REMOVED: 截圖和字幕顯示邏輯已移至 on_caption_lighting_ready()
        # 等待 SSR1 完成其等待時間後才開始顯示內容
    
    def on_tts_started(self):
        """TTS 開始朗讀"""
        if self.startup_params['debug_mode']:
            print("TTS: 開始語音朗讀")
    
    def on_tts_progress(self, current_pos, total_len):
        """TTS進度更新 - 用於即時字幕同步"""
        if self.startup_params['debug_mode']:
            progress = (current_pos / total_len * 100) if total_len > 0 else 0
            print(f"TTS Progress: {current_pos}/{total_len} ({progress:.1f}%) - 同步字幕顯示")
    
    def on_tts_word_progress(self, current_chunk):
        """TTS即時文字片段進度更新 - 提供精細同步"""
        if self.startup_params['debug_mode']:
            print(f"TTS Word Progress: '{current_chunk}' - 即時字幕片段同步")
    
    def on_tts_error(self, error_msg):
        """TTS 錯誤處理"""
        print(f"TTS Error: {error_msg}")
        
    def on_tc_typing_complete(self):
        """TC字幕打字完成"""
        print("TC typing complete")
        
    def on_en_typing_complete(self):
        """EN字幕打字完成"""
        print("EN typing complete")
        
    def on_caption_typing_complete(self):
        """字幕打字完成"""
        print("All caption typing complete")
        self.caption_completed = True
        
        # 啟動等待計時器
        wait_time = self.config.get('caption_wait_after', 2.0) * 1000
        QTimer.singleShot(int(wait_time), self.on_wait_timer_complete)
        
    def on_tts_finished(self):
        """TTS朗讀完成"""
        print("TTS speaking complete")
        self.tts_completed = True
        
        # 禁用TTS同步模式
        if hasattr(self, 'caption_widget'):
            self.caption_widget.disable_tts_sync()
            
        self.check_all_completed()
        
    def on_wait_timer_complete(self):
        """等待計時器完成"""
        print("Wait timer complete")
        self.wait_timer_completed = True
        self.check_all_completed()
        
    def check_all_completed(self):
        """檢查所有事件是否完成"""
        if self.caption_completed and self.tts_completed and self.wait_timer_completed:
            print("All caption events completed - transitioning to spotlight")
            self.state_machine.on_caption_complete()
            
    def on_spotlight_requested(self):
        """聚光燈狀態請求"""
        print("=== SPOTLIGHT STATE: Starting SSR2 (spotlight) ===")
        print("Spotlight state requested")
        # 啟動SSR2（聚光燈）
        self.ssr_controller.start_spotlight()
        self.ssr_controller.print_debug_status()
        
    def on_spotlight_ready(self):
        """聚光燈準備完成"""
        print("Spotlight ready - transitioning to weapon display")
        self.state_machine.on_spotlight_ready()
                         
    def on_caption_lighting_ready(self):
        """字幕燈光準備完成 - 現在開始顯示截圖和字幕"""
        print("=== SSR1 WAIT COMPLETE: Starting caption and image display ===")
        
        # 檢查是否有等待的回應數據
        if not hasattr(self, 'pending_caption_response') or not self.pending_caption_response:
            print("Warning: No pending caption response, skipping display")
            return
            
        response = self.pending_caption_response
        
        # 顯示截圖
        if self.current_screenshot_path:
            original_frame = cv2.imread(self.current_screenshot_path)
            if original_frame is not None:
                # 💪 截圖現在已經是處理過的1080x1920格式，只需要調整到視窗尺寸
                target_width = self.window_width
                target_height = self.window_height
                
                # 檢查截圖是否已經是正確尺寸
                frame_height, frame_width = original_frame.shape[:2]
                
                if frame_width != target_width or frame_height != target_height:
                    # 需要縮放到視窗尺寸（保持比例）
                    resized_frame = cv2.resize(original_frame, (target_width, target_height), 
                                             interpolation=cv2.INTER_LINEAR)
                else:
                    # 已經是正確尺寸
                    resized_frame = original_frame
                
                qimage = CameraManager.frame_to_qimage(resized_frame)
                pixmap = QPixmap.fromImage(qimage)
                self.screenshot_label.setPixmap(pixmap)
            
            self.fade_in_widget(self.screenshot_label)
            
        # 檢查字幕
        caption_tc = response.get('caption_tc', '')
        caption_en = response.get('caption', '')
        typing_speed = self.config.get('caption_typing_speed', 50)
        print(f"📖 載入字幕設定: typing_speed = {typing_speed}ms (來自配置文件)")
        
        # 儲存武器列表
        self.current_weapons = response.get('weapons', [])
        
        # 準備TTS和字幕同步 - 修復調用順序
        if caption_tc and caption_en:
            # 雙語模式 - 先設置字幕，再啟用TTS同步
            # 🎯 首先使用句子同步方法設置字幕
            if self.caption_widget.set_bilingual_text_sentence_sync(caption_tc, caption_en, typing_speed):
                print("使用句子同步模式")
            else:
                print("句子同步失敗，回退到普通模式")
                self.caption_widget.show_bilingual_caption(caption_tc, caption_en, typing_speed)
            
            # 然後檢查是否需要啟用TTS同步
            if caption_en and hasattr(self, 'tts_service') and self.tts_service.is_available():
                # 獲取TTS預估時長
                tts_duration = self.tts_service.get_estimated_duration(caption_en)
                
                # 計算同步速率
                tts_rate_wpm = 140
                if hasattr(self.tts_service, 'worker') and self.tts_service.worker and self.tts_service.worker.config:
                    tts_rate_wpm = self.tts_service.worker.config.get_int('rate', 140)
                
                # 啟用同步模式（在字幕設置之後）
                self.caption_widget.enable_tts_sync(caption_en, tts_rate_wpm)
                
                print(f"TTS: Starting synchronized caption display (after SSR1 wait)")
                self.tts_completed = False
                self.tts_service.speak_text(caption_en)
            else:
                # 💡 No-LLM模式或TTS不可用：設置TTS為完成狀態
                print("TTS不可用或No-LLM模式，跳過TTS播放")
                self.tts_completed = True
        elif caption_tc:
            # 只有中文
            print("只有中文字幕，無需TTS")
            self.tts_completed = True
            self.caption_widget.show_caption(caption_tc, typing_speed)
        elif caption_en:
            # 只有英文
            if hasattr(self, 'tts_service') and self.tts_service.is_available():
                tts_duration = self.tts_service.get_estimated_duration(caption_en)
                tts_rate_wpm = 140
                if hasattr(self.tts_service, 'worker') and self.tts_service.worker and self.tts_service.worker.config:
                    tts_rate_wpm = self.tts_service.worker.config.get_int('rate', 140)
                
                self.caption_widget.enable_tts_sync(caption_en, tts_rate_wpm)
                
                print(f"TTS: Starting synchronized caption display (after SSR1 wait)")
                self.tts_completed = False
                self.tts_service.speak_text(caption_en)
            else:
                # 💡 No-LLM模式或TTS不可用：設置TTS為完成狀態
                print("TTS不可用或No-LLM模式，跳過TTS播放")
                self.tts_completed = True
            
            self.caption_widget.show_caption(caption_en, typing_speed)
        else:
            # 沒有字幕
            print("Warning: No caption content found, completing all caption states")
            self.caption_completed = True
            self.tts_completed = True  # 沒有TTS需要完成
            self.wait_timer_completed = True  # 沒有等待計時器需要完成
            self.check_all_completed()
            
        # 清除待處理的回應數據
        self.pending_caption_response = None
        
    def display_weapons(self, weapon_ids):
        """顯示武器"""
        print(f"display_weapons() called with weapon_ids: {weapon_ids}")
        
        if not weapon_ids:
            print("武器列表為空，直接完成")
            self.state_machine.on_weapon_display_complete()
            return
            
        print(f" 開始顯示 {len(weapon_ids)} 個武器: {weapon_ids}")
        
        # 隱藏字幕和截圖
        self.caption_widget.hide()
        self.screenshot_label.hide()
        
        # 顯示黑屏遮罩
        self.black_overlay.show()
            
        self.weapon_display_index = 0
        self.current_weapons = weapon_ids
        self.display_next_weapon()
        
    def display_next_weapon(self):
        """顯示下一個武器"""
        if self.weapon_display_index >= len(self.current_weapons):
            # 所有武器顯示完成
            self.black_overlay.hide()
            
            # 關閉所有SSR燈光
            print("=== IMG_SHOW COMPLETE: Stopping all SSR lighting ===")
            self.ssr_controller.stop_all_lighting()
            self.ssr_controller.print_debug_status()
            
            self.state_machine.on_weapon_display_complete()
            return
            
        weapon_id = self.current_weapons[self.weapon_display_index]
        weapon_info = self.weapon_config.get(weapon_id)
        
        print(f"Displaying weapon - ID: {weapon_id}, Index: {self.weapon_display_index}")
        
        if weapon_info:
            # 💡 新增：詳細的調試信息顯示weapon_config.csv數據
            print(f"🔧 Weapon Config Data from weapon_config.csv:")
            print(f"   武器: {weapon_info['name']} (ID: {weapon_id})")
            print(f"   Arduino Pin: {weapon_info['pin']}")
            print(f"   Arduino Timing: wait_before={weapon_info['wait_before']}ms, high_time={weapon_info['high_time']}ms, wait_after={weapon_info['wait_after']}ms")
            print(f"   Image: {weapon_info['image_path']}")
            print(f"   Image Timing: fade_in={weapon_info['image_fade_in']}s, display={weapon_info['image_display']}s, fade_out={weapon_info['image_fade_out']}s")
            
            # 顯示武器圖片
            self.show_weapon_image(weapon_info)
            
            # 控制 Arduino
            if self.arduino_controller and weapon_info['pin']:
                print(f"🔌 Arduino Control: Pin {weapon_info['pin']} -> HIGH for {weapon_info['high_time']}ms")
                self.arduino_controller.control_pin(
                    weapon_info['pin'],
                    weapon_info['wait_before'],
                    weapon_info['high_time'],
                    weapon_info['wait_after']
                )
            elif weapon_info['pin']:
                print(f"Arduino not connected, but would control Pin {weapon_info['pin']}")
            else:
                print(f"No Arduino pin configured for weapon {weapon_id}")
        else:
            print(f"❌Warning: Weapon ID '{weapon_id}' not found in weapon_config.csv")
                
        self.weapon_display_index += 1
        
        # 計算下一個武器的顯示時間
        if weapon_info:
            fade_in = weapon_info.get('image_fade_in', 1.0)
            display = weapon_info.get('image_display', 3.0)
            fade_out = weapon_info.get('image_fade_out', 1.0)
            switch_delay = self.config.get('weapon_switch_delay', 0.5)
            
            total_time = (fade_in + display + fade_out + switch_delay) * 1000
        else:
            total_time = 2000
            
        QTimer.singleShot(int(total_time), self.display_next_weapon)
        
    def show_weapon_image(self, weapon_info):
        """顯示武器圖片"""
        image_path = os.path.join("weapons_img", weapon_info['image_path'])
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                print(f"Error: Cannot load image {image_path}")
                return
                
            # 縮放圖片
            if pixmap.width() > self.window_width or pixmap.height() > self.window_height:
                pixmap = pixmap.scaled(self.window_width, self.window_height, 
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                                     
            self.weapon_label.setPixmap(pixmap)
            
            # Fade in
            fade_in_time = weapon_info.get('image_fade_in', 1.0) * 1000
            self.fade_in_weapon_with_black_transition(int(fade_in_time))
            
            # Schedule fade out
            display_time = weapon_info.get('image_display', 3.0) * 1000
            fade_out_time = weapon_info.get('image_fade_out', 1.0) * 1000
            
            QTimer.singleShot(int(display_time), 
                            lambda: self.fade_out_weapon_with_black_transition(int(fade_out_time)))
        else:
            print(f"Error: Weapon image file not found - {image_path}")
        
    def fade_in_weapon_with_black_transition(self, duration):
        """帶黑屏轉場的武器淡入效果"""
        self.black_overlay.raise_()
        self.black_overlay.show()
        
        self.weapon_label.show()
        
        effect = QGraphicsOpacityEffect()
        self.black_overlay.setGraphicsEffect(effect)
        
        self.fade_animation = QPropertyAnimation(effect, b"opacity")
        self.fade_animation.setDuration(duration)
        self.fade_animation.setStartValue(1)
        self.fade_animation.setEndValue(0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.finished.connect(self.black_overlay.hide)
        self.fade_animation.start()
        
    def fade_out_weapon_with_black_transition(self, duration):
        """帶黑屏轉場的武器淡出效果"""
        self.black_overlay.show()
        self.black_overlay.raise_()
        
        effect = QGraphicsOpacityEffect()
        self.black_overlay.setGraphicsEffect(effect)
        
        self.fade_out_animation = QPropertyAnimation(effect, b"opacity")
        self.fade_out_animation.setDuration(duration)
        self.fade_out_animation.setStartValue(0)
        self.fade_out_animation.setEndValue(1)
        self.fade_out_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_out_animation.finished.connect(self.weapon_label.hide)
        self.fade_out_animation.start()
                            
    def reset_system(self):
        """重置系統"""
        # 隱藏所有顯示元件
        self.detection_overlay.clear_detections()
        self.screenshot_label.hide()
        self.caption_widget.hide()
        self.weapon_label.hide()
        self.black_overlay.hide()
        
        # 刪除截圖
        if self.current_screenshot_path and os.path.exists(self.current_screenshot_path):
            try:
                os.remove(self.current_screenshot_path)
            except:
                pass
                
        self.current_screenshot_path = None
        self.current_weapons = []
        
        # 重置狀態追蹤
        self.caption_completed = False
        self.tts_completed = True
        self.wait_timer_completed = False
        self.caption_displayed = False  # 重置防重複標記
        
        # 🔥 NEW: 清理待處理的回應數據
        self.pending_caption_response = None
        
        # 確保所有SSR關閉
        print("=== RESET: Ensuring all SSR are turned OFF ===")
        self.ssr_controller.stop_all_lighting()
        
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
            
    def update_debug_info(self):
        """更新 Debug 資訊"""
        if hasattr(self, 'debug_label'):
            detection_time = self.state_machine.get_detection_time()
            arduino_status = "Connected" if self.arduino_controller and self.arduino_controller.is_connected else "Not connected"
            llm_mode = "No LLM" if self.startup_params['no_llm_mode'] else "Normal"
            mode = "Mini Mode" if self.startup_params.get('mini_mode', False) else "Full Mode"
            
            weapons_display = "None"
            if hasattr(self, 'current_weapons') and self.current_weapons:
                weapons_display = f"[{', '.join(self.current_weapons)}]"
            
            # SSR狀態
            ssr_status = "Off"
            if hasattr(self, 'ssr_controller'):
                if self.state_machine.current_state in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
                    ssr_status = "Active"
            
            # 武器狀態顯示
            weapon_status_lines = []
            for weapon_id, weapon_info in self.weapon_config.items():
                weapon_name = weapon_info['name']
                weapon_pin = weapon_info['pin']
                pin_state = "LOW"
                if self.arduino_controller and weapon_pin:
                    pin_state = self.arduino_controller.get_pin_state(weapon_pin)
                weapon_status_lines.append(f"{weapon_id}：{weapon_name}（D{weapon_pin}）:{pin_state}")
            
            # SSR狀態顯示
            ssr_status_lines = []
            if hasattr(self, 'ssr_controller') and self.ssr_controller.config:
                ssr1_pin = self.ssr_controller.config.ssr1_pin
                ssr2_pin = self.ssr_controller.config.ssr2_pin
                ssr1_state = "LOW"
                ssr2_state = "LOW"
                if self.arduino_controller:
                    ssr1_state = self.arduino_controller.get_pin_state(ssr1_pin)
                    ssr2_state = self.arduino_controller.get_pin_state(ssr2_pin)
                ssr_status_lines.append(f"SSR1：AllLightInverted (D{ssr1_pin}):{ssr1_state}")
                ssr_status_lines.append(f"SSR2：SpotLight (D{ssr2_pin}):{ssr2_state}")
            
            debug_text = f"""State: {self.state_machine.current_state.value}
FPS: {self.current_fps}
Detection Time: {detection_time:.1f}s
Arduino: {arduino_status}
SSR: {ssr_status}
LLM Mode: {llm_mode}
Display: {mode}
Weapons: {weapons_display}
Window: {self.window_width}x{self.window_height}
""" + "\n".join(weapon_status_lines) + "\n" + "\n".join(ssr_status_lines)
            
            self.debug_label.setText(debug_text)
            
    def closeEvent(self, event):
        """關閉事件"""
        self.state_machine.stop()
        self.camera_manager.stop()
        self.face_detector.release()
        
        if self.arduino_controller:
            self.arduino_controller.disconnect()
        
        # 關閉SSR控制器
        if hasattr(self, 'ssr_controller'):
            self.ssr_controller.cleanup()
        
        # 關閉TTS服務
        if hasattr(self, 'tts_service'):
            print("Shutting down TTS service...")
            self.tts_service.shutdown()
            
        event.accept()