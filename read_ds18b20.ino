#include <Adafruit_NeoPixel.h>
#include <DallasTemperature.h>
#include <OneWire.h>

#define LED_PIN    PIN_NEOPIXEL
#define LED_COUNT  1

#define ONE_WIRE_PIN A0   // Data pin connected to DS18B20
#define FRIENDLY_FORMAT false

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature sensors(&oneWire);
Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

DeviceAddress tempDeviceAddress;

void setup() {
  //pinMode(NEOPIXEL_POWER, OUTPUT);
  digitalWrite(NEOPIXEL_POWER, LOW);

  //pixels.begin();
  //pixels.setBrightness(50);        // optional, 0–255
  pixels.clear();


  // Set pixel 0 to GREEN: (R, G, B)
  //pixels.setPixelColor(0, pixels.Color(0, 50, 0));
  pixels.show();

  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Serial.println("DS18B20 Test on QT Py RP2040");

  sensors.begin();
  int deviceCount = sensors.getDeviceCount();

  // Don't lock up if the DS18B20 isn't wired in yet — keep retrying and
  // emit a periodic ERROR line so the host can distinguish "no sensor"
  // from "no board" (both look like silence otherwise).
  while (deviceCount == 0) {
    Serial.println("ERROR: No DS18B20 detected");
    delay(1000);
    sensors.begin();
    deviceCount = sensors.getDeviceCount();
  }

  Serial.print("Found ");
  Serial.print(deviceCount);
  Serial.println(" DS18B20 device(s).");

  // Get address of first sensor
  sensors.getAddress(tempDeviceAddress, 0);
  Serial.print("Sensor address: ");
  for (uint8_t i = 0; i < 8; i++) {
    Serial.print(tempDeviceAddress[i], HEX);
    Serial.print(" ");
  }
  Serial.println();

  sensors.setResolution(tempDeviceAddress, 12); // highest precision
}

void loop() {
  sensors.requestTemperatures(); // tell sensor to perform conversion
  float tempC = sensors.getTempCByIndex(0);

  // Runtime disconnect: DallasTemperature returns DEVICE_DISCONNECTED_C
  // (-127.0) if the sensor stops responding. Surface that as an ERROR
  // line instead of printing -127 as if it were a real reading, and try
  // to rediscover the sensor in case the wire was just bumped.
  if (tempC == DEVICE_DISCONNECTED_C) {
    Serial.println("ERROR: DS18B20 disconnected");
    sensors.begin();
    if (sensors.getDeviceCount() > 0) {
      sensors.getAddress(tempDeviceAddress, 0);
      sensors.setResolution(tempDeviceAddress, 12);
    }
    delay(1000);
    return;
  }

  if(FRIENDLY_FORMAT)
  {
    Serial.print("Temperature: ");
    Serial.print(tempC);
    Serial.println(" C");
  }
  else
  {
    unsigned long ms = millis();
    Serial.print(ms);
    Serial.print(", ");
    Serial.println(tempC, 2);
  }
 
  delay(1000);
}