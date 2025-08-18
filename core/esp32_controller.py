# Location: project_v2/core/esp32_controller.py
# Usage: ESP32 TCP 控制器，替代原本的 Arduino 控制器

import socket
import time
import threading
from PyQt6.QtCore import QThread, QObject, pyqtSignal

class ESP32Config:
    """ESP32配置"""
    def __init__(self):
        self.esp32_configs = {
            'A': {
                'ip': '192.168.0.101',
                'port': 8080,
                'pins': [4, 5, 12, 13, 14, 16, 17, 18, 19, 21],
                'name': 'Weapons',
                'timeout': 5
            },
            'B': {
                'ip': '192.168.0.102', 
                'port': 8080,
                'pins': [4, 5, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25],  # 更新為13個腳位
                'name': 'SSR Control',
                'timeout': 5
            },

            'C': {
                'ip': '192.168.0.103',
                'port': 8080,
                'pins': [4],
                'name': 'Installation',

                'timeout': 5
            }
        }
        
        # Pin mapping
        self.weapon_pin_mapping = {
            2: ('A', 4),   # Arduino D2 -> ESP32 A GPIO4
            3: ('A', 5),   # Arduino D3 -> ESP32 A GPIO5
            4: ('A', 12),  # Arduino D4 -> ESP32 A GPIO12
            5: ('A', 13),  # Arduino D5 -> ESP32 A GPIO13
            6: ('A', 14),  # Arduino D6 -> ESP32 A GPIO14
            7: ('A', 16),  # Arduino D7 -> ESP32 A GPIO16
            8: ('A', 17),  # Arduino D8 -> ESP32 A GPIO17
            9: ('A', 18),  # Arduino D9 -> ESP32 A GPIO18
            10: ('A', 19), # Arduino D10 -> ESP32 A GPIO19
            11: ('A', 21), # Arduino D11 -> ESP32 A GPIO21
            12: ('B', 4),  # Arduino D12 (SSR1) -> ESP32 B GPIO4
            13: ('B', 5),  # Arduino D13 (SSR2) -> ESP32 B GPIO5
        }


