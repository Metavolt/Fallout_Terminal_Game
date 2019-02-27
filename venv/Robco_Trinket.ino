#include <TrinketKeyboard.h>

#define PIN_TRIGGER 0
boolean password_entered = false;

void setup(){
  
  pinMode(PIN_TRIGGER, INPUT);
  digitalWrite(PIN_TRIGGER, LOW);
  TrinketKeyboard.begin();
    
}

void loop(){
  
  TrinketKeyboard.poll();

  if (digitalRead(PIN_TRIGGER) == HIGH && password_entered == false){
    TrinketKeyboard.print("SuperSecretPassword");
    password_entered = true;
  }

}
