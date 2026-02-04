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
  Serial.print("Found ");
  Serial.print(deviceCount);
  Serial.println(" DS18B20 device(s).");

  if (deviceCount == 0) {
    Serial.println("ERROR: No DS18B20 detected!");
    while (1) delay(1000);
  }

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