class ESP32Thread(QThread):
    """ESP32 控制執行緒"""
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    pin_state_changed = pyqtSignal(str, int, str)  # esp_name, pin, state
    connection_status_changed = pyqtSignal(str, bool)  # esp_name, is_connected
    
    def __init__(self):
        super().__init__()
        self.config = ESP32Config()
        self.is_running = False
        self.command_queue = []
        self.connections = {}
        self.pin_states = {}
        self.lock = threading.Lock()
        
        # 初始化所有ESP32的pin狀態
        for esp_name, esp_config in self.config.esp32_configs.items():
            self.pin_states[esp_name] = {}
            for pin in esp_config['pins']:
                self.pin_states[esp_name][pin] = "LOW"
                
    def run(self):
        """執行緒主迴圈"""
        self.is_running = True
        
        # 初始連接所有ESP32
        self._connect_all_esp32()
        
        # 初始化所有腳位為LOW
        self._init_all_pins()
        
        while self.is_running:
            if self.command_queue:
                with self.lock:
                    cmd = self.command_queue.pop(0)
                    
                if cmd.get('type') == 'pin_state':
                    self._execute_pin_state_command(cmd)
                elif cmd.get('type') == 'esp32_pin_state':
                    self._execute_esp32_pin_state_command(cmd)
                else:
                    self._execute_command(cmd)
                    
            self.msleep(10)
            
        # 關閉所有連接
        self._disconnect_all()
        
    def _connect_all_esp32(self):
        """連接所有ESP32"""
        for esp_name, esp_config in self.config.esp32_configs.items():
            connected = self._test_connection(esp_name)
            self.connections[esp_name] = connected
            self.connection_status_changed.emit(esp_name, connected)
            
            if connected:
                self.status_changed.emit(f"ESP32 {esp_name} ({esp_config['name']}) 已連接")
            else:
                self.error_occurred.emit(f"ESP32 {esp_name} ({esp_config['name']}) 連接失敗")
                
    def _test_connection(self, esp_name):
        """測試ESP32連接"""
        try:
            response = self._send_command(esp_name, "STATUS")
            return "ONLINE" in response
        except:
            return False
            
    def _send_command(self, esp_name, command):
        """發送TCP命令到ESP32"""
        esp_config = self.config.esp32_configs.get(esp_name)
        if not esp_config:
            return f"ERROR: Unknown ESP32 {esp_name}"
            
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(esp_config['timeout'])
            sock.connect((esp_config['ip'], esp_config['port']))
            
            sock.send((command + '\n').encode())
            response = sock.recv(1024).decode().strip()
            sock.close()
            
            return response
        except Exception as e:
            return f"ERROR: {str(e)}"
            
    def _init_all_pins(self):
        """初始化所有ESP32的腳位"""
        for esp_name, esp_config in self.config.esp32_configs.items():
            if self.connections.get(esp_name, False):
                for pin in esp_config['pins']:
                    response = self._send_command(esp_name, f"SET:{pin},0")
                    if "SET_PIN" in response:
                        self.pin_states[esp_name][pin] = "LOW"
                        self.pin_state_changed.emit(esp_name, pin, "LOW")
                        
    def _execute_command(self, cmd):
        """執行腳位控制指令（自動HIGH->LOW）"""
        arduino_pin = cmd['pin']
        wait_before = cmd.get('wait_before', 0)
        high_time = cmd.get('high_time', 1000)
        wait_after = cmd.get('wait_after', 0)
        
        # 獲取對應的ESP32和實際腳位
        if arduino_pin not in self.config.weapon_pin_mapping:
            self.error_occurred.emit(f"Arduino pin {arduino_pin} 沒有對應的ESP32映射")
            return
            
        esp_name, esp_pin = self.config.weapon_pin_mapping[arduino_pin]
        
        if not self.connections.get(esp_name, False):
            self.error_occurred.emit(f"ESP32 {esp_name} 未連接")
            return
            
        # 前延遲
        if wait_before > 0:
            time.sleep(wait_before / 1000.0)
            
        # 設為HIGH
        response = self._send_command(esp_name, f"SET:{esp_pin},1")
        if "SET_PIN" in response:
            self.pin_states[esp_name][esp_pin] = "HIGH"
            self.pin_state_changed.emit(esp_name, esp_pin, "HIGH")
            self.status_changed.emit(f"ESP32 {esp_name} Pin {esp_pin} -> HIGH")
            
        # 維持HIGH
        time.sleep(high_time / 1000.0)
        
        # 設回LOW
        response = self._send_command(esp_name, f"SET:{esp_pin},0")
        if "SET_PIN" in response:
            self.pin_states[esp_name][esp_pin] = "LOW"
            self.pin_state_changed.emit(esp_name, esp_pin, "LOW")
            self.status_changed.emit(f"ESP32 {esp_name} Pin {esp_pin} -> LOW")
            
        # 後延遲
        if wait_after > 0:
            time.sleep(wait_after / 1000.0)
            
    def _execute_pin_state_command(self, cmd):
        """執行Pin狀態控制指令（不自動切換）"""
        arduino_pin = cmd['pin']
        state = cmd['state']
        wait_before = cmd.get('wait_before', 0)
        
        # 獲取對應的ESP32和實際腳位
        if arduino_pin not in self.config.weapon_pin_mapping:
            self.error_occurred.emit(f"Arduino pin {arduino_pin} 沒有對應的ESP32映射")
            return
            
        esp_name, esp_pin = self.config.weapon_pin_mapping[arduino_pin]
        
        if not self.connections.get(esp_name, False):
            self.error_occurred.emit(f"ESP32 {esp_name} 未連接")
            return
            
        # 前延遲
        if wait_before > 0:
            time.sleep(wait_before / 1000.0)
            
        # 設置Pin狀態
        value = 1 if state == 'HIGH' else 0
        response = self._send_command(esp_name, f"SET:{esp_pin},{value}")
        
        if "SET_PIN" in response:
            self.pin_states[esp_name][esp_pin] = state
            self.pin_state_changed.emit(esp_name, esp_pin, state)
            self.status_changed.emit(f"ESP32 {esp_name} Pin {esp_pin} -> {state}")
            
    def _execute_esp32_pin_state_command(self, cmd):
        """🔥 新增：執行直接ESP32腳位狀態控制指令"""
        esp_name = cmd['esp_name']
        esp_pin = cmd['esp_pin']
        state = cmd['state']
        wait_before = cmd.get('wait_before', 0)
        
        if not self.connections.get(esp_name, False):
            self.error_occurred.emit(f"ESP32 {esp_name} 未連接")
            return
            
        # 前延遲
        if wait_before > 0:
            time.sleep(wait_before / 1000.0)
            
        # 設置Pin狀態
        value = 1 if state == 'HIGH' else 0
        response = self._send_command(esp_name, f"SET:{esp_pin},{value}")
        
        if "SET_PIN" in response:
            self.pin_states[esp_name][esp_pin] = state
            self.pin_state_changed.emit(esp_name, esp_pin, state)
            self.status_changed.emit(f"ESP32 {esp_name} Pin {esp_pin} -> {state}")
        else:
            self.error_occurred.emit(f"ESP32 {esp_name} Pin {esp_pin} 設置失敗: {response}")
            
    def add_command(self, pin, wait_before=0, high_time=1000, wait_after=0):
        """新增控制指令"""
        with self.lock:
            self.command_queue.append({
                'pin': pin,
                'wait_before': wait_before,
                'high_time': high_time,
                'wait_after': wait_after
            })
            
    def add_pin_state_command(self, pin, state, wait_before=0):
        """新增Pin狀態控制指令"""
        with self.lock:
            self.command_queue.append({
                'type': 'pin_state',
                'pin': pin,
                'state': state,
                'wait_before': wait_before
            })
            
    def add_esp32_pin_state_command(self, esp_name, esp_pin, state, wait_before=0):
        """🔥 新增：直接ESP32腳位狀態控制指令"""
        with self.lock:
            self.command_queue.append({
                'type': 'esp32_pin_state',
                'esp_name': esp_name,
                'esp_pin': esp_pin,
                'state': state,
                'wait_before': wait_before
            })
            
    def get_all_pin_states(self):
        """獲取所有ESP32的pin狀態"""
        return self.pin_states.copy()
        
    def get_connection_status(self):
        """獲取所有ESP32的連接狀態"""
        return self.connections.copy()
        
    def _disconnect_all(self):
        """斷開所有ESP32連接"""
        for esp_name in self.config.esp32_configs:
            self.connections[esp_name] = False
            self.connection_status_changed.emit(esp_name, False)
            
    def stop(self):
        """停止執行緒"""
        self.is_running = False
        self.wait()


