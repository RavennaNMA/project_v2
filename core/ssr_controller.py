# Location: project_v2/core/ssr_controller.py
# Usage: SSR 燈光控制器

import csv
import os
from PyQt6.QtCore import QThread, QObject, pyqtSignal


class SSRConfig:
    """SSR配置類"""
    
    def __init__(self):
        self.ssr1_pin = 12
        self.ssr2_pin = 13
        self.ssr1_delay_before = 0
        self.ssr2_delay_before = 0
        self.ssr1_high_time = 0  # 持續時間（0表示一直保持）
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
                            self.ssr1_pin = int(row['pin'])
                            self.ssr1_delay_before = int(row['delay_before'])
                            self.ssr1_high_time = int(row['high_time'])
                            self.ssr1_wait_after = int(row['wait_after'])
                        elif row['name'] == 'SSR2':
                            self.ssr2_pin = int(row['pin'])
                            self.ssr2_delay_before = int(row['delay_before'])
                            self.ssr2_high_time = int(row['high_time'])
                            self.ssr2_wait_after = int(row['wait_after'])
                            
                print(f"SSR設定載入：SSR1 Pin {self.ssr1_pin}, SSR2 Pin {self.ssr2_pin}")
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
                writer.writerow(['SSR1', 12, 0, 0, 0])
                writer.writerow(['SSR2', 13, 0, 0, 0])
            print("已創建預設 config/otherssr_config.csv")
        except Exception as e:
            print(f"創建預設配置時發生錯誤: {e}")


class SSRThread(QThread):
    """SSR控制執行緒"""
    
    status_changed = pyqtSignal(str)
    ssr1_ready = pyqtSignal()  # SSR1準備完成
    ssr2_ready = pyqtSignal()  # SSR2準備完成
    
    def __init__(self, arduino_controller, ssr_config):
        super().__init__()
        self.arduino = arduino_controller
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
        while not self.should_stop:
            # 檢查SSR1
            if self.ssr1_active and not self.ssr1_processed:
                print(f"Processing SSR1: Pin {self.config.ssr1_pin}")
                
                # 等待前延遲
                if self.config.ssr1_delay_before > 0:
                    self.status_changed.emit(f"SSR1等待前延遲 {self.config.ssr1_delay_before}ms")
                    self.msleep(self.config.ssr1_delay_before)
                
                # 設定為HIGH
                if self.arduino:
                    print(f"Setting SSR1 Pin {self.config.ssr1_pin} to HIGH")
                    self.arduino.set_pin_state(self.config.ssr1_pin, 'HIGH', 0)
                    self.status_changed.emit(f"SSR1 Pin {self.config.ssr1_pin} -> HIGH")
                else:
                    print("Warning: Arduino controller not available for SSR1")
                
                # 🔥 NEW: 等待後延遲（分離SSR1和字幕顯示）
                if self.config.ssr1_wait_after > 0:
                    print(f"SSR1 waiting {self.config.ssr1_wait_after}ms before triggering caption display...")
                    self.status_changed.emit(f"SSR1燈光已啟動，等待 {self.config.ssr1_wait_after}ms 後開始字幕顯示")
                    self.msleep(self.config.ssr1_wait_after)
                    print("SSR1 wait complete, ready to show captions")
                
                self.ssr1_processed = True
                self.ssr1_ready.emit()
            
            # 檢查SSR2
            if self.ssr2_active and not self.ssr2_processed:
                print(f"Processing SSR2: Pin {self.config.ssr2_pin}")
                
                # 等待前延遲
                if self.config.ssr2_delay_before > 0:
                    self.status_changed.emit(f"SSR2等待前延遲 {self.config.ssr2_delay_before}ms")
                    self.msleep(self.config.ssr2_delay_before)
                
                # 設定為HIGH
                if self.arduino:
                    print(f"Setting SSR2 Pin {self.config.ssr2_pin} to HIGH")
                    self.arduino.set_pin_state(self.config.ssr2_pin, 'HIGH', 0)
                    self.status_changed.emit(f"SSR2 Pin {self.config.ssr2_pin} -> HIGH")
                else:
                    print("Warning: Arduino controller not available for SSR2")
                    
                self.ssr2_processed = True
                self.ssr2_ready.emit()
                
            # 短暫休眠
            self.msleep(50)
            
        print("SSR thread ending")


