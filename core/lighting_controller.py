# Location: project_v2/core/lighting_controller.py
# Usage: 燈光控制器 - 完整版本，整合所有燈光控制邏輯

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class LightingController(QObject):
    """燈光控制器 - 統一管理所有燈光和武器控制"""
   
    # 信號定義
    status_changed = pyqtSignal(str)
    spotlight_ready = pyqtSignal()
    caption_lighting_ready = pyqtSignal()
    debug_message = pyqtSignal(str)  # Debug訊息信號
   
    def __init__(self, esp32_controller, osc_controller=None, no_esp32_mode=False):
        super().__init__()
        self.esp32 = esp32_controller
        self.osc_controller = osc_controller
        self.no_esp32_mode = no_esp32_mode
       
        # ESP32 B 腳位分配 (SSR控制)
        # 1-10: WeaponLight, 11: Spotlight, 12: InstallationSSR, 13: wallLightSSR
        self.weapon_light_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # G4~G21 (1-10)
        self.spotlight_pin = 22        # G22 (11)
        self.installation_pin = 23     # G23 (12)
        self.wall_light_pin = 25       # G25 (13)
       
        self.all_esp32b_pins = self.weapon_light_pins + [self.spotlight_pin, self.installation_pin, self.wall_light_pin]
       
        # ESP32 A 武器腳位分配 (武器硬體控制)
        self.esp32a_weapon_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # G4~G21 (1-10)
       
        # 🔥 修復：ESP32 C 自動關閉計時器
        from PyQt6.QtCore import QTimer
        self.esp32c_timer = QTimer()
        self.esp32c_timer.setSingleShot(True)
        self.esp32c_timer.timeout.connect(self.auto_turn_off_esp32c)
        self.weapon_timers = {}  # 存儲武器計時器
       
        # 狀態追蹤
        self.current_state = "DETECTING"
       
        # 模擬模式的狀態追蹤（用於無ESP32模式）
        self.simulated_states = {
            'A': {},  # ESP32 A pin states
            'B': {},  # ESP32 B pin states  
            'C': {}   # ESP32 C pin states
        }
       
        # 初始化模擬狀態
        self._init_simulated_states()
       
        # 連接ESP32信號
        if self.esp32:
            self.esp32.status_changed.connect(self.on_status_changed)
   
    def _init_simulated_states(self):
        """初始化模擬狀態"""
        for pin in self.esp32a_weapon_pins:
            self.simulated_states['A'][pin] = 'LOW'
        for pin in self.all_esp32b_pins:
            self.simulated_states['B'][pin] = 'LOW'
        self.simulated_states['C'][4] = 'LOW'
   
    def on_status_changed(self, status):
        """處理ESP32狀態變化"""
        self.status_changed.emit(status)
   
    def handle_state_lighting(self, state_name):
        """根據系統狀態控制燈光"""
        self.current_state = state_name
        print(f"=== 燈光控制：進入 {state_name} 狀態 ===")
       
        if state_name in ["DETECTING", "LLM_LOADING"]:
            # 偵測和載入狀態：所有燈光開啟
            self.set_detecting_lighting()
            # 🔥 修復：僅在進入 DETECTING 狀態時啟動 ESP32 C 計時器，避免在 LLM_LOADING 時重複啟動
            if state_name == "DETECTING":
                self.start_esp32c_auto_off_timer()
           
        elif state_name == "SPOTLIGHT":
            # 聚光燈狀態：所有燈光關閉
            self.set_all_lights_off()
           
        elif state_name == "CAPTION":
            # 字幕狀態：所有燈光關閉
            self.set_all_lights_off()
           
        elif state_name == "RESET":
            # 重置狀態：返回初始狀態
            self.reset_lighting()
           
        self.debug_message.emit(f"State: {state_name} - Lighting updated")
   
    def set_detecting_lighting(self):
        """設置偵測/LLM載入狀態的燈光 - 所有燈光開啟"""
        print("設置偵測狀態燈光 - 所有燈光開啟")
       
        if self.no_esp32_mode:
            # 模擬模式
            self._simulate_detecting_lighting()
        else:
            # 實際控制
            self._actual_detecting_lighting()
       
        # OSC控制
        self._osc_all_lights(True)
   
    def _simulate_detecting_lighting(self):
        """模擬偵測狀態燈光"""
        # ESP32 B: 全部 HIGH
        for i, pin in enumerate(self.all_esp32b_pins, 1):
            self.simulated_states['B'][pin] = 'HIGH'
            self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> HIGH (/light {i} 1)")
        # ESP32 C: G4 HIGH
        self.simulated_states['C'][4] = 'HIGH'
        self.debug_message.emit("[SIM] ESP32 C G4 -> HIGH")
   
    def _actual_detecting_lighting(self):
        """實際偵測狀態燈光控制"""
        if self.esp32:
            # ESP32 B: 1-13 全部開啟 (HIGH)
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                self.debug_message.emit(f"ESP32 B G{pin} -> HIGH (/light {i} 1)")
               
            # ESP32 C: G4 開啟 (HIGH)
            self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
            self.debug_message.emit("ESP32 C G4 -> HIGH")
   
    def set_all_lights_on(self):
        """設置所有燈光為開啟狀態（別名方法）"""
        self.set_detecting_lighting()
   
    def set_all_lights_off(self):
        """設置所有燈光為關閉狀態"""
        print("設置所有燈光為關閉狀態")
       
        if self.no_esp32_mode:
            # 模擬模式
            self._simulate_all_lights_off()
        else:
            # 實際控制
            self._actual_all_lights_off()
       
        # OSC控制
        self._osc_all_lights(False)
   
    def _simulate_all_lights_off(self):
        """模擬所有燈光關閉"""
        # ESP32 B: 全部 LOW
        for i, pin in enumerate(self.all_esp32b_pins, 1):
            self.simulated_states['B'][pin] = 'LOW'
            self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> LOW (/light {i} 0)")
        # ESP32 C: G4 LOW
        self.simulated_states['C'][4] = 'LOW'
        self.debug_message.emit("[SIM] ESP32 C G4 -> LOW")
   
    def _actual_all_lights_off(self):
        """實際關閉所有燈光"""
        if self.esp32:
            # ESP32 B: 1-13 全部關閉 (LOW)
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.esp32.set_esp32_pin_state('B', pin, 'LOW', 0)
                self.debug_message.emit(f"ESP32 B G{pin} -> LOW (/light {i} 0)")
               
            # ESP32 C: G4 關閉 (LOW)
            self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
            self.debug_message.emit("ESP32 C G4 -> LOW")
   
    def _osc_all_lights(self, state):
        """OSC控制所有燈光"""
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, state)
                self.debug_message.emit(f"OSC: /light {i} {1 if state else 0}")
   
    def start_caption_lighting(self):
        """開始字幕燈光 - 關閉所有燈光"""
        print("=== CAPTION 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
       
        # 等待後發送準備信號
        QTimer.singleShot(500, self.caption_lighting_ready.emit)
       
    def start_spotlight(self):
        """開始聚光燈狀態 - 關閉所有燈光"""
        print("=== SPOTLIGHT 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
       
        # 等待後發送準備信號
        QTimer.singleShot(500, self.spotlight_ready.emit)
   
    def activate_weapon_light(self, weapon_id, duration_ms):
        """啟動特定武器的燈光（包含硬體和燈光）"""
        weapon_num = int(weapon_id)
        print(f"啟動武器 {weapon_num} 燈光 - 持續 {duration_ms}ms")
       
        if 1 <= weapon_num <= 10:
            # 啟動武器硬體和燈光
            self._activate_weapon_hardware(weapon_num)
            self._activate_weapon_lighting(weapon_num)
           
            # 電磁砲特殊處理 (5,6,7)
            if weapon_id in ['05', '06', '07']:
                self._activate_electromagnetic_cannon(weapon_num, duration_ms)
           
            # 設定關閉計時器
            self._schedule_weapon_deactivation(weapon_num, duration_ms)
   
    def _activate_weapon_hardware(self, weapon_num):
        """啟動武器硬體（ESP32 A）"""
        if self.no_esp32_mode:
            # 模擬模式
            weapon_pin_a = self.esp32a_weapon_pins[weapon_num - 1]
            self.simulated_states['A'][weapon_pin_a] = 'HIGH'
            self.debug_message.emit(f"[SIM] ESP32 A G{weapon_pin_a} -> HIGH (武器{weapon_num})")
        else:
            # 實際控制
            if self.esp32:
                weapon_pin_a = self.esp32a_weapon_pins[weapon_num - 1]
                self.esp32.set_esp32_pin_state('A', weapon_pin_a, 'HIGH', 0)
                self.debug_message.emit(f"ESP32 A G{weapon_pin_a} -> HIGH (武器{weapon_num})")
   
    def _activate_weapon_lighting(self, weapon_num):
        """啟動武器燈光（ESP32 B）"""
        if self.no_esp32_mode:
            # 模擬模式
            weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
            self.simulated_states['B'][weapon_pin_b] = 'HIGH'
            self.debug_message.emit(f"[SIM] ESP32 B G{weapon_pin_b} -> HIGH (/light {weapon_num} 1)")
        else:
            # 實際控制
            if self.esp32:
                weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                self.esp32.set_esp32_pin_state('B', weapon_pin_b, 'HIGH', 0)
                self.debug_message.emit(f"ESP32 B G{weapon_pin_b} -> HIGH (/light {weapon_num} 1)")
       
        # OSC控制
        if self.osc_controller:
            self.osc_controller.send_light_command(weapon_num, True)
            self.debug_message.emit(f"OSC: /light {weapon_num} 1")
   
    def _activate_electromagnetic_cannon(self, weapon_num, duration_ms):
        """電磁砲特殊處理 - 同時啟動wall light"""
        print(f"電磁砲 {weapon_num}: 同時啟動wall light")
       
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['B'][self.wall_light_pin] = 'HIGH'
            self.debug_message.emit(f"[SIM] ESP32 B G{self.wall_light_pin} -> HIGH (/light 13 1) - 電磁砲")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'HIGH', 0)
                self.debug_message.emit(f"ESP32 B G{self.wall_light_pin} -> HIGH (/light 13 1) - 電磁砲")
       
        # OSC控制
        if self.osc_controller:
            self.osc_controller.send_light_command(13, True)
            self.debug_message.emit("OSC: /light 13 1 - 電磁砲")
       
        # 設定關閉計時器
        QTimer.singleShot(duration_ms, self.deactivate_wall_light)
   
    def _schedule_weapon_deactivation(self, weapon_num, duration_ms):
        """安排武器關閉"""
        # 清除舊計時器
        if weapon_num in self.weapon_timers:
            self.weapon_timers[weapon_num].stop()
       
        # 設定新計時器
        timer = QTimer()
        timer.timeout.connect(lambda: self.deactivate_weapon_light(weapon_num))
        timer.setSingleShot(True)
        timer.start(duration_ms)
        self.weapon_timers[weapon_num] = timer
   
    def deactivate_weapon_light(self, weapon_num):
        """關閉特定武器的燈光"""
        print(f"關閉武器 {weapon_num} 燈光")
       
        if 1 <= weapon_num <= 10:
            # 關閉武器硬體
            self._deactivate_weapon_hardware(weapon_num)
            # 關閉武器燈光
            self._deactivate_weapon_lighting(weapon_num)
           
            # 清除計時器
            if weapon_num in self.weapon_timers:
                del self.weapon_timers[weapon_num]
   
    def _deactivate_weapon_hardware(self, weapon_num):
        """關閉武器硬體（ESP32 A）"""
        if self.no_esp32_mode:
            # 模擬模式
            weapon_pin_a = self.esp32a_weapon_pins[weapon_num - 1]
            self.simulated_states['A'][weapon_pin_a] = 'LOW'
            self.debug_message.emit(f"[SIM] ESP32 A G{weapon_pin_a} -> LOW (武器{weapon_num})")
        else:
            # 實際控制
            if self.esp32:
                weapon_pin_a = self.esp32a_weapon_pins[weapon_num - 1]
                self.esp32.set_esp32_pin_state('A', weapon_pin_a, 'LOW', 0)
                self.debug_message.emit(f"ESP32 A G{weapon_pin_a} -> LOW (武器{weapon_num})")
   
    def _deactivate_weapon_lighting(self, weapon_num):
        """關閉武器燈光（ESP32 B）"""
        if self.no_esp32_mode:
            # 模擬模式
            weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
            self.simulated_states['B'][weapon_pin_b] = 'LOW'
            self.debug_message.emit(f"[SIM] ESP32 B G{weapon_pin_b} -> LOW (/light {weapon_num} 0)")
        else:
            # 實際控制
            if self.esp32:
                weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                self.esp32.set_esp32_pin_state('B', weapon_pin_b, 'LOW', 0)
                self.debug_message.emit(f"ESP32 B G{weapon_pin_b} -> LOW (/light {weapon_num} 0)")
       
        # OSC控制
        if self.osc_controller:
            self.osc_controller.send_light_command(weapon_num, False)
            self.debug_message.emit(f"OSC: /light {weapon_num} 0")
   
    def deactivate_wall_light(self):
        """關閉wall light（電磁砲特殊燈光）"""
        print("關閉wall light")
       
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['B'][self.wall_light_pin] = 'LOW'
            self.debug_message.emit(f"[SIM] ESP32 B G{self.wall_light_pin} -> LOW (/light 13 0)")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'LOW', 0)
                self.debug_message.emit(f"ESP32 B G{self.wall_light_pin} -> LOW (/light 13 0)")
           
        # OSC控制
        if self.osc_controller:
            self.osc_controller.send_light_command(13, False)
            self.debug_message.emit("OSC: /light 13 0")
   
    def reset_lighting(self):
        """重置燈光狀態 - 返回初始狀態"""
        print("重置燈光狀態")
       
        # ESP32 A: 所有武器腳位關閉 (LOW)
        self._reset_weapon_hardware()
       
        # ESP32 B: 所有腳位開啟 (HIGH)
        # ESP32 C: G4 開啟 (HIGH)
        self.set_detecting_lighting()
       
        self.status_changed.emit("All lights reset to initial state")
   
    def _reset_weapon_hardware(self):
        """重置所有武器硬體"""
        if self.no_esp32_mode:
            # 模擬模式
            for pin in self.esp32a_weapon_pins:
                self.simulated_states['A'][pin] = 'LOW'
                self.debug_message.emit(f"[SIM] ESP32 A G{pin} -> LOW")
        else:
            # 實際控制
            if self.esp32:
                for pin in self.esp32a_weapon_pins:
                    self.esp32.set_esp32_pin_state('A', pin, 'LOW', 0)
                    self.debug_message.emit(f"ESP32 A G{pin} -> LOW")
   
    def print_debug_status(self):
        """打印當前狀態（用於調試）"""
        print(f"=== Lighting Controller Debug Status ===")
        print(f"Current State: {self.current_state}")
        print(f"No ESP32 Mode: {self.no_esp32_mode}")
       
        if self.no_esp32_mode:
            print("Simulated States:")
            print(f"  ESP32 A (武器硬體):")
            for i, pin in enumerate(self.esp32a_weapon_pins, 1):
                print(f"    武器{i} (G{pin}): {self.simulated_states['A'][pin]}")
           
            print(f"  ESP32 B (SSR燈光):")
            for i, pin in enumerate(self.weapon_light_pins, 1):
                print(f"    燈光{i} (G{pin}): {self.simulated_states['B'][pin]}")
            print(f"    Spotlight (G{self.spotlight_pin}): {self.simulated_states['B'][self.spotlight_pin]}")
            print(f"    Installation (G{self.installation_pin}): {self.simulated_states['B'][self.installation_pin]}")
            print(f"    WallLight (G{self.wall_light_pin}): {self.simulated_states['B'][self.wall_light_pin]}")
           
            print(f"  ESP32 C (安裝控制):")
            print(f"    Installation (G4): {self.simulated_states['C'][4]}")
   
    def get_simulated_states(self):
        """取得模擬狀態（用於調試顯示）"""
        return self.simulated_states.copy()
   
    def start_esp32c_auto_off_timer(self):
        """🔥 新增：啟動ESP32 C G4的自動關閉計時器"""
        from utils import ConfigLoader
        
        # 從配置獲取時間，預設5秒
        config_loader = ConfigLoader()
        period_config = config_loader.load_period_config()
        auto_off_time = period_config.get('esp32c_auto_off_time', 5) * 1000
        
        print(f"⏰ LightingController: 啟動ESP32 C G4自動關閉計時器: {auto_off_time/1000}秒")
        
        # 停止現有計時器
        if self.esp32c_timer.isActive():
            self.esp32c_timer.stop()
        
        # 啟動新計時器
        self.esp32c_timer.start(int(auto_off_time))
        print(f"⏰ LightingController: 計時器已啟動 - isActive: {self.esp32c_timer.isActive()}, interval: {self.esp32c_timer.interval()}ms")
    
    def auto_turn_off_esp32c(self):
        """🔥 新增：自動關閉ESP32 C G4"""
        print("⏰ LightingController: ESP32 C G4 自動關閉")
        
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['C'][4] = 'LOW'
            self.debug_message.emit("[SIM] ESP32 C G4 -> LOW (auto)")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
                self.debug_message.emit("ESP32 C G4 -> LOW (auto)")
    
    def cleanup(self):
        """清理資源"""
        # 停止所有計時器
        for timer in self.weapon_timers.values():
            timer.stop()
        self.weapon_timers.clear()
       
        if self.esp32c_timer and self.esp32c_timer.isActive():
            self.esp32c_timer.stop()
       
        print("LightingController cleanup completed")