class ESP32Controller(QObject):
    """ESP32 控制器（替代ArduinoController）"""
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.esp32_thread = None
        self.is_connected = False
        self.current_port = "TCP/IP"  # 兼容性
        self.pin_states = {}  # Arduino pin -> state mapping
        self.esp32_connections = {}  # ESP32連接狀態
        
        # 初始化Arduino pin狀態（兼容舊代碼）
        for pin in range(2, 14):
            self.pin_states[pin] = "LOW"
            
    def connect(self, port=None):
        """連接ESP32（port參數僅為兼容性保留）"""
        if self.esp32_thread and self.esp32_thread.isRunning():
            self.disconnect()
            
        self.esp32_thread = ESP32Thread()
        self.esp32_thread.status_changed.connect(self._on_status_changed)
        self.esp32_thread.error_occurred.connect(self._on_error)
        self.esp32_thread.pin_state_changed.connect(self._on_pin_state_changed)
        self.esp32_thread.connection_status_changed.connect(self._on_connection_status_changed)
        self.esp32_thread.start()
        
        self.is_connected = True
        
    def disconnect(self):
        """斷開連接"""
        if self.esp32_thread:
            self.esp32_thread.stop()
            self.esp32_thread = None
            
        self.is_connected = False
        
    def control_pin(self, pin, wait_before=0, high_time=1000, wait_after=0):
        """控制腳位（自動HIGH->LOW）"""
        if self.esp32_thread and self.esp32_thread.isRunning():
            self.esp32_thread.add_command(pin, wait_before, high_time, wait_after)
            
    def set_pin_state(self, pin, state, wait_before=0):
        """設置Arduino腳位狀態（兼容性方法）"""
        if self.esp32_thread and self.esp32_thread.isRunning():
            self.esp32_thread.add_pin_state_command(pin, state, wait_before)
        else:
            print(f"⚠️ ESP32線程未運行，無法設置腳位 {pin}")
        
    def set_esp32_pin_state(self, esp_name, esp_pin, state, wait_before=0):
        """🔥 新增：直接設置ESP32腳位狀態"""
        if not self.esp32_thread:
            print(f"⚠️ ESP32線程未初始化")
            return
            
        # 檢查ESP32是否存在
        if esp_name not in self.esp32_thread.config.esp32_configs:
            print(f"⚠️ ESP32 {esp_name} 不存在")
            return
            
        # 檢查腳位是否在ESP32的腳位列表中
        esp_config = self.esp32_thread.config.esp32_configs[esp_name]
        if esp_pin not in esp_config['pins']:
            print(f"⚠️ ESP32 {esp_name} 沒有腳位 {esp_pin}")
            return
            
        # 添加直接ESP32腳位控制命令
        self.esp32_thread.add_esp32_pin_state_command(esp_name, esp_pin, state, wait_before)
            
    def get_pin_state(self, pin):
        """獲取腳位狀態"""
        return self.pin_states.get(pin, "LOW")
        
    def get_esp32_pin_states(self):
        """獲取所有ESP32的實際pin狀態"""
        if self.esp32_thread:
            return self.esp32_thread.get_all_pin_states()
        return {}
        
    def get_esp32_connections(self):
        """獲取ESP32連接狀態"""
        return self.esp32_connections.copy()
        
    def is_esp32_connected(self, esp_name):
        """檢查特定ESP32是否連接"""
        return self.esp32_connections.get(esp_name, False)
        
    def _on_status_changed(self, status):
        """狀態變更"""
        self.status_changed.emit(status)
        
    def _on_error(self, error):
        """錯誤發生"""
        self.error_occurred.emit(error)
        
    def _on_pin_state_changed(self, esp_name, pin, state):
        """ESP32 pin狀態變更"""
        # 更新Arduino pin映射（用於兼容性）
        config = ESP32Config()
        for arduino_pin, (target_esp, target_pin) in config.weapon_pin_mapping.items():
            if target_esp == esp_name and target_pin == pin:
                self.pin_states[arduino_pin] = state
                break
                
    def _on_connection_status_changed(self, esp_name, is_connected):
        """ESP32連接狀態變更"""
        self.esp32_connections[esp_name] = is_connected
        
    def update_pin_state(self, pin, state):
        """更新pin狀態（兼容性方法）"""
        self.pin_states[pin] = state
        
    def test_all_connections(self):
        """測試所有ESP32連接狀態"""
        connections = {}
        config = ESP32Config()
        
        for esp_name in config.esp32_configs.keys():
            try:
                # 嘗試連接測試
                esp_config = config.esp32_configs[esp_name]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)  # 2秒超時
                
                result = sock.connect_ex((esp_config['ip'], esp_config['port']))
                connections[esp_name] = (result == 0)
                
                sock.close()
                
            except Exception as e:
                print(f"ESP32 {esp_name} 連接測試失敗: {e}")
                connections[esp_name] = False
                
        return connections