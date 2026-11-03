#include <WiFi.h>
#include <Wire.h>

// ============================================================
// ESP32-C3 Super Mini + MPU6050 + Wi-Fi TCP Server
// SSID     : ESP32-C3-MPU6050
// Password : mpu6050wifi
// IP       : 192.168.4.1
// TCP Port : 3333
// Output   : ax,ay,az,gx,gy,gz   (m/s^2 , rad/s , 20Hz)
// ============================================================

// -------------------- I2C pins --------------------
const uint8_t SDA_PIN = 8;
const uint8_t SCL_PIN = 9;

// -------------------- Wi-Fi AP / TCP --------------------
const char* AP_SSID     = "ESP32-C3-MPU6050";
const char* AP_PASSWORD = "mpu6050wifi";

const uint16_t TCP_PORT             = 3333;
const uint8_t  AP_CHANNEL           = 6;
const uint8_t  MAX_AP_CONNECTIONS   = 4;

IPAddress AP_IP(192, 168, 4, 1);
IPAddress AP_GATEWAY(192, 168, 4, 1);
IPAddress AP_SUBNET(255, 255, 255, 0);

// -------------------- Sampling --------------------
const uint32_t OUTPUT_RATE_HZ   = 20;
const uint32_t SAMPLE_PERIOD_US = 1000000UL / OUTPUT_RATE_HZ;
const uint8_t  SAMPLE_RATE_DIVIDER = 49;

// -------------------- MPU6050 conversion --------------------
const float ACCEL_LSB_PER_G    = 16384.0f;
const float GYRO_LSB_PER_DPS   = 131.0f;
const float GRAVITY_MS2        = 9.80665f;
const float DEG_TO_RAD_VALUE   = 0.017453292519943295f;

// -------------------- Global objects --------------------
WiFiServer server(TCP_PORT);
WiFiClient client;

uint8_t  mpuAddress        = 0;
uint32_t lastSampleTimeUs  = 0;

// ============================================================
uint8_t findMPU6050()
{
  for (uint8_t a = 0x68; a <= 0x69; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) return a;
  }
  return 0;
}

bool writeRegister(uint8_t reg, uint8_t value)
{
  Wire.beginTransmission(mpuAddress);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readRegisters(uint8_t reg, uint8_t* buffer, uint8_t length)
{
  Wire.beginTransmission(mpuAddress);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;

  uint8_t received = Wire.requestFrom(mpuAddress, length, true);
  if (received != length) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (uint8_t i = 0; i < length; i++) {
    if (!Wire.available()) {
      while (Wire.available()) Wire.read();
      return false;
    }
    buffer[i] = Wire.read();
  }
  return true;
}

bool configureMPU6050()
{
  if (!writeRegister(0x6B, 0x00)) return false;   // wake
  if (!writeRegister(0x1A, 0x03)) return false;   // DLPF_CFG=3
  if (!writeRegister(0x1B, 0x00)) return false;   // Gyro ±250
  if (!writeRegister(0x1C, 0x00)) return false;   // Accel ±2g
  if (!writeRegister(0x19, SAMPLE_RATE_DIVIDER)) return false;
  return true;
}

void sendHeader()
{
  client.print("ax,ay,az,gx,gy,gz\r\n");
}

void disconnectClient()
{
  if (client) client.stop();
  lastSampleTimeUs = 0;
}

void acceptClientIfAvailable()
{
  WiFiClient incoming = server.available();
  if (!incoming) return;

  if (client && client.connected()) client.stop();

  client = incoming;
  client.setNoDelay(true);
  lastSampleTimeUs = 0;
  sendHeader();

  Serial.print("TCP client connected: ");
  Serial.println(client.remoteIP());
}

// ============================================================
// Wi-Fi AP — فقط این تابع اصلاح شد
// ============================================================
bool startWiFiAccessPoint()
{
  Serial.println();
  Serial.println("Starting Wi-Fi Access Point...");

  WiFi.persistent(false);

  // 1) ریست رادیو
  WiFi.mode(WIFI_MODE_NULL);
  delay(300);

  // 2) ورود به حالت AP
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);

  // 3) 🔑 تنها تنظیم TX Power، بعد از mode(AP)
  //    SuperMini فقط با توان پایین درست پخش می‌کند
  WiFi.setTxPower(WIFI_POWER_8_5dBm);

  bool configOK = WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET);
  Serial.print("softAPConfig: ");
  Serial.println(configOK ? "OK" : "FAILED");
  if (!configOK) return false;

  bool apOK = WiFi.softAP(
    AP_SSID, AP_PASSWORD, AP_CHANNEL, false, MAX_AP_CONNECTIONS
  );
  Serial.print("softAP: ");
  Serial.println(apOK ? "OK" : "FAILED");
  if (!apOK) return false;

  delay(1000);

  Serial.println();
  Serial.println("Wi-Fi Access Point started successfully");
  Serial.print("SSID: ");     Serial.println(WiFi.softAPSSID());
  Serial.print("Password: "); Serial.println(AP_PASSWORD);
  Serial.print("Channel: ");  Serial.println(AP_CHANNEL);
  Serial.print("IP: ");       Serial.println(WiFi.softAPIP());
  Serial.print("MAC: ");      Serial.println(WiFi.softAPmacAddress());
  Serial.print("Stations: "); Serial.println(WiFi.softAPgetStationNum());

  return true;
}

