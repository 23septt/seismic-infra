#include <Arduino_Modulino.h>
#include <Arduino_RouterBridge.h>

ModulinoPixels pixels;
ModulinoBuzzer buzzer;

volatile bool pixelsPending = false;
volatile bool buzzerPending = false;

volatile int pixelR = 0;
volatile int pixelG = 0;
volatile int pixelB = 0;
volatile int pixelBrightness = 0;
volatile int pixelCount = 8;

volatile int buzzerFrequency = 0;
volatile int buzzerDuration = 0;

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
  pixels.begin();
  buzzer.begin();

  Bridge.begin();
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
