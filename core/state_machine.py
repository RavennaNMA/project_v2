# Location: project_v2/core/state_machine.py
# Usage: 狀態機管理系統，控制整體流程 - 改良版本

from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import time
import gc


class SystemState(Enum):
    """系統狀態定義"""
    DETECTING = "DETECTING"
    SCREENSHOT_TRIGGER = "SCREENSHOT_TRIGGER" 
    LLM_LOADING = "LLM_LOADING"
    CAL_WINDOW_FADE = "CAL_WINDOW_FADE"  # Cal Window 消失狀態
    DETECT_FRAME_FADE = "DETECT_FRAME_FADE"  # Detect Frame 消失狀態
    CAPTION = "CAPTION"
    SPOTLIGHT = "SPOTLIGHT"  # 聚光燈狀態
    IMG_SHOW = "IMG_SHOW"
    RESET = "RESET"


class StateMachine(QObject):
    """狀態機控制器 - 改良版本"""
    
    # 狀態變更信號
    state_changed = pyqtSignal(SystemState)
    
    # 各狀態事件信號
    screenshot_requested = pyqtSignal()
    llm_analysis_requested = pyqtSignal(str)  # 圖片路徑
    cal_window_fade_requested = pyqtSignal()  # Cal Window 消失信號
    detect_frame_fade_requested = pyqtSignal()  # Detect Frame 消失信號
    caption_display_requested = pyqtSignal(dict)  # AI 回應
    spotlight_requested = pyqtSignal()  # 聚光燈信號
    weapon_display_requested = pyqtSignal(list)  # 武器列表
    reset_requested = pyqtSignal()
    
    # 狀態相關燈光控制信號
    state_lighting_requested = pyqtSignal(str)  # 狀態名稱
    
    def __init__(self, config, config_loader=None):
        super().__init__()
        self.config = config
        self.config_loader = config_loader
        self.current_state = SystemState.DETECTING
        self.detection_start_time = None
        self.face_detected = False
        self.no_llm_mode = False
        self.pending_weapons = []  # 暫存武器列表
        self.pending_llm_response = None  # 暫存 LLM 回應
        self.robot_mode = False  # 機器人模式標記
        
        # 計時器
        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self._handle_state_timeout)
        
        # 記憶體管理計時器
        self.gc_timer = QTimer()
        self.gc_timer.timeout.connect(self._perform_gc)
        self.gc_timer.start(60000)  # 每60秒執行一次垃圾回收
        
    def set_no_llm_mode(self, enabled):
        """設定 No LLM 模式"""
        self.no_llm_mode = enabled
        
    def set_robot_mode(self, enabled):
        """設定機器人模式"""
        self.robot_mode = enabled
        print(f"State Machine: Robot mode = {enabled}")
        
    def start(self):
        """啟動狀態機"""
        self.transition_to(SystemState.DETECTING)
        
    def stop(self):
        """停止狀態機"""
        self.state_timer.stop()
        self.gc_timer.stop()
        gc.collect()
        
    def transition_to(self, new_state):
        """狀態轉換"""
        print(f"State transition: {self.current_state.value} -> {new_state.value}")
        self.current_state = new_state
        self.state_timer.stop()
        
        # 發送狀態變更信號
        self.state_changed.emit(new_state)
        self.state_lighting_requested.emit(new_state.value)
        
        # 根據狀態執行對應動作
        if new_state == SystemState.DETECTING:
            self._enter_detecting()
        elif new_state == SystemState.SCREENSHOT_TRIGGER:
            self._enter_screenshot_trigger()
        elif new_state == SystemState.LLM_LOADING:
            self._enter_llm_loading()
        elif new_state == SystemState.CAL_WINDOW_FADE:
            self._enter_cal_window_fade()
        elif new_state == SystemState.DETECT_FRAME_FADE:
            self._enter_detect_frame_fade()
        elif new_state == SystemState.CAPTION:
            self._enter_caption()
        elif new_state == SystemState.SPOTLIGHT:
            self._enter_spotlight()
        elif new_state == SystemState.IMG_SHOW:
            self._enter_img_show()
        elif new_state == SystemState.RESET:
            self._enter_reset()
            
    def _enter_detecting(self):
        """進入偵測狀態"""
        self.detection_start_time = None
        self.face_detected = False
        self.robot_mode = False  # 重置機器人模式
        # 釋放記憶體
        gc.collect()
        
    def _enter_screenshot_trigger(self):
        """進入截圖觸發狀態"""
        self.screenshot_requested.emit()
        self.transition_to(SystemState.LLM_LOADING)
        
    def _enter_llm_loading(self):
        """進入 LLM 載入狀態"""
        # 在機器人模式下，跳過視覺效果，直接進入字幕狀態
        if self.robot_mode:
            print("Robot mode: Skipping visual effects in LLM_LOADING")
            # 不顯示 cal window 和 detect frame
            # 直接等待 LLM 完成
        else:
            # Human mode: 保持原有的視覺效果，延長動畫顯示時間
            print("Human mode: Keeping visual effects active during LLM_LOADING")
            # 設置一個較長的 LLM 載入顯示時間，讓動畫持續運作
            # 這個時間會在 LLM 實際完成時被覆蓋
            
    def _enter_cal_window_fade(self):
        """進入 Cal Window 消失狀態"""
        # 機器人模式下跳過
        if self.robot_mode:
            self.transition_to(SystemState.DETECT_FRAME_FADE)
        else:
            self.cal_window_fade_requested.emit()
            self.state_timer.start(int(self.config.get('cal_window_fade_time', 1) * 1000))
        
    def _enter_detect_frame_fade(self):
        """進入 Detect Frame 消失狀態"""
        # 機器人模式下跳過
        if self.robot_mode:
            self.transition_to(SystemState.CAPTION)
        else:
            self.detect_frame_fade_requested.emit()
            self.state_timer.start(int(self.config.get('detect_frame_fade_time', 1) * 1000))
        
    def _enter_caption(self):
        """進入字幕顯示狀態"""
        if self.pending_llm_response:
            self.caption_display_requested.emit(self.pending_llm_response)
            self.pending_llm_response = None
            
    def _enter_spotlight(self):
        """進入聚光燈狀態"""
        self.spotlight_requested.emit()
        
    def _enter_img_show(self):
        """進入武器顯示狀態"""
        self.weapon_display_requested.emit(self.pending_weapons)
        self.pending_weapons = []
        
    def _enter_reset(self):
        """進入重置狀態"""
        self.reset_requested.emit()
        # 重置後釋放記憶體
        gc.collect()
        # 等待冷卻時間
        cooldown = int(self.config.get('cooldown_time', 5) * 1000)
        self.state_timer.start(cooldown)
        
    def _handle_state_timeout(self):
        """處理狀態超時"""
        if self.current_state == SystemState.LLM_LOADING:
            # 🔥 修改：LLM_LOADING 狀態超時時，所有模式都直接進入字幕狀態（與 on_llm_complete 邏輯一致）
            print("LLM_LOADING timeout: 直接進入CAPTION狀態")
            self.transition_to(SystemState.CAPTION)
        elif self.current_state == SystemState.CAL_WINDOW_FADE:
            self.transition_to(SystemState.DETECT_FRAME_FADE)
        elif self.current_state == SystemState.DETECT_FRAME_FADE:
            self.transition_to(SystemState.CAPTION)
        elif self.current_state == SystemState.RESET:
            self.transition_to(SystemState.DETECTING)
            
    def _perform_gc(self):
        """定期執行垃圾回收"""
        collected = gc.collect()
        if collected > 0:
            print(f"GC: Collected {collected} objects")
            
    def update_face_detection(self, detected):
        """更新人臉偵測狀態"""
        if self.current_state != SystemState.DETECTING:
            return
            
        if detected:
            if not self.face_detected:
                self.face_detected = True
                self.detection_start_time = time.time()
            else:
                # 檢查是否達到偵測時間
                duration = time.time() - self.detection_start_time
                required_duration = self.config.get('detect_duration', 3)
                
                if duration >= required_duration:
                    self.transition_to(SystemState.SCREENSHOT_TRIGGER)
        else:
            self.face_detected = False
            self.detection_start_time = None
            
    def get_detection_time(self):
        """取得偵測時間"""
        if self.detection_start_time and self.face_detected:
            return time.time() - self.detection_start_time
        return 0
        
    def on_llm_complete(self, response):
        """LLM 分析完成"""
        # 暫存回應
        self.pending_llm_response = response
        
        # 解析武器列表
        if isinstance(response, dict):
            self.pending_weapons = response.get('weapons', [])
        else:
            self.pending_weapons = []
            
        # 🔥 修改：所有模式都直接進入字幕狀態，實現平滑過渡
        print(f"LLM分析完成，直接進入CAPTION狀態 (模式: {'機器人' if self.robot_mode else '人類'})")
        self.transition_to(SystemState.CAPTION)
                
    def on_caption_complete(self):
        """字幕顯示完成"""
        if self.current_state == SystemState.CAPTION:
            self.transition_to(SystemState.SPOTLIGHT)
            
    def on_spotlight_complete(self):
        """聚光燈完成"""
        if self.current_state == SystemState.SPOTLIGHT:
            self.transition_to(SystemState.IMG_SHOW)
            
    def on_weapon_display_complete(self):
        """武器顯示完成"""
        if self.current_state == SystemState.IMG_SHOW:
            self.transition_to(SystemState.RESET)

