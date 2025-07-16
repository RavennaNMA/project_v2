# Location: project_v2/core/state_machine.py
# Usage: 狀態機管理系統，控制整體流程

from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import time


class SystemState(Enum):
    """系統狀態定義"""
    DETECTING = "DETECTING"
    SCREENSHOT_TRIGGER = "SCREENSHOT_TRIGGER" 
    LLM_LOADING = "LLM_LOADING"
    CAPTION = "CAPTION"
    SPOTLIGHT = "SPOTLIGHT"  # 新增聚光燈狀態
    IMG_SHOW = "IMG_SHOW"
    RESET = "RESET"


class StateMachine(QObject):
    """狀態機控制器"""
    
    # 狀態變更信號
    state_changed = pyqtSignal(SystemState)
    
    # 各狀態事件信號
    screenshot_requested = pyqtSignal()
    llm_analysis_requested = pyqtSignal(str)  # 圖片路徑
    caption_display_requested = pyqtSignal(dict)  # AI 回應
    spotlight_requested = pyqtSignal()  # 新增聚光燈信號
    weapon_display_requested = pyqtSignal(list)  # 武器列表
    reset_requested = pyqtSignal()
    
    def __init__(self, config, config_loader=None):
        super().__init__()
        self.config = config
        self.config_loader = config_loader  # 💡 新增：配置載入器引用
        self.current_state = SystemState.DETECTING
        self.detection_start_time = None
        self.face_detected = False
        self.no_llm_mode = False
        self.pending_weapons = []  # 暫存武器列表
        
        # 計時器
        self.state_timer = QTimer()
        self.state_timer.timeout.connect(self._handle_state_timeout)
        
    def set_no_llm_mode(self, enabled):
        """設定 No LLM 模式"""
        self.no_llm_mode = enabled
        
    def start(self):
        """啟動狀態機"""
        self.transition_to(SystemState.DETECTING)
        
    def stop(self):
        """停止狀態機"""
        self.state_timer.stop()
        
    def transition_to(self, new_state):
        """狀態轉換"""
        print(f"State transition: {self.current_state.value} -> {new_state.value}")
        self.current_state = new_state
        self.state_timer.stop()
        
        # 發送狀態變更信號
        self.state_changed.emit(new_state)
        
        # 處理新狀態
        self._enter_state(new_state)
        
    def _enter_state(self, state):
        """進入新狀態的處理"""
        if state == SystemState.DETECTING:
            # 重置偵測
            self.detection_start_time = None
            self.face_detected = False
            self.pending_weapons = []
            
        elif state == SystemState.SCREENSHOT_TRIGGER:
            # 觸發截圖
            self.screenshot_requested.emit()
            # 直接轉到下一狀態
            if self.no_llm_mode:
                # 💡 No LLM 模式：使用可配置的調試回應
                if self.config_loader:
                    debug_response = self.config_loader.get_debug_response()
                    print(f"🔧 State Machine Debug Mode:")
                    print(f"   武器: {debug_response.get('weapons', [])}")
                else:
                    # 備用硬編碼回應
                    debug_response = {
                        'caption': 'Emergency defense protocol activated.',
                        'caption_tc': '緊急防禦協議啟動。',
                        'weapons': ['01', '02']
                    }
                
                # 💡 修復：No-LLM模式下也要設置pending_weapons
                self.pending_weapons = debug_response.get('weapons', [])
                print(f"🔧 No-LLM Mode: 設置pending_weapons = {self.pending_weapons}")
                    
                self.transition_to(SystemState.CAPTION)
                self.caption_display_requested.emit(debug_response)
            else:
                self.transition_to(SystemState.LLM_LOADING)
                
        elif state == SystemState.LLM_LOADING:
            # 等待 AI 分析完成
            pass
            
        elif state == SystemState.CAPTION:
            # 字幕顯示不使用計時器，等待完成信號
            pass
            
        elif state == SystemState.SPOTLIGHT:
            # 聚光燈狀態
            self.spotlight_requested.emit()
            # Spotlight狀態不需要計時器，由SSR控制器決定何時進入下一狀態
            
        elif state == SystemState.IMG_SHOW:
            # 武器展示會由 weapon display 控制時間
            pass
            
        elif state == SystemState.RESET:
            # 重置並等待冷卻
            self.reset_requested.emit()
            cooldown = self.config.get('cooldown_time', 3.0) * 1000
            self.state_timer.start(int(cooldown))
            
    def _handle_state_timeout(self):
        """處理狀態超時"""
        self.state_timer.stop()
        
        if self.current_state == SystemState.RESET:
            # 冷卻完成，返回偵測
            self.transition_to(SystemState.DETECTING)
            
    def update_face_detection(self, face_detected):
        """更新人臉偵測狀態"""
        if self.current_state != SystemState.DETECTING:
            return
            
        if face_detected and not self.face_detected:
            # 開始偵測
            self.face_detected = True
            self.detection_start_time = time.time()
            
        elif not face_detected and self.face_detected:
            # 偵測中斷
            self.face_detected = False
            self.detection_start_time = None
            
        elif face_detected and self.face_detected:
            # 檢查是否達到觸發閾值
            if self.detection_start_time:
                elapsed = time.time() - self.detection_start_time
                threshold = self.config.get('detect_duration', 3.0)
                if elapsed >= threshold:
                    self.transition_to(SystemState.SCREENSHOT_TRIGGER)
                    
    def on_llm_complete(self, response):
        """AI 分析完成"""
        if self.current_state == SystemState.LLM_LOADING:
            # 暫存武器列表
            self.pending_weapons = response.get('weapons', [])
            self.transition_to(SystemState.CAPTION)
            self.caption_display_requested.emit(response)
            
    def on_caption_complete(self):
        """字幕顯示完成（包括打字和等待）"""
        if self.current_state == SystemState.CAPTION:
            # 進入聚光燈狀態
            self.transition_to(SystemState.SPOTLIGHT)
            
    def on_spotlight_ready(self):
        """聚光燈準備完成，可以顯示武器"""
        if self.current_state == SystemState.SPOTLIGHT:
            print(f"🎯 聚光燈準備完成，發送武器展示請求: {self.pending_weapons}")
            self.transition_to(SystemState.IMG_SHOW)
            self.weapon_display_requested.emit(self.pending_weapons)
            
    def on_weapon_display_complete(self):
        """武器展示完成"""
        if self.current_state == SystemState.IMG_SHOW:
            self.transition_to(SystemState.RESET)
            
    def get_detection_time(self):
        """獲取當前偵測時間"""
        if self.face_detected and self.detection_start_time:
            return time.time() - self.detection_start_time
        return 0.0