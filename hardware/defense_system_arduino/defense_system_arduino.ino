/*
  Defense System Arduino Controller
  防禦系統 Arduino 控制器
  
  功能：
  - 控制數位腳位 2-13 (武器 + SSR燈光)
  - 接收串口指令控制腳位狀態
  - 提供狀態指示和調試信息
  
  指令格式：
  - H{pin} : 設置指定腳位為 HIGH (例: H2, H13)
  - L{pin} : 設置指定腳位為 LOW  (例: L2, L13)
  
  腳位分配：
  - Pin 2-11: 武器控制 (鐵鎚、閃光燈、電磁模組等)
  - Pin 12-13: SSR燈光控制 (全亮燈、聚光燈)
  - Pin 13: 內建LED狀態指示
  
  作者: Defense System v2
  日期: 2024
*/

// 常數定義
const int MIN_CONTROL_PIN = 2;    // 最小控制腳位
const int MAX_CONTROL_PIN = 13;   // 最大控制腳位
const int LED_PIN = 13;           // 內建LED腳位
const int BAUD_RATE = 9600;       // 串口波特率
const int MAX_COMMAND_LENGTH = 10; // 最大指令長度

// 全域變數
String inputCommand = "";         // 接收的指令字串
bool commandComplete = false;     // 指令接收完成標記
unsigned long lastActivity = 0;  // 最後活動時間
bool systemReady = false;        // 系統就緒標記

// 腳位狀態追蹤 (用於調試)
bool pinStates[14] = {false};     // 腳位狀態陣列

void setup() {
  // 初始化串口通訊
  Serial.begin(BAUD_RATE);
  
  // 等待串口連接 (僅用於Leonardo/Micro)
  while (!Serial && millis() < 3000) {
    ; // 等待串口連接，最多3秒
  }
  
  // 初始化控制腳位
  initializePins();
  
  // 系統啟動指示
  systemStartupSequence();
  
  // 發送就緒信號
  Serial.println("Defense System Arduino Ready");
  Serial.println("Commands: H{pin} = HIGH, L{pin} = LOW");
  Serial.println("Pins: 2-13 available");
  Serial.println("===========================");
  
  systemReady = true;
  lastActivity = millis();
}

void loop() {
  // 檢查串口數據
  checkSerialInput();
  
  // 處理完整指令
  if (commandComplete) {
    processCommand();
    commandComplete = false;
  }
  
  // 狀態指示燈心跳
  updateStatusLED();
  
  // 延遲避免過度佔用CPU
  delay(1);
}

void initializePins() {
  // 設置所有控制腳位為輸出模式並初始化為LOW
  for (int pin = MIN_CONTROL_PIN; pin <= MAX_CONTROL_PIN; pin++) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, LOW);
    pinStates[pin] = false;
  }
  
  Serial.println("All pins initialized to LOW");
}

void systemStartupSequence() {
  // 啟動燈光序列 - 快速閃爍3次
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(100);
    digitalWrite(LED_PIN, LOW);
    delay(100);
  }
  
  // 短暫的測試序列 (可選)
  Serial.println("System startup sequence complete");
}

void checkSerialInput() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    
    // 更新活動時間
    lastActivity = millis();
    
    if (inChar == '\n' || inChar == '\r') {
      // 指令結束
      if (inputCommand.length() > 0) {
        commandComplete = true;
      }
    } else if (inputCommand.length() < MAX_COMMAND_LENGTH) {
      // 添加字符到指令字串
      inputCommand += inChar;
    } else {
      // 指令過長，重置
      Serial.println("ERROR: Command too long");
      inputCommand = "";
    }
  }
}

