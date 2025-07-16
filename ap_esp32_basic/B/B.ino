#include <WiFi.h>

// Network settings
const char* ssid = "system_esp32";
const char* password = "2468xXxX";
const int port = 8080;

// Pin configuration for ESP32 B
int controlPins[] = {4, 5, 12};
int numPins = sizeof(controlPins) / sizeof(controlPins[0]);

WiFiServer server(port);
WiFiClient client;

void setup() {
  Serial.begin(115200);
  
  // Initialize pins as outputs and set to LOW
  for (int i = 0; i < numPins; i++) {
    pinMode(controlPins[i], OUTPUT);
    digitalWrite(controlPins[i], LOW);
  }
  
  // Connect to WiFi with static IP
  WiFi.config(IPAddress(192, 168, 0, 102), IPAddress(192, 168, 0, 1), IPAddress(255, 255, 255, 0));
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  
  server.begin();
  Serial.println("ESP32 B Server started");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  client = server.available();
  
  if (client) {
    while (client.connected()) {
      if (client.available()) {
        String request = client.readStringUntil('\n');
        request.trim();
        
        String response = processRequest(request);
        client.println(response);
        client.flush();
      }
    }
    client.stop();
  }
}

String processRequest(String request) {
  if (request == "STATUS") {
    return "ESP32_B_ONLINE";
  }
  else if (request == "GET_PINS") {
    String pinStates = "B:";
    for (int i = 0; i < numPins; i++) {
      pinStates += String(controlPins[i]) + "=" + String(digitalRead(controlPins[i]));
      if (i < numPins - 1) pinStates += ",";
    }
    return pinStates;
  }
  else if (request.startsWith("SET:")) {
    // Format: SET:pin,value
    String params = request.substring(4);
    int commaIndex = params.indexOf(',');
    
    if (commaIndex > 0) {
      int pin = params.substring(0, commaIndex).toInt();
      int value = params.substring(commaIndex + 1).toInt();
      
      // Check if pin is in control list
      bool validPin = false;
      for (int i = 0; i < numPins; i++) {
        if (controlPins[i] == pin) {
          validPin = true;
          break;
        }
      }
      
      if (validPin && (value == 0 || value == 1)) {
        digitalWrite(pin, value);
        return "B:SET_PIN_" + String(pin) + "_TO_" + String(value);
      }
    }
    return "B:ERROR_INVALID_COMMAND";
  }
  
  return "B:ERROR_UNKNOWN_COMMAND";
}