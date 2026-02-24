# Location: project_v2/core/osc_controller.py
# Usage: OSC通訊控制器 - 改良版本，使用新的訊息格式

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from pythonosc import dispatcher, osc_server, udp_client
import threading
import time
import gc


class OSCConfig:
    """OSC配置"""
    # A電腦（本系統）
    A_IP = "192.168.0.62"
    A_PORT = 7000
    
    # B電腦（發送robot指令）
    B_IP = "10.254.26.146"
    B_PORT = 7001
    
    # C電腦（接收燈光控制）
    C_IP = "127.0.0.1"
    C_PORT = 7002


class OSCThread(QThread):
    """OSC接收執行緒"""
    robot_arrive = pyqtSignal()
    message_received = pyqtSignal(str, list)
    
    def __init__(self, ip, port):
        super().__init__()
        self.ip = ip
        self.port = port
        self.server = None
        self.running = False
        
    def run(self):
        """執行OSC伺服器"""
        self.running = True
        
        # 設定dispatcher
        disp = dispatcher.Dispatcher()
        disp.map("/robotarrive", self.handle_robot_arrive)
        disp.set_default_handler(self.handle_default)
        
        # 建立伺服器
        try:
            self.server = osc_server.ThreadingOSCUDPServer(
                (self.ip, self.port), disp
            )
            print(f"OSC Server listening on {self.ip}:{self.port}")
            self.server.serve_forever()
        except Exception as e:
            print(f"OSC Server error: {e}")
        finally:
            # 釋放記憶體
            gc.collect()
            
    def handle_robot_arrive(self, address, *args):
        """處理機器人到達訊息"""
        print(f"Received OSC: {address} with args: {args}")
        self.robot_arrive.emit()
        
    def handle_default(self, address, *args):
        """處理其他訊息"""
        print(f"Received OSC: {address} with args: {args}")
        self.message_received.emit(address, list(args))
        
    def stop(self):
        """停止伺服器"""
        self.running = False
        if self.server:
            self.server.shutdown()
            

class OSCController(QObject):
    """OSC控制器 - 改良版本"""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.config = OSCConfig()
        
        # OSC客戶端（發送）
        self.client_c = udp_client.SimpleUDPClient(
            self.config.C_IP, 
            self.config.C_PORT
        )
        
        # OSC伺服器執行緒（接收）
        self.server_thread = OSCThread(
            self.config.A_IP,
            self.config.A_PORT
        )
        self.server_thread.robot_arrive.connect(self.on_robot_arrive)
        self.server_thread.message_received.connect(self.on_message_received)
        
    def start(self):
        """啟動OSC服務"""
        self.server_thread.start()
        print(f"OSC Controller started")
        print(f"  A (本機): {self.config.A_IP}:{self.config.A_PORT}")
        print(f"  B (Robot): {self.config.B_IP}:{self.config.B_PORT}")
        print(f"  C (燈光): {self.config.C_IP}:{self.config.C_PORT}")
        
    def stop(self):
        """停止OSC服務"""
        if self.server_thread.isRunning():
            self.server_thread.stop()
            self.server_thread.wait(2000)
        print("OSC Controller stopped")
        # 釋放記憶體
        gc.collect()
        
    def on_robot_arrive(self):
        """處理機器人到達事件"""
        print("OSC: Robot arrived!")
        if hasattr(self.main_window, 'on_robot_arrive'):
            self.main_window.on_robot_arrive()
            
    def on_message_received(self, address, args):
        """處理其他OSC訊息"""
        print(f"OSC message: {address} = {args}")
        
    def send_light_command(self, light_num, state):
        """發送燈光控制命令 - 使用新格式
        
        新格式: /light <num> <state>
        例如: /light 1 1 (開啟第1盞燈)
             /light 1 0 (關閉第1盞燈)
        
        Args:
            light_num: 燈光編號 1-13
            state: True=開燈(1), False=關燈(0)
        """
        if 1 <= light_num <= 13:
            # 使用新的訊息格式
            state_value = 1 if state else 0
            command = "/light"
            args = [light_num, state_value]
            
            try:
                self.client_c.send_message(command, args)
                print(f"OSC sent to C: {command} {light_num} {state_value}")
            except Exception as e:
                print(f"OSC send error: {e}")
                
    def send_all_lights_on(self):
        """開啟所有燈光"""
        for i in range(1, 14):
            self.send_light_command(i, True)
            time.sleep(0.01)  # 避免訊息過快
            
    def send_all_lights_off(self):
        """關閉所有燈光"""
        for i in range(1, 14):
            self.send_light_command(i, False)
            time.sleep(0.01)
            
    def get_status(self):
        """取得OSC狀態"""
        return f"{self.config.A_IP}:{self.config.A_PORT}"

