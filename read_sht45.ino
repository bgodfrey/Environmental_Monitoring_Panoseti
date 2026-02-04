#include <Adafruit_SHT4x.h>
#include <Adafruit_NeoPixel.h>

// --- NeoPixel setup (so we can turn it off) ---
#define LED_PIN    PIN_NEOPIXEL
#define LED_COUNT  1

Adafruit_NeoPixel pixels(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

// --- SHT45 sensor object ---
Adafruit_SHT4x sht4;

void setup() {
  // USB serial
  Serial.begin(115200);
  while (!Serial) {
    ; // wait for USB serial connection
  }

  Serial.println("SHT45 Trinkey: Temp + Humidity over Serial");

  // Initialize NeoPixel and turn it OFF
  pixels.begin();
  pixels.clear();
  pixels.show();

  // Initialize SHT45
  if (!sht4.begin()) {
    Serial.println("ERROR: Couldn't find SHT4x sensor!");
    while (1) {
      delay(1000);
    }
  }

  // Highest precision, no heater
  sht4.setPrecision(SHT4X_HIGH_PRECISION);
  sht4.setHeater(SHT4X_NO_HEATER);

  Serial.println("Sensor initialized.");
  Serial.println("Format: millis,temp_C,humidity_percent");
}

void loop() {
  sensors_event_t humidity, temp;

  // Read sensor
  if (!sht4.getEvent(&humidity, &temp)) {
    Serial.println("ERROR: Failed to read SHT45");
  } else {
    unsigned long ms = millis();
    float t = temp.temperature;                 // °C
    float rh = humidity.relative_humidity;      // %RH

    // CSV-style output
    Serial.print(ms);
    Serial.print(", ");
    Serial.print(t, 2);
    Serial.print(", ");
    Serial.println(rh, 2);
  }

  delay(1000);  // 1 sample per second
}