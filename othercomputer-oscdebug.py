#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSC Debug Tool
用於測試OSC通訊的調試工具
"""


import sys
import time
import threading
import socket
from pythonosc import dispatcher, osc_server, udp_client




class OSCDebugTool:
    def __init__(self):
        # 系統配置（與主系統一致）
        self.A_IP = "10.254.26.213"  # A電腦（主系統）
        self.A_PORT = 7000
       
        self.B_IP = "10.254.26.146"  # B電腦（發送robot）
        self.B_PORT = 7001
       
        self.C_IP = "10.254.26.144"  # C電腦（接收燈光）
        self.C_PORT = 7002
       
        self.running = False
        self.server = None
        self.mode = None
        
    def get_local_ip(self):
        """取得本機IP地址"""
        try:
            # 建立一個UDP socket連接到外部地址以取得本機IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "無法取得IP"
       
    def start_mode_b(self):
        """模式B：模擬B電腦發送機器人訊號"""
        print(f"\n=== 模式B：模擬機器人控制端 ===")
        print(f"將從 {self.B_IP}:{self.B_PORT} 發送OSC到 A系統 {self.A_IP}:{self.A_PORT}")
       
        # 建立客戶端
        client = udp_client.SimpleUDPClient(self.A_IP, self.A_PORT)
       
        print("\n按Enter發送 /robotarrive 訊號，輸入'q'退出")
       
        while True:
            user_input = input("> ")
           
            if user_input.lower() == 'q':
                print("退出模式B")
                break
            elif user_input == '':
                # 發送機器人到達訊號
                client.send_message("/robotarrive", [])
                print(f"已發送: /robotarrive 到 {self.A_IP}:{self.A_PORT}")
                print(f"時間戳記: {time.strftime('%H:%M:%S')}")
            else:
                print("無效輸入。按Enter發送訊號，輸入'q'退出")
               
    def start_mode_c(self):
        """模式C：模擬C電腦接收燈光控制"""
        local_ip = self.get_local_ip()
        
        print(f"\n=== 模式C：模擬燈光控制接收端 ===")
        print(f"本機IP地址: {local_ip}")
        print(f"監聽端口: {self.C_PORT}")
        print(f"綁定所有網路介面 (0.0.0.0:{self.C_PORT})")
        print(f"\n⚠️  重要提醒：")
        print(f"請確認A系統 (osc_controller.py) 中的 C_IP 設定為: {local_ip}")
        print(f"目前A系統配置的C_IP: {self.C_IP}")
        if local_ip != self.C_IP and local_ip != "無法取得IP":
            print(f"🔥 IP不匹配！請更新A系統的配置")
        print(f"----------")
       
        # 設定dispatcher
        disp = dispatcher.Dispatcher()
       
        # 註冊所有燈光控制處理器
        for i in range(1, 14):
            disp.map(f"/lighton{i:02d}", self.handle_light_on)
            disp.map(f"/lightoff{i:02d}", self.handle_light_off)
           
        disp.set_default_handler(self.handle_default)
       
        # 建立伺服器
        try:
            # 使用 0.0.0.0 綁定所有網路介面，這樣可以接收來自任何IP的訊息
            self.server = osc_server.ThreadingOSCUDPServer(
                ("0.0.0.0", self.C_PORT), disp
            )
           
            print(f"OSC Server 啟動於 0.0.0.0:{self.C_PORT}")
            print(f"可接收來自任何IP的OSC訊息")
            print(f"預期A系統將發送到: [此電腦實際IP]:{self.C_PORT}")
            print("等待接收燈光控制指令...")
            print("按Ctrl+C退出\n")
           
            # 在新執行緒中運行伺服器
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
           
            # 主執行緒等待用戶輸入
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n停止伺服器...")
                self.server.shutdown()
               
        except Exception as e:
            print(f"OSC Server 錯誤: {e}")
           
    def handle_light_on(self, address, *args):
        """處理開燈指令"""
        timestamp = time.strftime('%H:%M:%S')
        
        # 從OSC地址解析燈光編號 (例如: /lighton01 -> 1)
        try:
            light_num = int(address[-2:])  # 取最後兩位數字
        except ValueError:
            print(f"[{timestamp}] 無法解析燈光編號: {address}")
            return
       
        # 顯示燈光狀態
        light_name = self.get_light_name(light_num)
        print(f"[{timestamp}] 燈光 {light_num:02d} ({light_name}) >>> 開啟 [ON]")
       
        # 顯示視覺化狀態
        self.display_light_status(light_num, True)
       
    def handle_light_off(self, address, *args):
        """處理關燈指令"""
        timestamp = time.strftime('%H:%M:%S')
        
        # 從OSC地址解析燈光編號 (例如: /lightoff01 -> 1)
        try:
            light_num = int(address[-2:])  # 取最後兩位數字
        except ValueError:
            print(f"[{timestamp}] 無法解析燈光編號: {address}")
            return
       
        # 顯示燈光狀態
        light_name = self.get_light_name(light_num)
        print(f"[{timestamp}] 燈光 {light_num:02d} ({light_name}) <<< 關閉 [OFF]")
       
        # 顯示視覺化狀態
        self.display_light_status(light_num, False)
       
    def handle_default(self, address, *args):
        """處理其他訊息"""
        timestamp = time.strftime('%H:%M:%S')
        print(f"[{timestamp}] 收到OSC訊息: {address}")
        if args:
            print(f"           參數: {args}")
        print(f"           來源: 來自A系統的訊息")
       
    def get_light_name(self, light_num):
        """取得燈光名稱"""
        names = {
            1: "武器1", 2: "武器2", 3: "武器3", 4: "武器4", 5: "武器5",
            6: "武器6", 7: "武器7", 8: "武器8", 9: "武器9", 10: "武器10",
            11: "聚光燈", 12: "安裝SSR", 13: "牆壁燈"
        }
        return names.get(light_num, f"燈光{light_num}")
       
    def display_light_status(self, light_num, is_on):
        """顯示視覺化燈光狀態"""
        status_line = "狀態: "
        for i in range(1, 14):
            if i == light_num:
                if is_on:
                    status_line += f"[{i:02d}:●] "
                else:
                    status_line += f"[{i:02d}:○] "
            else:
                status_line += f"[{i:02d}:─] "
        print(status_line)
        print("-" * 80)
       
    def run(self):
        """主程式"""
        print("=" * 80)
        print("OSC Debug Tool - 系統測試工具")
        print("=" * 80)
        
        # 顯示本機網路資訊
        local_ip = self.get_local_ip()
        print(f"\n本機資訊：")
        print(f"  本機IP: {local_ip}")
        
        print("\n網路配置：")
        print(f"  A系統（主控）: {self.A_IP}:{self.A_PORT}")
        print(f"  B電腦（機器人）: {self.B_IP}:{self.B_PORT}")
        print(f"  C電腦（燈光）: {self.C_IP}:{self.C_PORT}")
        
        # IP匹配檢查
        if local_ip != "無法取得IP":
            if local_ip == self.A_IP:
                print(f"✅ 本機是A系統主控端")
            elif local_ip == self.B_IP:
                print(f"✅ 本機是B電腦機器人端")
            elif local_ip == self.C_IP:
                print(f"✅ 本機是C電腦燈光端")
            else:
                print(f"⚠️  本機IP ({local_ip}) 不在預定義配置中")
        
        print("\n選擇模式：")
        print("  1 - 模擬B電腦（發送機器人訊號到A系統）")
        print("  2 - 模擬C電腦（接收來自A系統的燈光控制）")
        print("  q - 退出")
       
        while True:
            choice = input("\n請選擇 (1/2/q): ").strip()
           
            if choice == '1':
                self.start_mode_b()
            elif choice == '2':
                self.start_mode_c()
            elif choice.lower() == 'q':
                print("退出程式")
                break
            else:
                print("無效選擇，請重新輸入")




if __name__ == "__main__":
    tool = OSCDebugTool()
   
    try:
        tool.run()
    except KeyboardInterrupt:
        print("\n\n程式中斷")
    except Exception as e:
        print(f"\n錯誤: {e}")
    finally:
        print("程式結束")
        sys.exit(0)