// ============================================================
void setup()
{
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("Starting ESP32-C3 MPU6050 server...");
  Serial.print("I2C SDA: GPIO"); Serial.println(SDA_PIN);
  Serial.print("I2C SCL: GPIO"); Serial.println(SCL_PIN);

  Wire.begin(SDA_PIN, SCL_PIN, 400000);
  delay(100);

  mpuAddress = findMPU6050();
  if (mpuAddress == 0) {
    Serial.println("ERROR: MPU6050 not found");
    while (true) delay(1000);
  }
  Serial.print("MPU6050 address: 0x");
  Serial.println(mpuAddress, HEX);

  if (!configureMPU6050()) {
    Serial.println("ERROR: MPU6050 configuration failed");
    while (true) delay(1000);
  }
  Serial.println("MPU6050 configured successfully");

  if (!startWiFiAccessPoint()) {
    Serial.println();
    Serial.println("ERROR: Wi-Fi Access Point failed");
    while (true) delay(1000);
  }

  server.begin();
  server.setNoDelay(true);

  Serial.print("TCP port: "); Serial.println(TCP_PORT);
  Serial.println("Waiting for TCP client...");
}

// ============================================================
void loop()
{
  if (client && !client.connected()) {
    Serial.println("TCP client disconnected");
    disconnectClient();
  }

  acceptClientIfAvailable();

  if (!client || !client.connected()) {
    delay(2);
    return;
  }

  uint32_t nowUs = micros();
  if (lastSampleTimeUs == 0) { lastSampleTimeUs = nowUs; return; }

  if ((uint32_t)(nowUs - lastSampleTimeUs) < SAMPLE_PERIOD_US) return;
  lastSampleTimeUs = nowUs;

  uint8_t data[14];
  if (!readRegisters(0x3B, data, 14)) {
    Serial.println("ERROR: MPU6050 read failed");
    return;
  }

  int16_t axRaw = (int16_t)(((uint16_t)data[0]  << 8) | data[1]);
  int16_t ayRaw = (int16_t)(((uint16_t)data[2]  << 8) | data[3]);
  int16_t azRaw = (int16_t)(((uint16_t)data[4]  << 8) | data[5]);
  int16_t gxRaw = (int16_t)(((uint16_t)data[8]  << 8) | data[9]);
  int16_t gyRaw = (int16_t)(((uint16_t)data[10] << 8) | data[11]);
  int16_t gzRaw = (int16_t)(((uint16_t)data[12] << 8) | data[13]);

  float ax = (axRaw / ACCEL_LSB_PER_G)  * GRAVITY_MS2;
  float ay = (ayRaw / ACCEL_LSB_PER_G)  * GRAVITY_MS2;
  float az = (azRaw / ACCEL_LSB_PER_G)  * GRAVITY_MS2;

  float gx = (gxRaw / GYRO_LSB_PER_DPS) * DEG_TO_RAD_VALUE;
  float gy = (gyRaw / GYRO_LSB_PER_DPS) * DEG_TO_RAD_VALUE;
  float gz = (gzRaw / GYRO_LSB_PER_DPS) * DEG_TO_RAD_VALUE;

  char line[128];
  snprintf(line, sizeof(line),
           "%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\r\n",
           ax, ay, az, gx, gy, gz);

  size_t sent = client.print(line);
  if (sent == 0) {
    Serial.println("TCP send failed");
    disconnectClient();
  }
}