# Location: project_v2/core/lighting_controller.py
# Usage: 燈光控制器 - 根據用戶需求重新設計

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class LightingController(QObject):
    """新版燈光控制器 - 根據用戶需求重新設計"""
    
    status_changed = pyqtSignal(str)
    spotlight_ready = pyqtSignal()
    caption_lighting_ready = pyqtSignal()
    
    def __init__(self, esp32_controller, osc_controller=None):
        super().__init__()
        self.esp32 = esp32_controller
        self.osc_controller = osc_controller
        
        # ESP32 B 腳位分配 (根據用戶規範)
        # 1-10 (G4~G21): WeaponLight, 11 (G22): Spotlight, 12 (G23): InstallationSSR, 13 (G25): wallLightSSR
        self.weapon_light_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # G4~G21 (1-10): WeaponLight
        self.spotlight_pin = 22        # G22 (11): Spotlight
        self.installation_pin = 23     # G23 (12): InstallationSSR
        self.wall_light_pin = 25       # G25 (13): wallLightSSR
        
        self.all_esp32b_pins = self.weapon_light_pins + [self.spotlight_pin, self.installation_pin, self.wall_light_pin]
        
        self.esp32c_timer = None
        
        # 連接ESP32信號
        if self.esp32:
            self.esp32.status_changed.connect(self.on_status_changed)
    
    def set_all_lights_on(self):
        """設置所有燈光為開啟狀態 (平常/偵測中)"""
        print("🌟 設置所有燈光為開啟狀態")
        
        if self.esp32:
            # ESP32 B: 1-13 全部開啟 (HIGH)
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                self.status_changed.emit(f"/light {i} 1")
                
            # ESP32 C: G4 開啟 (HIGH)
            self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
            self.status_changed.emit("ESP32 C G4 -> HIGH")
        
        # OSC: 所有燈開啟
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, True)
    
    def set_all_lights_off(self):
        """設置所有燈光為關閉狀態 (Spotlight/Caption狀態)"""
        print("🌑 設置所有燈光為關閉狀態")
        
        if self.esp32:
            # ESP32 B: 1-13 全部關閉 (LOW)
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.esp32.set_esp32_pin_state('B', pin, 'LOW', 0)
                self.status_changed.emit(f"lightoff{i:02d}")
                
            # ESP32 C: G4 關閉 (LOW)
            self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
            self.status_changed.emit("ESP32 C G4 -> LOW")
        
        # OSC: 所有燈關閉
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, False)
    
    def start_caption_lighting(self):
        """開始字幕燈光 - 實際上是關閉所有燈光"""
        print("=== CAPTION 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
        
        # 等待配置的時間後發送準備信號
        QTimer.singleShot(500, self.caption_lighting_ready.emit)
        
    def start_spotlight(self):
        """開始聚光燈狀態 - 關閉所有燈光"""
        print("=== SPOTLIGHT 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
        
        # 等待後發送準備信號
        QTimer.singleShot(500, self.spotlight_ready.emit)
    
    def activate_weapon_light(self, weapon_id, duration_ms):
        """啟動特定武器的燈光"""
        weapon_num = int(weapon_id)
        print(f"🔫 啟動武器 {weapon_num} 燈光")
        
        if 1 <= weapon_num <= 10 and self.esp32:
            # ESP32 B: 對應武器燈光
            weapon_pin = self.weapon_light_pins[weapon_num - 1]
            self.esp32.set_esp32_pin_state('B', weapon_pin, 'HIGH', 0)
            self.status_changed.emit(f"/light {weapon_num} 1")
            
            # OSC: 對應燈光
            if self.osc_controller:
                self.osc_controller.send_light_command(weapon_num, True)
            
            # 電磁砲特殊處理 (5,6,7)
            if weapon_id in ['05', '06', '07']:
                print(f"🔥 電磁砲 {weapon_num}: 同時啟動wall light")
                self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'HIGH', 0)
                self.status_changed.emit("/light 13 1")
                if self.osc_controller:
                    self.osc_controller.send_light_command(13, True)
                
                # 設定關閉計時器
                QTimer.singleShot(duration_ms, lambda: self.deactivate_wall_light())
            
            # 設定武器燈關閉計時器
            QTimer.singleShot(duration_ms, lambda: self.deactivate_weapon_light(weapon_num))
    
    def deactivate_weapon_light(self, weapon_num):
        """關閉特定武器的燈光"""
        print(f"🔫 關閉武器 {weapon_num} 燈光")
        
        if 1 <= weapon_num <= 10 and self.esp32:
            weapon_pin = self.weapon_light_pins[weapon_num - 1]
            self.esp32.set_esp32_pin_state('B', weapon_pin, 'LOW', 0)
            self.status_changed.emit(f"lightoff{weapon_num:02d}")
            
            if self.osc_controller:
                self.osc_controller.send_light_command(weapon_num, False)
    
    def deactivate_wall_light(self):
        """關閉wall light"""
        print("🔥 關閉wall light")
        
        if self.esp32:
            self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'LOW', 0)
            self.status_changed.emit("/light 13 0")
            
            if self.osc_controller:
                self.osc_controller.send_light_command(13, False)
    
    def reset_lighting(self):
        """重置燈光狀態"""
        print("🔄 重置燈光狀態")
        
        if self.esp32:
            # ESP32 A: 所有武器腳位關閉 (LOW)
            weapon_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # ESP32 A的武器腳位
            for pin in weapon_pins:
                self.esp32.set_esp32_pin_state('A', pin, 'LOW', 0)
            self.status_changed.emit("ESP32 A: All weapon pins -> LOW")
        
        # 設置所有燈光開啟
        self.set_all_lights_on()
        
        # 啟動ESP32 C G4的10秒自動關閉計時器
        self.start_esp32c_auto_off_timer()
    
    def start_esp32c_auto_off_timer(self):
        """啟動ESP32 C G4的10秒自動關閉計時器"""
        from utils import ConfigLoader
        
        # 從配置獲取時間，預設10秒
        config_loader = ConfigLoader()
        period_config = config_loader.load_period_config()
        auto_off_time = period_config.get('esp32c_auto_off_time', 10) * 1000
        
        print(f"⏰ 啟動ESP32 C G4自動關閉計時器: {auto_off_time/1000}秒")
        
        if self.esp32c_timer:
            self.esp32c_timer.stop()
        
        self.esp32c_timer = QTimer()
        self.esp32c_timer.setSingleShot(True)
        self.esp32c_timer.timeout.connect(self.auto_turn_off_esp32c)
        self.esp32c_timer.start(int(auto_off_time))
    
    def auto_turn_off_esp32c(self):
        """自動關閉ESP32 C G4"""
        print("⏰ ESP32 C G4 自動關閉")
        
        if self.esp32:
            self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
            self.status_changed.emit("ESP32 C G4 -> LOW (auto)")
    
    def stop_esp32c_timer(self):
        """停止ESP32 C計時器"""
        if self.esp32c_timer:
            self.esp32c_timer.stop()
            self.esp32c_timer = None
            print("⏰ ESP32 C計時器已停止")
    
    # 兼容性方法
    def stop_all_lighting(self):
        """停止所有燈光 - 重置狀態"""
        self.reset_lighting()
    
    def on_status_changed(self, status):
        """狀態變更處理"""
        self.status_changed.emit(status)
    
    def cleanup(self):
        """清理資源"""
        self.stop_esp32c_timer()

    def print_debug_status(self):
        """調試狀態打印"""
        print(f"Lighting Controller Status:")
        print(f"  ESP32 Controller: {'Available' if self.esp32 else 'None'}")
        print(f"  OSC Controller: {'Available' if self.osc_controller else 'None'}")
        print(f"  ESP32 C Timer: {'Running' if self.esp32c_timer and self.esp32c_timer.isActive() else 'Stopped'}")