class SSRController(QObject):
    """SSR控制器主類"""
    
    status_changed = pyqtSignal(str)
    spotlight_ready = pyqtSignal()
    caption_lighting_ready = pyqtSignal()
    
    def __init__(self, arduino_controller=None):
        super().__init__()
        self.arduino = arduino_controller
        self.config = SSRConfig()
        self.ssr_thread = None
        
    def start_caption_lighting(self):
        """開始字幕燈光（SSR1）"""
        print(f"Starting caption lighting: SSR1 Pin {self.config.ssr1_pin}")
        
        if self.ssr_thread and self.ssr_thread.isRunning():
            print("SSR thread already running, activating SSR1")
            self.ssr_thread.activate_ssr1()
            self.status_changed.emit("字幕燈光已啟動")
            return
            
        # 創建新線程
        print("Creating new SSR thread for caption lighting")
        self.ssr_thread = SSRThread(self.arduino, self.config)
        self.ssr_thread.status_changed.connect(self.on_status_changed)
        self.ssr_thread.ssr1_ready.connect(self.on_ssr1_ready)
        self.ssr_thread.ssr2_ready.connect(self.on_ssr2_ready)
        
        self.ssr_thread.activate_ssr1()
        self.ssr_thread.start()
        
        self.status_changed.emit("字幕燈光已啟動")
        
    def start_spotlight(self):
        """開始聚光燈（SSR2）"""
        print(f"Starting spotlight: SSR2 Pin {self.config.ssr2_pin}")
        
        if self.ssr_thread and self.ssr_thread.isRunning():
            print("SSR thread running, activating SSR2")
            self.ssr_thread.activate_ssr2()
            self.status_changed.emit("聚光燈已啟動")
        else:
            print("Creating new SSR thread for spotlight")
            self.ssr_thread = SSRThread(self.arduino, self.config)
            self.ssr_thread.status_changed.connect(self.on_status_changed)
            self.ssr_thread.ssr1_ready.connect(self.on_ssr1_ready)
            self.ssr_thread.ssr2_ready.connect(self.on_ssr2_ready)
            
            self.ssr_thread.activate_ssr2()
            self.ssr_thread.start()
            
    def stop_all_lighting(self):
        """停止所有燈光"""
        print("Stopping all SSR lighting")
        
        if self.arduino:
            if hasattr(self, 'ssr_thread') and self.ssr_thread:
                if self.ssr_thread.ssr1_processed:
                    print(f"Setting SSR1 Pin {self.config.ssr1_pin} to LOW")
                    self.arduino.set_pin_state(self.config.ssr1_pin, 'LOW', 0)
                    self.status_changed.emit(f"SSR1 Pin {self.config.ssr1_pin} -> LOW")
                
                if self.ssr_thread.ssr2_processed:
                    print(f"Setting SSR2 Pin {self.config.ssr2_pin} to LOW")
                    self.arduino.set_pin_state(self.config.ssr2_pin, 'LOW', 0)
                    self.status_changed.emit(f"SSR2 Pin {self.config.ssr2_pin} -> LOW")
        
        # 停止線程
        if self.ssr_thread and self.ssr_thread.isRunning():
            self.ssr_thread.should_stop = True
            self.ssr_thread.wait(1000)
            
        self.status_changed.emit("所有燈光已關閉")
            
    def on_status_changed(self, status):
        """狀態變更處理"""
        self.status_changed.emit(status)
        
    def on_ssr1_ready(self):
        """SSR1準備完成"""
        print("SSR1 (字幕燈光) 已啟動")
        self.caption_lighting_ready.emit()
        
    def on_ssr2_ready(self):
        """SSR2準備完成"""
        print("SSR2 (聚光燈) 已啟動")
        self.spotlight_ready.emit()
        
    def cleanup(self):
        """清理資源"""
        if self.ssr_thread and self.ssr_thread.isRunning():
            self.ssr_thread.deactivate_all()
            self.ssr_thread.wait(2000)
            
    def reload_config(self):
        """重新載入配置"""
        self.config.load_config()

    def get_ssr_status(self):
        """獲取當前SSR狀態"""
        status = {
            'thread_running': self.ssr_thread and self.ssr_thread.isRunning(),
            'ssr1_active': False,
            'ssr2_active': False,
            'ssr1_processed': False,
            'ssr2_processed': False
        }
        
        if self.ssr_thread:
            status['ssr1_active'] = self.ssr_thread.ssr1_active
            status['ssr2_active'] = self.ssr_thread.ssr2_active
            status['ssr1_processed'] = self.ssr_thread.ssr1_processed
            status['ssr2_processed'] = self.ssr_thread.ssr2_processed
            
        return status
        
    def print_debug_status(self):
        """列印調試狀態"""
        status = self.get_ssr_status()
        print("=== SSR Debug Status ===")
        print(f"SSR1 Pin: {self.config.ssr1_pin}")
        print(f"SSR2 Pin: {self.config.ssr2_pin}")
        print(f"Thread Running: {status['thread_running']}")
        print(f"SSR1 Active: {status['ssr1_active']}, Processed: {status['ssr1_processed']}")
        print(f"SSR2 Active: {status['ssr2_active']}, Processed: {status['ssr2_processed']}")
        print("========================") 