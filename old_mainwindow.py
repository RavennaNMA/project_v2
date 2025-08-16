# Location: project_v2/ui/main_window.py
# Usage: 主視窗，整合所有功能模組

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QPixmap, QFont, QFontDatabase
import os
import cv2
import numpy as np
import time  # 添加缺少的time導入

from core import StateMachine, SystemState, CameraManager, FaceDetector, ESP32Controller
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
        # 創建 AnimConfigLoader 用於 cal windows 配置
        from utils import AnimConfigLoader
        self.anim_config_loader = AnimConfigLoader()
        
        # 核心元件 - 傳遞anim_config_loader以支持cal windows配置
        self.state_machine = StateMachine(self.config, self.anim_config_loader)
        self.camera_manager = CameraManager()
        self.face_detector = FaceDetector(self.config)
        
        # ESP32 控制器（替代Arduino）
        self.esp32_controller = None
        if self.startup_params['arduino_port']:  # 兼容性保留
            self.esp32_controller = ESP32Controller()
            self.esp32_controller.connect()
            
        # SSR控制器
        self.ssr_controller = SSRController(self.esp32_controller)
        
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
        
        # 兼容性別名
        self.arduino_controller = self.esp32_controller
        
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
            self.debug_label.resize(int(450 * self.scale_factor), int(800 * self.scale_factor))
            debug_font_size = int(self.startup_params.get('debug_text_size', 16) * self.scale_factor)
            self.debug_label.setStyleSheet("""
                color: white;
                background-color: rgba(0, 0, 0, 192);
                padding: %dpx;
                font-family: monospace;
                font-size: %dpx;
                font-weight: bold;
            """ % (int(8 * self.scale_factor), debug_font_size))
            
            # 設置調試標籤為始終在最上層

            self.debug_label.raise_()  # 最頂層
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
            # 連接 TTS 生命週期信號
            self.tts_service.tts_started.connect(self.on_tts_started)
            self.tts_service.tts_finished.connect(self.on_tts_finished)
            self.tts_service.tts_error.connect(self.on_tts_error)
            
            # 連接進度信號 - 這是即時打字效果的關鍵
            self.tts_service.tts_progress.connect(self.on_tts_progress)
            self.tts_service.tts_progress.connect(self.caption_widget.update_tts_progress)
            
            # 連接文字片段信號 - 提供更精細的同步
            self.tts_service.tts_word_progress.connect(self.on_tts_word_progress)
            
        # SSR控制器信號
        self.ssr_controller.spotlight_ready.connect(self.on_spotlight_ready)
        self.ssr_controller.caption_lighting_ready.connect(self.on_caption_lighting_ready)  # 新增SSR1完成信號
        
    def start_system(self):
        """啟動系統"""
        # 設定 No LLM 模式
        self.state_machine.set_no_llm_mode(self.startup_params['no_llm_mode'])
        
        # 啟動相機 - 修復：添加camera_index參數
        camera_index = self.startup_params.get('camera_index', 0)
        self.camera_manager.start(camera_index)
        
        # 第一個畫面到達時隱藏載入提示
        self.first_frame_received = False
        
        # 啟動狀態機
        self.state_machine.start()
        
    def on_state_changed(self, state):
        """狀態變更處理"""
        print(f"State changed to: {state.value}")
        
        # 根據狀態控制檢測動畫顯示
        if state == SystemState.DETECTING:
            # 顯示檢測動畫 - 不需要特別調用，在process_frame中會自動更新
            # 隱藏其他覆蓋層
            self.screenshot_label.hide()
            self.caption_widget.hide()
            self.weapon_label.hide()
            self.black_overlay.hide()
        elif state in [SystemState.CAPTION, SystemState.SPOTLIGHT, SystemState.IMG_SHOW]:
            # 在這些狀態中清除檢測動畫
            self.detection_overlay.clear_detections()
            
            if hasattr(self, 'debug_label') and self.debug_label.isVisible():
                self.debug_label.raise_()
        elif state == SystemState.RESET:
            # 重置狀態，清除檢測動畫
            self.detection_overlay.clear_detections()
            
    def on_detection_state_changed(self, is_detecting):
        """檢測狀態變更"""
        # 可以在此處理檢測狀態的UI反饋
        pass
        
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
        
    def adjust_detection_coordinates_fast(self, detection_result, original_shape, display_width, display_height):
        """ FPS 優化：快速版本的偵測座標調整（用於原始完整畫面）"""
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
        
    def on_face_detected(self, detected):
        """人臉偵測回調 - 修復：使用正確的StateMachine API"""
        # ESP32版本使用 update_face_detection 而不是 on_face_detected
        if hasattr(self.state_machine, 'update_face_detection'):
            self.state_machine.update_face_detection(detected)
        
    def take_screenshot(self):
        """擷取螢幕截圖 - 修復：使用CameraManager的take_screenshot方法"""
        # 使用CameraManager的截圖功能，而不是從UI控件截取
        screenshot_path = self.camera_manager.take_screenshot()
        
        if screenshot_path:
            self.current_screenshot_path = screenshot_path
            print(f"Screenshot saved: {screenshot_path}")
            
            # ESP32版本：screenshot_requested信號會自動觸發狀態轉換
            # 不需要手動調用 on_screenshot_complete
            if self.startup_params['no_llm_mode']:
                # No LLM模式：直接使用config_loader的調試回應
                if hasattr(self, 'config_loader'):
                    debug_response = self.config_loader.get_debug_response()
                    
                    self.state_machine.on_llm_complete(debug_response)
            else:
                # 正常模式：啟動LLM分析
                self.start_llm_analysis(screenshot_path)
        
    def start_llm_analysis(self, image_path):
        """開始 AI 分析"""
        weapon_list = self.config_loader.get_weapon_list()
        # 從配置獲取LLM回應超時時間
        llm_timeout = self.config.get('llm_response_timeout', 10)
        print(f" 開始LLM分析: 超時設定 = {llm_timeout}秒")
        print(f" 正常模式: 啟動Ollama分析")
        self.ollama_service.analyze_image(image_path, weapon_list, llm_timeout)
        
    def on_llm_complete(self, response):
        """AI 分析完成"""
        print(f" LLM分析完成，回應類型: {type(response)}")
        print(f" 回應內容: {response}")
        print(f" 當前狀態機狀態: {self.state_machine.current_state.value}")
        # 只通知狀態機，不直接顯示字幕
        # 字幕顯示將由狀態機在適當的時機觸發
        self.state_machine.on_llm_complete(response)
        
    def display_caption(self, response):
        """顯示字幕和截圖"""
        print(f" display_caption 被調用:")
        print(f"   回應類型: {type(response)}")
        print(f"   回應內容: {response}")
        print(f"   當前模式: {'No-LLM' if self.startup_params['no_llm_mode'] else 'Normal'}")
        
        # 設置字幕顯示標誌，防止重複顯示
        self.caption_displayed = True
        print(" 設置字幕顯示標誌")
        
        # 重置完成狀態
        self.caption_completed = False
        self.tts_completed = False  # 修正：初始應為 False
        self.wait_timer_completed = False
        self.pending_caption_response = response
        print("🔄 重置完成狀態")
        
        # 啟動SSR1（字幕燈光）- 現在會等待配置的時間
        print("=== CAPTION STATE: Starting SSR1 (caption lighting) ===")
        print("SSR1 will wait for configured time before triggering caption display...")
        self.ssr_controller.start_caption_lighting()
        self.ssr_controller.print_debug_status()
        
        esp32_connected = self.esp32_controller and self.esp32_controller.is_connected
        print(f"🔌 ESP32連接狀態檢查:")
        print(f"   ESP32控制器存在: {self.esp32_controller is not None}")
        print(f"   ESP32已連接: {esp32_connected}")
        print(f"   當前模式: {'No-LLM' if self.startup_params.get('no_llm_mode', False) else 'Normal'}")
        
        if not esp32_connected:
            print("⚠️ ESP32 未連接，直接顯示字幕")
            # 使用短延遲模擬 SSR 等待時間
            QTimer.singleShot(500, self.on_caption_lighting_ready)
        elif self.startup_params.get('no_llm_mode', False):
            print("🔧 No-LLM 調試模式，使用短延遲顯示字幕")
            QTimer.singleShot(500, self.on_caption_lighting_ready)
        else:
            print("🔧 正常模式，等待SSR1信號")
            print("   SSR1信號將在SSR控制器完成後發送")
            if not esp32_connected:
                print("⚠️ 正常模式下ESP32未連接，使用短延遲顯示字幕")
                QTimer.singleShot(500, self.on_caption_lighting_ready)
        
    def on_caption_lighting_ready(self):
        """SSR1燈光準備完成，現在可以顯示字幕"""
        print("=== SSR1 READY: Now displaying caption and screenshot ===")
        
        if not hasattr(self, 'pending_caption_response') or not self.pending_caption_response:
            print("⚠️ 沒有待處理的字幕回應")
            return
            
        response = self.pending_caption_response
        
        # 清除偵測框
        self.detection_overlay.clear_detections()
        
        # 顯示截圖（淡入效果）
        if self.current_screenshot_path and os.path.exists(self.current_screenshot_path):
            pixmap = QPixmap(self.current_screenshot_path)
            self.screenshot_label.setPixmap(pixmap)
            self.fade_in_widget(self.screenshot_label)
            
        # 解析回應
        if isinstance(response, dict):
            caption_tc = response.get('caption_tc', '')
            caption_en = response.get('caption_en', '') or response.get('caption', '')  # 兼容兩種格式
            weapons = response.get('weapons', [])
        else:
            # No-LLM 模式
            caption_tc = response
            caption_en = response
            weapons = []
            
        # 儲存武器列表
        self.current_weapons = weapons
        
        # 從配置獲取打字速度
        typing_speed = self.config.get('caption_typing_speed', 50)
        
        print(f" 準備顯示字幕:")
        print(f"   中文: {caption_tc[:50]}..." if caption_tc else "   中文: (無)")
        print(f"   英文: {caption_en[:50]}..." if caption_en else "   英文: (無)")
        print(f"   打字速度: {typing_speed}ms/字")
        
        # 顯示字幕
        if caption_tc or caption_en:
            # TTS 相關處理
            tts_enabled = self.startup_params.get('tts_enabled', False)
            no_llm_mode = self.startup_params.get('no_llm_mode', False)
            tts_skip_reason = ""
            
            if not tts_enabled:
                tts_skip_reason = "TTS已禁用"
            elif no_llm_mode:
                tts_skip_reason = "No-LLM模式"
            elif not caption_en:
                tts_skip_reason = "無英文字幕"
                
            # 配置字幕打字效果
            if tts_enabled and not no_llm_mode and caption_en and hasattr(self, 'tts_service'):
                # TTS模式：字幕與語音同步
                print(" 啟用TTS同步字幕顯示")
                self.caption_widget.enable_tts_sync(caption_en)
                
                # 估算TTS時長並設定超時保護
                words = caption_en.split()
                effective_wpm = 140  # 有效WPM（考慮標點和停頓）
                estimated_duration = len(words) / effective_wpm * 60 if effective_wpm > 0 else 10
                timeout_duration = max(estimated_duration * 1.5, 8.0)  # 至少8秒，最多1.5倍預估時間
                print(f" 設定TTS超時保護: {timeout_duration:.1f}秒")
                
                # 設定備用完成計時器
                QTimer.singleShot(int(timeout_duration * 1000), self.on_tts_timeout_fallback)
                
                # 啟動TTS
                self.tts_service.speak_text(caption_en)
            else:
                print(f" 跳過TTS播放: {tts_skip_reason}")
                self.tts_completed = True
            
            # 🔧 確保字幕元件可見並在最上層
            self.caption_widget.show()
            self.caption_widget.raise_()  # 確保字幕元件在最上層

            self.caption_widget.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
            self.caption_widget.raise_()

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
            self.check_all_completed()
            
        # 清除待處理的回應數據
        self.pending_caption_response = None
    
    def on_tts_started(self):
        """TTS 開始朗讀"""
        if self.startup_params['debug_mode']:
            print("TTS: 開始語音朗讀")
    
    def on_tts_progress(self, current_pos, total_len):
        """TTS進度更新 - 用於即時字幕同步"""
        pass
    
    def on_tts_word_progress(self, current_chunk):
        """TTS即時文字片段進度更新 - 提供精細同步"""
        pass
    
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
        print("TTS playback finished")
        self.tts_completed = True
        self.check_all_completed()
        
    def on_tts_timeout_fallback(self):
        """TTS超時備用完成機制"""
        if not self.tts_completed:
            print("⚠️ TTS超時，強制完成字幕狀態")
            self.tts_completed = True
            
            # 如果TTS同步還在進行，禁用它
            if hasattr(self.caption_widget, 'disable_tts_sync'):
                self.caption_widget.disable_tts_sync()
                
            self.check_all_completed()
        
    def on_wait_timer_complete(self):
        """等待計時器完成"""
        print("Caption wait timer complete")
        self.wait_timer_completed = True
        self.check_all_completed()
        
    def check_all_completed(self):
        """檢查是否所有字幕相關任務都完成"""
        if (self.caption_completed and 
            self.tts_completed and 
            self.wait_timer_completed):
            
            self.state_machine.on_caption_complete()
    
    def on_cal_window_fade_requested(self):
        """Cal Window 消失請求處理"""
        print("🎭 Cal Window 消失請求")
        if hasattr(self, 'detection_overlay') and hasattr(self.detection_overlay, 'window_effect'):
            self.detection_overlay.window_effect.start_fade_out()
            
    def on_detect_frame_fade_requested(self):
        """Detect Frame 消失請求處理"""
        print("🎭 Detect Frame 消失請求")
        if hasattr(self, 'detection_overlay'):
            self.detection_overlay.start_fade_out()
            
    def on_spotlight_requested(self):
        """聚光燈請求"""
        self.ssr_controller.start_spotlight()
        
    def on_spotlight_ready(self):
        """聚光燈準備完成"""
        print("Spotlight ready")
        # 這裡可以添加聚光燈效果的視覺回饋
        # 直接進入下一個狀態 - 修復：使用正確的方法名
        if hasattr(self.state_machine, 'on_spotlight_ready'):
            self.state_machine.on_spotlight_ready()
        else:
            # 備用：直接進入武器顯示狀態
            if hasattr(self, 'current_weapons'):
                self.display_weapons(self.current_weapons)
        
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
        
        #  確保調試標籤始終在最上層
        if hasattr(self, 'debug_label') and self.debug_label.isVisible():
            self.debug_label.raise_()
            
        self.weapon_display_index = 0
        self.current_weapons = weapon_ids
        self.display_next_weapon()
        
    def display_next_weapon(self):
        """顯示下一個武器"""
        if self.weapon_display_index >= len(self.current_weapons):
            # 所有武器顯示完成
            self.black_overlay.hide()
            
            # 關閉所有SSR燈光
            self.ssr_controller.stop_all_lighting()
            
            self.state_machine.on_weapon_display_complete()
            return
            
        weapon_id = self.current_weapons[self.weapon_display_index]
        weapon_info = self.weapon_config.get(weapon_id)
        
        print(f"Displaying weapon - ID: {weapon_id}, Index: {self.weapon_display_index}")
        
        if weapon_info:

            
            # 顯示武器圖片
            self.show_weapon_image(weapon_info)
            
            # 控制 ESP32
            if self.esp32_controller and weapon_info['pin']:
                print(f"🔌 ESP32 Control: Pin {weapon_info['pin']} -> HIGH for {weapon_info['high_time']}ms")
                self.esp32_controller.control_pin(
                    weapon_info['pin'],
                    weapon_info['wait_before'],
                    weapon_info['high_time'],
                    weapon_info['wait_after']
                )
            elif weapon_info['pin']:
                print(f"ESP32 not connected, but would control Pin {weapon_info['pin']}")
            else:
                print(f"No ESP32 pin configured for weapon {weapon_id}")
        else:
            pass
                
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
        
        print(f"顯示武器圖片: {image_path}")
        
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            
            if pixmap.isNull():
                print(f"Error: Cannot load image {image_path}")
                return
                
            print(f"成功載入圖片: {pixmap.width()}x{pixmap.height()}")
                
            # 縮放圖片
            if pixmap.width() > self.window_width or pixmap.height() > self.window_height:
                pixmap = pixmap.scaled(self.window_width, self.window_height, 
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                print(f"🔧 圖片已縮放至: {pixmap.width()}x{pixmap.height()}")
                                     
            self.weapon_label.setPixmap(pixmap)
            
            # 🔧 關鍵修復：確保武器圖片顯示在黑屏遮罩之上
            self.weapon_label.raise_()  # 將武器圖片提升到最頂層
            self.weapon_label.show()
            
            # 🔥 確保調試標籤始終在最上層
            if hasattr(self, 'debug_label') and self.debug_label.isVisible():
                self.debug_label.raise_()
            
            # 淡入效果
            fade_in_duration = int(weapon_info.get('image_fade_in', 1.0) * 1000)
            print(f"🎬 開始淡入動畫: {fade_in_duration}ms")
            self.fade_in_widget(self.weapon_label, fade_in_duration)
            
            # 設定淡出計時器
            display_duration = weapon_info.get('image_display', 3.0)
            fade_out_duration = int(weapon_info.get('image_fade_out', 1.0) * 1000)
            total_display_time = int((display_duration + weapon_info.get('image_fade_in', 1.0)) * 1000)
            
            print(f"圖片顯示時間: 淡入{fade_in_duration}ms + 顯示{display_duration*1000}ms + 淡出{fade_out_duration}ms = 總計{total_display_time}ms")
            
            QTimer.singleShot(total_display_time, 
                            lambda: self.fade_out_widget(self.weapon_label, fade_out_duration))
        else:

            print(f"當前工作目錄: {os.getcwd()}")
            
            # 列出weapons_img目錄的內容以幫助調試
            weapons_dir = "weapons_img"
            if os.path.exists(weapons_dir):
                files = os.listdir(weapons_dir)
                print(f"weapons_img目錄內容: {files}")
            else:
                print(f"weapons_img目錄不存在")
            
    def reset_system(self):
        """重置系統"""
        print("System reset")
        
        # 隱藏所有覆蓋層
        self.detection_overlay.clear_detections()
        self.screenshot_label.hide()
        self.caption_widget.hide()
        self.weapon_label.hide()
        self.black_overlay.hide()
        
        # 重置 cal windows fade 狀態
        if hasattr(self.detection_overlay, 'window_effect'):
            self.detection_overlay.window_effect.reset_fade_state()
            print("🔄 重置 Cal Windows fade 狀態")
        
        # 清除狀態
        self.current_screenshot_path = None
        self.current_weapons = []
        
        # 重置狀態追蹤
        self.caption_completed = False
        self.tts_completed = True
        self.wait_timer_completed = False
        self.caption_displayed = False  # 重置防重複標記
    
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
            esp32_status = "Connected" if self.esp32_controller and self.esp32_controller.is_connected else "Not connected"
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
            
            # ESP32連接狀態
            esp32_connections = self.esp32_controller.get_esp32_connections() if self.esp32_controller else {}
            esp32_status_lines = []
            for esp_name, is_connected in esp32_connections.items():
                status = "✓" if is_connected else "✗"
                esp32_status_lines.append(f"ESP32 {esp_name}: {status}")
            
            # ESP32腳位狀態顯示
            esp32_pin_lines = []
            if self.esp32_controller:
                all_pin_states = self.esp32_controller.get_esp32_pin_states()
                
                # ESP32 A (武器控制)
                if 'A' in all_pin_states:
                    pins_a = []
                    for weapon_id, weapon_info in self.weapon_config.items():
                        if weapon_info['pin']:
                            # 從映射找到對應的ESP32腳位
                            arduino_pin = weapon_info['pin']
                            if arduino_pin in range(2, 12):  # 武器腳位範圍
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
                    
                    # SSR1 腳位狀態
                    ssr1_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23]
                    ssr1_states = []
                    for pin in ssr1_pins:
                        state = all_pin_states['B'].get(pin, 'LOW')
                        ssr1_states.append(f"G{pin}:{state}")
                    
                    # SSR1腳位狀態分組顯示
                    for i in range(0, len(ssr1_states), 4):
                        esp32_pin_lines.append(f"  SSR1: {' '.join(ssr1_states[i:i+4])}")
                    
                    # SSR2 腳位狀態
                    ssr2_state = all_pin_states['B'].get(25, 'LOW')
                    esp32_pin_lines.append(f"  SSR2(G25):{ssr2_state}")




                # ESP32 C (安裝控制)
                if 'C' in all_pin_states:
                    install_state = all_pin_states['C'].get(4, 'LOW')
                    esp32_pin_lines.append("ESP32 C :")
                    esp32_pin_lines.append(f"  Installation (G4):{install_state}")
            
            debug_text = f"""State: {self.state_machine.current_state.value}
FPS: {self.current_fps}
Detection Time: {detection_time:.1f}s
Controller: ESP32
SSR: {ssr_status}
LLM Mode: {llm_mode}
Display: {mode}
Weapons: {weapons_display}
Window: {self.window_width}x{self.window_height}

=== ESP32 連接狀態 ===
""" + "\n".join(esp32_status_lines) + "\n\n=== ESP32 腳位狀態 ===\n" + "\n".join(esp32_pin_lines)
            
            self.debug_label.setText(debug_text)

            self.debug_label.raise_()
            
    def closeEvent(self, event):
        """關閉事件"""
        self.state_machine.stop()
        self.camera_manager.stop()
        self.face_detector.release()
        
        if self.esp32_controller:
            self.esp32_controller.disconnect()
        
        # 關閉SSR控制器
        if hasattr(self, 'ssr_controller'):
            self.ssr_controller.cleanup()
        
        # 關閉TTS服務
        if hasattr(self, 'tts_service'):
            print("Shutting down TTS service...")
            self.tts_service.shutdown()
            
        event.accept()