void processCommand() {
  inputCommand.trim(); // 移除空白字符
  
  if (inputCommand.length() < 2) {
    Serial.println("ERROR: Invalid command format");
    inputCommand = "";
    return;
  }
  
  // 解析指令格式: H{pin} 或 L{pin}
  char action = inputCommand.charAt(0);
  String pinString = inputCommand.substring(1);
  int pin = pinString.toInt();
  
  // 驗證指令
  if ((action != 'H' && action != 'h' && action != 'L' && action != 'l') ||
      pin < MIN_CONTROL_PIN || pin > MAX_CONTROL_PIN) {
    Serial.println("ERROR: Invalid command - " + inputCommand);
    Serial.println("Valid format: H{2-13} or L{2-13}");
    inputCommand = "";
    return;
  }
  
  // 執行指令
  bool newState = (action == 'H' || action == 'h');
  digitalWrite(pin, newState ? HIGH : LOW);
  pinStates[pin] = newState;
  
  // 發送確認信息
  Serial.println("PIN " + String(pin) + " -> " + (newState ? "HIGH" : "LOW"));
  
  // 特殊處理：如果是pin 13，同時作為狀態指示
  if (pin == LED_PIN) {
    Serial.println("LED status updated");
  }
  
  // 清除指令
  inputCommand = "";
}

void updateStatusLED() {
  static unsigned long lastHeartbeat = 0;
  static bool heartbeatState = false;
  
  // 如果pin 13被外部控制，跳過心跳
  if (pinStates[LED_PIN]) {
    return;
  }
  
  // 心跳間隔：系統正常時慢閃，無活動時快閃
  unsigned long heartbeatInterval;
  if (millis() - lastActivity < 5000) {
    heartbeatInterval = 1000; // 1秒慢閃 - 正常狀態
  } else {
    heartbeatInterval = 200;  // 0.2秒快閃 - 待機狀態
  }
  
  if (millis() - lastHeartbeat >= heartbeatInterval) {
    heartbeatState = !heartbeatState;
    digitalWrite(LED_PIN, heartbeatState);
    lastHeartbeat = millis();
  }
}

// 調試函數：列印所有腳位狀態
void printPinStates() {
  Serial.println("=== Pin States ===");
  for (int pin = MIN_CONTROL_PIN; pin <= MAX_CONTROL_PIN; pin++) {
    Serial.println("Pin " + String(pin) + ": " + (pinStates[pin] ? "HIGH" : "LOW"));
  }
  Serial.println("==================");
}

// 應急停止：設置所有腳位為LOW
void emergencyStop() {
  for (int pin = MIN_CONTROL_PIN; pin <= MAX_CONTROL_PIN; pin++) {
    digitalWrite(pin, LOW);
    pinStates[pin] = false;
  }
  Serial.println("EMERGENCY STOP: All pins set to LOW");
}

// 測試序列：依次激活所有腳位
void testSequence() {
  Serial.println("Starting test sequence...");
  
  for (int pin = MIN_CONTROL_PIN; pin <= MAX_CONTROL_PIN; pin++) {
    Serial.println("Testing Pin " + String(pin));
    digitalWrite(pin, HIGH);
    delay(500);
    digitalWrite(pin, LOW);
    delay(200);
  }
  
  Serial.println("Test sequence complete");
}

/*
  使用說明：
  
  1. 將此程序燒錄到Arduino Uno/Nano/Pro Mini
  2. 設置串口波特率為9600
  3. 連接設備到腳位2-13
  4. 發送指令控制腳位：
     - H2  -> Pin 2 HIGH (鐵鎚)
     - L2  -> Pin 2 LOW
     - H13 -> Pin 13 HIGH (SSR2/LED)
     - L13 -> Pin 13 LOW
  
  狀態指示：
  - LED慢閃：系統正常，最近有活動
  - LED快閃：系統待機，無近期活動
  - LED常亮：Pin 13被外部控制為HIGH
  
  故障排除：
  - 如果無回應，檢查串口連接和波特率
  - 如果指令無效，檢查格式（H/L + 數字2-13）
  - 緊急情況下重啟Arduino將所有腳位復位為LOW
*/ 