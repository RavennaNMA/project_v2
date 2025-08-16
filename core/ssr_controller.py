# Location: project_v2/core/ssr_controller.py
# Usage: SSR 燈光控制器（修改為使用ESP32）

import csv
import os
from PyQt6.QtCore import QThread, QObject, pyqtSignal


class SSRConfig:
    """SSR配置類"""
    
    def __init__(self):
        # SSR1 現在控制多個腳位
        self.ssr1_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23]  # 12個腳位
        self.ssr2_pin = 25  # SSR2 只控制單一腳位
        
        self.ssr1_delay_before = 0
        self.ssr2_delay_before = 0
        self.ssr1_high_time = 0
        self.ssr2_high_time = 0
        self.ssr1_wait_after = 0
        self.ssr2_wait_after = 0
        
        self.load_config()
    
    def load_config(self):
        """載入配置"""
        try:
            if os.path.exists('config/otherssr_config.csv'):
                with open('config/otherssr_config.csv', 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['name'] == 'SSR1':
                            # SSR1 的 pin 欄位現在存儲多個腳位（以分號分隔）
                            self.ssr1_pins = [int(p.strip()) for p in row['pin'].split(';')]
                            self.ssr1_delay_before = int(row['delay_before'])
                            self.ssr1_high_time = int(row['high_time'])
                            self.ssr1_wait_after = int(row['wait_after'])
                        elif row['name'] == 'SSR2':
                            self.ssr2_pin = int(row['pin'])
                            self.ssr2_delay_before = int(row['delay_before'])
                            self.ssr2_high_time = int(row['high_time'])
                            self.ssr2_wait_after = int(row['wait_after'])
                            
                print(f"SSR設定載入：SSR1 Pins {self.ssr1_pins}, SSR2 Pin {self.ssr2_pin}")
            else:
                print("config/otherssr_config.csv 不存在，創建預設配置")
                self.create_default_config()
                
        except Exception as e:
            print(f"載入SSR配置時發生錯誤: {e}")
            print("使用預設配置")
            
    def create_default_config(self):
        """創建預設配置檔案"""
        try:
            with open('config/otherssr_config.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'pin', 'delay_before', 'high_time', 'wait_after'])
                # SSR1 使用分號分隔多個腳位
                writer.writerow(['SSR1', '4;5;12;13;14;16;17;18;19;21;22;23', 0, 0, 3000])
                writer.writerow(['SSR2', 25, 0, 0, 0])
            print("已創建預設 config/otherssr_config.csv")
        except Exception as e:
            print(f"創建預設配置時發生錯誤: {e}")


class SSRThread(QThread):
    """SSR控制執行緒"""
    
    status_changed = pyqtSignal(str)
    ssr1_ready = pyqtSignal()  # SSR1準備完成
    ssr2_ready = pyqtSignal()  # SSR2準備完成
    
    def __init__(self, esp32_controller, ssr_config):
        super().__init__()
        self.esp32 = esp32_controller  # 使用ESP32控制器
        self.config = ssr_config
        self.ssr1_active = False
        self.ssr2_active = False
        self.ssr1_processed = False
        self.ssr2_processed = False
        self.should_stop = False
        
    def activate_ssr1(self):
        """啟動SSR1"""
        print("Activating SSR1")
        self.ssr1_active = True
        self.ssr1_processed = False
        
    def activate_ssr2(self):
        """啟動SSR2"""
        print("Activating SSR2")
        self.ssr2_active = True
        self.ssr2_processed = False
        
    def deactivate_all(self):
        """關閉所有SSR"""
        self.should_stop = True
        
    def run(self):
        """執行緒主邏輯"""
        print("🔌 SSR執行緒啟動")
        
        while not self.should_stop:
            # 檢查SSR1
            if self.ssr1_active and not self.ssr1_processed:
                print(f"🔦 處理 SSR1: Pins {self.config.ssr1_pins}")
                
                # 等待前延遲
                if self.config.ssr1_delay_before > 0:
                    self.status_changed.emit(f"SSR1等待前延遲 {self.config.ssr1_delay_before}ms")
                    self.msleep(self.config.ssr1_delay_before)
                
                # 設定所有SSR1腳位為HIGH
                if self.esp32:
                    try:
                        for pin in self.config.ssr1_pins:
                            print(f"設定 SSR1 Pin {pin} 為 HIGH")
                            # 🔥 修復：直接設置ESP32 B的腳位，不使用Arduino映射
                            self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                        self.status_changed.emit(f"SSR1 Pins {self.config.ssr1_pins} -> HIGH")
                        
                        # 🔥 新增：同時設置ESP32(C)的腳位為HIGH
                        print("設定 ESP32(C) Pin 4 為 HIGH")
                        self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
                        self.status_changed.emit("ESP32(C) Pin 4 -> HIGH")
                        
                    except Exception as e:
                        print(f"⚠️ SSR1 控制錯誤: {e}")
                else:
                    print("⚠️ 警告：ESP32 控制器不可用於 SSR1")
                
                # 等待後延遲
                if self.config.ssr1_wait_after > 0:
                    print(f"⏳ SSR1 等待 {self.config.ssr1_wait_after}ms 後觸發字幕顯示")
                    self.status_changed.emit(f"SSR1等待 {self.config.ssr1_wait_after}ms 後顯示字幕")
                    self.msleep(self.config.ssr1_wait_after)
                
                self.ssr1_processed = True
                self.ssr1_active = False
                
                # 🔥 重要：發出 SSR1 準備完成信號
                print(" SSR1 處理完成，發出準備信號")
                self.ssr1_ready.emit()
                
                # 🔥 可選：如果您希望ESP32(C)在SSR1完成後自動設為LOW，請取消註釋以下代碼
                # if self.esp32:
                #     try:
                #         print("SSR1完成，將ESP32(C) Pin 4設為LOW")
                #         self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
                #         self.status_changed.emit("ESP32(C) Pin 4 -> LOW (SSR1完成)")
                #     except Exception as e:
                #         print(f"⚠️ ESP32(C) 設為LOW時發生錯誤: {e}")
                # else:
                #     print("⚠️ 警告：ESP32 控制器不可用於設置ESP32(C)為LOW")
                
            # 檢查SSR2
            if self.ssr2_active and not self.ssr2_processed:
                print(f"💡 處理 SSR2: Pin {self.config.ssr2_pin}")
                
                # 等待前延遲
                if self.config.ssr2_delay_before > 0:
                    self.status_changed.emit(f"SSR2等待前延遲 {self.config.ssr2_delay_before}ms")
                    self.msleep(self.config.ssr2_delay_before)
                
                # 設定為HIGH
                if self.esp32:
                    try:
                        print(f"設定 SSR2 Pin {self.config.ssr2_pin} 為 HIGH")
                        # 🔥 修復：直接設置ESP32 B的腳位，不使用Arduino映射
                        self.esp32.set_esp32_pin_state('B', self.config.ssr2_pin, 'HIGH', 0)
                        self.status_changed.emit(f"SSR2 Pin {self.config.ssr2_pin} -> HIGH")
                    except Exception as e:
                        print(f"⚠️ SSR2 控制錯誤: {e}")
                else:
                    print("⚠️ 警告：ESP32 控制器不可用於 SSR2")
                
                # 等待後延遲
                if self.config.ssr2_wait_after > 0:
                    self.status_changed.emit(f"SSR2等待後延遲 {self.config.ssr2_wait_after}ms")
                    self.msleep(self.config.ssr2_wait_after)
                
                self.ssr2_processed = True
                self.ssr2_active = False
                
                # 🔥 重要：發出 SSR2 準備完成信號
                print(" SSR2 處理完成，發出準備信號")
                self.ssr2_ready.emit()
                
            self.msleep(50)  # 短暫休眠
        
        print("🔌 SSR執行緒結束")



class LightingController(QObject):
    """新版燈光控制器 - 根據用戶需求重新設計"""
    
    status_changed = pyqtSignal(str)
    spotlight_ready = pyqtSignal()
    caption_lighting_ready = pyqtSignal()
    debug_message = pyqtSignal(str)  # 🔥 新增：用於debug顯示的信號
    
    def __init__(self, esp32_controller, osc_controller=None, no_esp32_mode=False):
        super().__init__()
        self.esp32 = esp32_controller
        self.osc_controller = osc_controller
        self.no_esp32_mode = no_esp32_mode  # 🔥 新增：無ESP32模式
        
        # ESP32 B 腳位分配 (根據用戶規範)
        self.weapon_light_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # G4~G21 (1-10): WeaponLight
        self.spotlight_pin = 22        # G22 (11): Spotlight
        self.installation_pin = 23     # G23 (12): InstallationSSR
        self.wall_light_pin = 25       # G25 (13): wallLightSSR
        
        self.all_esp32b_pins = self.weapon_light_pins + [self.spotlight_pin, self.installation_pin, self.wall_light_pin]
        
        # ESP32 A 武器腳位分配
        self.esp32a_weapon_pins = [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]  # G4~G21 (1-10): 對應武器
        
        self.esp32c_timer = None
        self.current_state = "DETECTING"  # 🔥 新增：當前狀態追蹤
        
        # 🔥 新增：模擬模式的狀態追蹤（用於無ESP32模式）
        self.simulated_states = {
            'A': {},  # ESP32 A pin states
            'B': {},  # ESP32 B pin states  
            'C': {}   # ESP32 C pin states
        }
        # 初始化模擬狀態
        for pin in self.esp32a_weapon_pins:
            self.simulated_states['A'][pin] = 'LOW'
        for pin in self.all_esp32b_pins:
            self.simulated_states['B'][pin] = 'LOW'
        self.simulated_states['C'][4] = 'LOW'
        
        # 連接ESP32信號
        if self.esp32:
            self.esp32.status_changed.connect(self.on_status_changed)
    
    def handle_state_lighting(self, state_name):
        """🔥 新增：根據狀態控制燈光"""
        self.current_state = state_name
        print(f"🎭 LightingController: 狀態變更為 {state_name}")
        
        if state_name in ["DETECTING", "LLM_LOADING"]:
            # ESP32 B 所有 SSR = HIGH
            self.set_detecting_lighting()
            
        elif state_name == "SPOTLIGHT":
            # 全關 (LOW)
            self.set_all_lights_off()
            
        elif state_name == "CAPTION":
            # 全關 (LOW) - CAPTION狀態開始時關閉所有燈光
            self.set_all_lights_off()
            
        elif state_name == "RESET":
            # ESP32 A weapons = LOW, ESP32 B = HIGH, ESP32 C G4 = HIGH
            self.reset_lighting()
            
        self.debug_message.emit(f"State: {state_name} - Lighting updated")
    
    def set_detecting_lighting(self):
        """設置偵測/LLM載入狀態的燈光 - ESP32 B 和 ESP32 C 全HIGH"""
        print("🌟 設置偵測狀態燈光: ESP32 B 和 ESP32 C 全HIGH")
        
        if self.no_esp32_mode:
            # 模擬模式
            # ESP32 B: 全部 HIGH
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.simulated_states['B'][pin] = 'HIGH'
                self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> HIGH (lighton{i:02d})")
            # ESP32 C: G4 HIGH
            self.simulated_states['C'][4] = 'HIGH'
            self.debug_message.emit("[SIM] ESP32 C G4 -> HIGH")
        else:
            # 實際控制
            if self.esp32:
                # ESP32 B: 全部 HIGH
                for i, pin in enumerate(self.all_esp32b_pins, 1):
                    self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                    self.debug_message.emit(f"ESP32 B G{pin} -> HIGH (lighton{i:02d})")
                # ESP32 C: G4 HIGH
                self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
                self.debug_message.emit("ESP32 C G4 -> HIGH")
                    
        # OSC: 所有燈開啟
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, True)
                self.debug_message.emit(f"OSC: lighton{i:02d}")
    
    def set_all_lights_on(self):
        """設置所有燈光為開啟狀態 (平常/偵測中)"""
        print("🌟 設置所有燈光為開啟狀態")
        
        if self.no_esp32_mode:
            # 模擬模式
            # ESP32 B: 1-13 全部開啟 (HIGH)
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.simulated_states['B'][pin] = 'HIGH'
                self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> HIGH (lighton{i:02d})")
            # ESP32 C: G4 開啟 (HIGH)
            self.simulated_states['C'][4] = 'HIGH'
            self.debug_message.emit("[SIM] ESP32 C G4 -> HIGH")
        else:
            # 實際控制
            if self.esp32:
                # ESP32 B: 1-13 全部開啟 (HIGH)
                for i, pin in enumerate(self.all_esp32b_pins, 1):
                    self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                    self.debug_message.emit(f"ESP32 B G{pin} -> HIGH (lighton{i:02d})")
                    
                # ESP32 C: G4 開啟 (HIGH)
                self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
                self.debug_message.emit("ESP32 C G4 -> HIGH")
        
        # OSC: 所有燈開啟
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, True)
                self.debug_message.emit(f"OSC: lighton{i:02d}")
    
    def set_all_lights_off(self):
        """設置所有燈光為關閉狀態 (Spotlight/Caption狀態)"""
        print("🌑 設置所有燈光為關閉狀態")
        
        if self.no_esp32_mode:
            # 模擬模式
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.simulated_states['B'][pin] = 'LOW'
                self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> LOW (lightoff{i:02d})")
            self.simulated_states['C'][4] = 'LOW'
            self.debug_message.emit("[SIM] ESP32 C G4 -> LOW")
        else:
            # 實際控制
            if self.esp32:
                # ESP32 B: 1-13 全部關閉 (LOW)
                for i, pin in enumerate(self.all_esp32b_pins, 1):
                    self.esp32.set_esp32_pin_state('B', pin, 'LOW', 0)
                    self.debug_message.emit(f"ESP32 B G{pin} -> LOW (lightoff{i:02d})")
                    
                # ESP32 C: G4 關閉 (LOW)
                self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
                self.debug_message.emit("ESP32 C G4 -> LOW")
        
        # OSC: 所有燈關閉
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, False)
                self.debug_message.emit(f"OSC: lightoff{i:02d}")
    
    def start_caption_lighting(self):
        """開始字幕燈光 - 實際上是關閉所有燈光"""
        print("=== CAPTION 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
        
        # 等待配置的時間後發送準備信號
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.caption_lighting_ready.emit)
        
    def start_spotlight(self):
        """開始聚光燈狀態 - 關閉所有燈光"""
        print("=== SPOTLIGHT 狀態: 關閉所有燈光 ===")
        self.set_all_lights_off()
        
        # 等待後發送準備信號
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.spotlight_ready.emit)
    
    def activate_weapon_light(self, weapon_id, duration_ms):
        """啟動特定武器的燈光 - CAPTIONS狀態期間使用"""
        weapon_num = int(weapon_id)
        print(f"🔫 啟動武器 {weapon_num} 燈光")
        
        if 1 <= weapon_num <= 10:
            # ESP32 A: 對應武器腳位 HIGH
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
            
            # ESP32 B: 對應武器燈光 HIGH
            if self.no_esp32_mode:
                # 模擬模式
                weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                self.simulated_states['B'][weapon_pin_b] = 'HIGH'
                self.debug_message.emit(f"[SIM] ESP32 B G{weapon_pin_b} -> HIGH (lighton{weapon_num:02d})")
            else:
                # 實際控制
                if self.esp32:
                    weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                    self.esp32.set_esp32_pin_state('B', weapon_pin_b, 'HIGH', 0)
                    self.debug_message.emit(f"ESP32 B G{weapon_pin_b} -> HIGH (lighton{weapon_num:02d})")
            
            # OSC: 對應燈光
            if self.osc_controller:
                self.osc_controller.send_light_command(weapon_num, True)
                self.debug_message.emit(f"OSC: lighton{weapon_num:02d}")
            
            # 電磁砲特殊處理 (5,6,7)
            if weapon_id in ['05', '06', '07']:
                print(f"🔥 電磁砲 {weapon_num}: 同時啟動wall light")
                
                if self.no_esp32_mode:
                    # 模擬模式
                    self.simulated_states['B'][self.wall_light_pin] = 'HIGH'
                    self.debug_message.emit(f"[SIM] ESP32 B G{self.wall_light_pin} -> HIGH (lighton13) - 電磁砲")
                else:
                    # 實際控制
                    if self.esp32:
                        self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'HIGH', 0)
                        self.debug_message.emit(f"ESP32 B G{self.wall_light_pin} -> HIGH (lighton13) - 電磁砲")
                
                if self.osc_controller:
                    self.osc_controller.send_light_command(13, True)
                    self.debug_message.emit("OSC: lighton13 - 電磁砲")
                
                # 設定關閉計時器
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(duration_ms, lambda: self.deactivate_wall_light())
            
            # 設定武器燈關閉計時器
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(duration_ms, lambda: self.deactivate_weapon_light(weapon_num))
    
    def deactivate_weapon_light(self, weapon_num):
        """關閉特定武器的燈光"""
        print(f"🔫 關閉武器 {weapon_num} 燈光")
        
        if 1 <= weapon_num <= 10:
            # ESP32 A: 對應武器腳位 LOW
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
            
            # ESP32 B: 對應武器燈光 LOW
            if self.no_esp32_mode:
                # 模擬模式
                weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                self.simulated_states['B'][weapon_pin_b] = 'LOW'
                self.debug_message.emit(f"[SIM] ESP32 B G{weapon_pin_b} -> LOW (lightoff{weapon_num:02d})")
            else:
                # 實際控制
                if self.esp32:
                    weapon_pin_b = self.weapon_light_pins[weapon_num - 1]
                    self.esp32.set_esp32_pin_state('B', weapon_pin_b, 'LOW', 0)
                    self.debug_message.emit(f"ESP32 B G{weapon_pin_b} -> LOW (lightoff{weapon_num:02d})")
            
            if self.osc_controller:
                self.osc_controller.send_light_command(weapon_num, False)
                self.debug_message.emit(f"OSC: lightoff{weapon_num:02d}")
    
    def deactivate_wall_light(self):
        """關閉wall light"""
        print("🔥 關閉wall light")
        
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['B'][self.wall_light_pin] = 'LOW'
            self.debug_message.emit(f"[SIM] ESP32 B G{self.wall_light_pin} -> LOW (lightoff13)")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('B', self.wall_light_pin, 'LOW', 0)
                self.debug_message.emit(f"ESP32 B G{self.wall_light_pin} -> LOW (lightoff13)")
            
        if self.osc_controller:
            self.osc_controller.send_light_command(13, False)
            self.debug_message.emit("OSC: lightoff13")
    
    def reset_lighting(self):
        """🔥 更新：重置燈光狀態 - 符合用戶規範"""
        print("🔄 重置燈光狀態")
        
        # ESP32 A: 所有武器腳位關閉 (LOW)
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
        
        # ESP32 B: 所有腳位開啟 (HIGH)
        if self.no_esp32_mode:
            # 模擬模式
            for i, pin in enumerate(self.all_esp32b_pins, 1):
                self.simulated_states['B'][pin] = 'HIGH'
                self.debug_message.emit(f"[SIM] ESP32 B G{pin} -> HIGH (lighton{i:02d})")
        else:
            # 實際控制
            if self.esp32:
                for i, pin in enumerate(self.all_esp32b_pins, 1):
                    self.esp32.set_esp32_pin_state('B', pin, 'HIGH', 0)
                    self.debug_message.emit(f"ESP32 B G{pin} -> HIGH (lighton{i:02d})")
        
        # ESP32 C: G4 開啟 (HIGH)
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['C'][4] = 'HIGH'
            self.debug_message.emit("[SIM] ESP32 C G4 -> HIGH")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('C', 4, 'HIGH', 0)
                self.debug_message.emit("ESP32 C G4 -> HIGH")
        
        # OSC: 所有燈開啟
        if self.osc_controller:
            for i in range(1, 14):
                self.osc_controller.send_light_command(i, True)
                self.debug_message.emit(f"OSC: lighton{i:02d}")
        
        # 啟動ESP32 C G4的10秒自動關閉計時器
        self.start_esp32c_auto_off_timer()
    
    def start_esp32c_auto_off_timer(self):
        """啟動ESP32 C G4的10秒自動關閉計時器"""
        from PyQt6.QtCore import QTimer
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
        
        if self.no_esp32_mode:
            # 模擬模式
            self.simulated_states['C'][4] = 'LOW'
            self.debug_message.emit("[SIM] ESP32 C G4 -> LOW (auto)")
        else:
            # 實際控制
            if self.esp32:
                self.esp32.set_esp32_pin_state('C', 4, 'LOW', 0)
                self.debug_message.emit("ESP32 C G4 -> LOW (auto)")
    
    def stop_esp32c_timer(self):
        """停止ESP32 C計時器"""
        if self.esp32c_timer:
            self.esp32c_timer.stop()
            self.esp32c_timer = None
            print("⏰ ESP32 C計時器已停止")
    
    def on_status_changed(self, status):
        """狀態變更處理"""
        self.status_changed.emit(status)
    
    def print_debug_status(self):
        """🔥 新增：調試狀態打印 - 向後兼容"""
        print(f"=== Lighting Controller Debug Status ===")
        print(f"  Current State: {self.current_state}")
        print(f"  ESP32 Controller: {'Available' if self.esp32 else 'None'}")
        print(f"  OSC Controller: {'Available' if self.osc_controller else 'None'}")
        print(f"  No ESP32 Mode: {self.no_esp32_mode}")
        print(f"  ESP32 C Timer: {'Running' if self.esp32c_timer and self.esp32c_timer.isActive() else 'Stopped'}")
        
        if self.no_esp32_mode:
            print("  Simulated States:")
            for esp_name, states in self.simulated_states.items():
                print(f"    ESP32 {esp_name}: {states}")
        elif self.esp32:
            print("  Real ESP32 States:")
            pin_states = self.esp32.get_esp32_pin_states()
            for esp_name, states in pin_states.items():
                print(f"    ESP32 {esp_name}: {states}")
        print("=" * 40)
    
    def cleanup(self):
        """清理資源"""
        self.stop_esp32c_timer()

# 保持向後兼容性的別名
SSRController = LightingController