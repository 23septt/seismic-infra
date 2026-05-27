#include "Arduino_Modulino.h"
#include "Arduino_RouterBridge.h"
#include <Arduino.h>

ModulinoPixels pixels;
ModulinoBuzzer buzzer;
ModulinoThermo thermo;
ModulinoMovement movement;

volatile bool pixelsPending = false;
volatile bool buzzerPending = false;

volatile int pixelR = 0;
volatile int pixelG = 0;
volatile int pixelB = 0;
volatile int pixelBrightness = 0;
volatile int pixelCount = 8;

volatile int buzzerFrequency = 0;
volatile int buzzerDuration = 0;

const int DHT11_PIN = 2;

void pixels_set_all(int r, int g, int b, int brightness, int count) {
  pixelR = constrain(r, 0, 255);
  pixelG = constrain(g, 0, 255);
  pixelB = constrain(b, 0, 255);
  pixelBrightness = constrain(brightness, 0, 255);
  pixelCount = constrain(count, 0, 8);
  pixelsPending = true;
}

void buzzer_tone(int frequency, int duration) {
  buzzerFrequency = constrain(frequency, 0, 20000);
  buzzerDuration = constrain(duration, 0, 10000);
  buzzerPending = true;
}

bool readDht11(float &temperatureC, float &humidityPct) {
  uint8_t data[5] = {0, 0, 0, 0, 0};

  pinMode(DHT11_PIN, OUTPUT);
  digitalWrite(DHT11_PIN, LOW);
  delay(20);
  digitalWrite(DHT11_PIN, HIGH);
  delayMicroseconds(40);
  pinMode(DHT11_PIN, INPUT_PULLUP);

  if (pulseIn(DHT11_PIN, LOW, 1000) == 0) {
    return false;
  }
  if (pulseIn(DHT11_PIN, HIGH, 1000) == 0) {
    return false;
  }

  for (int bit = 0; bit < 40; bit++) {
    if (pulseIn(DHT11_PIN, LOW, 1000) == 0) {
      return false;
    }
    unsigned long highTime = pulseIn(DHT11_PIN, HIGH, 1000);
    if (highTime == 0) {
      return false;
    }
    data[bit / 8] <<= 1;
    if (highTime > 45) {
      data[bit / 8] |= 1;
    }
  }

  uint8_t checksum = data[0] + data[1] + data[2] + data[3];
  if (checksum != data[4]) {
    return false;
  }

  humidityPct = data[0] + data[1] * 0.1;
  temperatureC = data[2] + data[3] * 0.1;
  return true;
}

String sensor_accel() {
  movement.update();
  return String(movement.getX(), 6) + "," +
         String(movement.getY(), 6) + "," +
         String(movement.getZ(), 6) + "," +
         String(movement.getRoll(), 6) + "," +
         String(movement.getPitch(), 6) + "," +
         String(movement.getYaw(), 6);
}

String sensor_env() {
  float dhtTemp = NAN;
  float dhtHumid = NAN;
  readDht11(dhtTemp, dhtHumid);

  return String(thermo.getTemperature(), 3) + "," +
         String(thermo.getHumidity(), 3) + "," +
         String(dhtTemp, 3) + "," +
         String(dhtHumid, 3);
}

void applyPixels() {
  int r = pixelR * pixelBrightness / 255;
  int g = pixelG * pixelBrightness / 255;
  int b = pixelB * pixelBrightness / 255;

  for (int i = 0; i < 8; i++) {
    if (i < pixelCount) {
      pixels.set(i, ModulinoColor(r, g, b));
    } else {
      pixels.clear(i);
    }
  }
  pixels.show();
}

void applyBuzzer() {
  if (buzzerFrequency <= 0 || buzzerDuration <= 0) {
    buzzer.tone(0, 1);
    return;
  }
  buzzer.tone(buzzerFrequency, buzzerDuration);
}

void setup() {
  Modulino.begin();
  thermo.begin();
  movement.begin();
  pixels.begin();
  buzzer.begin();
  pinMode(DHT11_PIN, INPUT_PULLUP);

  Bridge.begin();
  Bridge.provide("sensor_env", sensor_env);
  Bridge.provide("sensor_accel", sensor_accel);
  Bridge.provide("pixels_set_all", pixels_set_all);
  Bridge.provide("buzzer_tone", buzzer_tone);
  Bridge.notify("mcu_status", "seismoguard_bridge_ready");
}

void loop() {
  if (pixelsPending) {
    pixelsPending = false;
    applyPixels();
  }

  if (buzzerPending) {
    buzzerPending = false;
    applyBuzzer();
  }

  delay(5);
}
