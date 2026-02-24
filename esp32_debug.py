
import socket
import time


class ESP32Controller:
    def __init__(self):
        self.esp32_configs = {
            'A': {'ip': '192.168.0.101', 'pins': [4, 5, 12, 13, 14, 16, 17, 18, 19, 21]},
            'B': {'ip': '192.168.0.102', 'pins': [4, 5, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25]},
            'C': {'ip': '192.168.0.103', 'pins': [4]}
        }
        self.port = 8080
        self.timeout = 5
   
    def send_command(self, esp_name, command): 
        """Send command to ESP32 and return response"""
        try:
            ip = self.esp32_configs[esp_name]['ip']
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((ip, self.port))
           
            sock.send((command + '\n').encode())
            response = sock.recv(1024).decode().strip()
            sock.close()
            return response
        except Exception as e:
            return f"ERROR: {str(e)}"
   
    def check_connections(self):
        """Check which ESP32s are online"""
        print("\n=== ESP32 Connection Status ===")
        for esp_name in self.esp32_configs:
            response = self.send_command(esp_name, "STATUS")
            if "ONLINE" in response:
                print(f"ESP32 {esp_name}: CONNECTED ({self.esp32_configs[esp_name]['ip']})")
            else:
                print(f"ESP32 {esp_name}: DISCONNECTED ({response})")
   
    def get_pin_states(self):
        """Get current pin states from all ESP32"""
        print("\n=== Pin States ===")
        for esp_name in self.esp32_configs:
            response = self.send_command(esp_name, "GET_PINS")
            if response.startswith(esp_name + ":"):
                pin_data = response.split(":")[1]
                if pin_data:
                    pins = pin_data.split(",")
                    print(f"ESP32 {esp_name}:")
                    for pin in pins:
                        pin_num, state = pin.split("=")
                        state_text = "HIGH" if state == "1" else "LOW"
                        print(f"  Pin {pin_num}: {state_text}")
                else:
                    print(f"ESP32 {esp_name}: No pin data")
            else:
                print(f"ESP32 {esp_name}: ERROR - {response}")
   
    def show_control_options(self):
        """Show available controls and handle user input"""
        print("\n=== Control Options ===")
        print("Available ESP32s and pins:")
        for esp_name, config in self.esp32_configs.items():
            pins_str = ", ".join(map(str, config['pins']))
            print(f"ESP32 {esp_name}: pins [{pins_str}]")
       
        print("\nFormat: ESP_NAME,PIN,VALUE")
        print("Example: A,4,1 (set ESP32 A pin 4 to HIGH)")
        print("Example: B,12,0 (set ESP32 B pin 12 to LOW)")
        print("Type 'back' to return to main menu")
       
        while True:
            user_input = input("\nEnter command: ").strip()
           
            if user_input.lower() == 'back':
                break
           
            if self.process_control_command(user_input):
                continue
            else:
                print("Invalid format. Use: ESP_NAME,PIN,VALUE")
   
    def process_control_command(self, command):
        """Process control command like A,4,1"""
        try:
            parts = command.split(',')
            if len(parts) != 3:
                return False
           
            esp_name = parts[0].upper().strip()
            pin = int(parts[1].strip())
            value = int(parts[2].strip())
           
            # Validate ESP name
            if esp_name not in self.esp32_configs:
                print(f"ERROR: ESP32 {esp_name} not found")
                return True
           
            # Validate pin
            if pin not in self.esp32_configs[esp_name]['pins']:
                available_pins = ", ".join(map(str, self.esp32_configs[esp_name]['pins']))
                print(f"ERROR: Pin {pin} not available on ESP32 {esp_name}")
                print(f"Available pins: {available_pins}")
                return True
           
            # Validate value
            if value not in [0, 1]:
                print("ERROR: Value must be 0 or 1")
                return True
           
            # Send command
            response = self.send_command(esp_name, f"SET:{pin},{value}")
            if "SET_PIN" in response:
                state_text = "HIGH" if value == 1 else "LOW"
                print(f"SUCCESS: ESP32 {esp_name} pin {pin} set to {state_text}")
            else:
                print(f"ERROR: {response}")
           
            return True
           
        except ValueError:
            return False
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return True
   
    def run(self):
        """Main program loop"""
        print("ESP32 Test")
       
        while True:
            print("\nOptions:")
            print("1. Check ESP32 connections")
            print("2. Show pin states")
            print("3. Control pins")
            print("0. Exit")
           
            choice = input("\nEnter choice: ").strip()
           
            if choice == '1':
                self.check_connections()
            elif choice == '2':
                self.get_pin_states()
            elif choice == '3':
                self.show_control_options()
            elif choice == '0':
                print("Goodbye!")
                break
            else:
                print("Invalid choice. Please enter 0-3.")


if __name__ == "__main__":
    controller = ESP32Controller()
    controller.run()
