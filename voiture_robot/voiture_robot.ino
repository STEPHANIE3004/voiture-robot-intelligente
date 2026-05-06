/*
 * ============================================================
 *  VOITURE ROBOT INTELLIGENTE
 *  Evitement d'obstacles + Suivi de ligne
 * ============================================================
 *  Auteure  : Vanelle Stephanie MANGOUA DJOUSSEU
 *  Materiel : Arduino Uno + L298N + HC-SR04 + Servo SG90
 *             + 2x capteurs IR TCRT5000 + 2x moteurs DC 6V
 *
 *  Librairies requises (Arduino IDE) :
 *    - NewPing  (Ultrasonic)  -> Gestionnaire de bibliotheques
 *    - Servo    (integree Arduino)
 * ============================================================
 *
 *  SCHEMA DE CABLAGE :
 *  -------------------
 *  HC-SR04  : TRIG -> D7 | ECHO -> D8
 *  Servo    : Signal -> D9
 *  L298N    : IN1->D2 | IN2->D3 | IN3->D4 | IN4->D5
 *             ENA->D10 (PWM) | ENB->D11 (PWM)
 *  IR Gauche: A0   IR Droite: A1
 *  Alimentation : 7.4V LiPo -> L298N | 5V Arduino -> Servo
 */

#include <NewPing.h>
#include <Servo.h>

// ─── Broches ──────────────────────────────────────────────
#define TRIG_PIN       7
#define ECHO_PIN       8
#define SERVO_PIN      9

// Moteur GAUCHE (L298N : IN1, IN2, ENA)
#define IN1            2
#define IN2            3
#define ENA            10   // PWM

// Moteur DROIT (L298N : IN3, IN4, ENB)
#define IN3            4
#define IN4            5
#define ENB            11   // PWM

// Capteurs IR suivi de ligne
#define IR_GAUCHE      A0
#define IR_DROITE      A1

// ─── Parametres ───────────────────────────────────────────
#define DISTANCE_MAX_CM   200
#define DISTANCE_OBSTACLE  25   // cm -> commence a eviter
#define DISTANCE_URGENCE   10   // cm -> stop immediat
#define VITESSE_NORMALE   180   // 0-255
#define VITESSE_LENTE     120
#define VITESSE_ROTATION  150
#define SEUIL_IR          500   // valeur analogique (0-1023)
#define DELAI_ROTATION    350   // ms

// ─── Objets globaux ───────────────────────────────────────
NewPing sonar(TRIG_PIN, ECHO_PIN, DISTANCE_MAX_CM);
Servo   servoTete;

// ─── Variables etat ───────────────────────────────────────
unsigned int distanceCm      = 0;
unsigned long nbEvitements   = 0;
bool          modesuiviLigne = false;

// ─── Prototypes ───────────────────────────────────────────
void avancer(uint8_t vitesse);
void reculer(uint8_t vitesse);
void tournerGauche(uint8_t vitesse);
void tournerDroite(uint8_t vitesse);
void stopper();
unsigned int lireDistance();
int choisirMeilleureDirection();
void eviterObstacle();
void suivreLigne();
void afficherSerial();

// ════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(9600);

  // Moteurs
  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT); pinMode(ENA, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);

  // Servo
  servoTete.attach(SERVO_PIN);
  servoTete.write(90);   // centre
  delay(500);

  stopper();

  Serial.println(F("=== VOITURE ROBOT INITIALISEE ==="));
  Serial.println(F("Mode : evitement d'obstacles"));
  delay(2000);
}

// ════════════════════════════════════════════════════════════
//  LOOP PRINCIPAL
// ════════════════════════════════════════════════════════════
void loop() {
  distanceCm = lireDistance();
  afficherSerial();

  if (distanceCm <= DISTANCE_URGENCE) {
    // Stop immediat + recul d'urgence
    stopper();
    delay(100);
    reculer(VITESSE_LENTE);
    delay(400);
    eviterObstacle();

  } else if (distanceCm <= DISTANCE_OBSTACLE) {
    // Obstacle detecte -> strategie d'evitement
    stopper();
    delay(200);
    eviterObstacle();

  } else {
    // Voie libre -> avancer
    avancer(VITESSE_NORMALE);
  }

  delay(50);  // Anti-rebond capteur
}

// ════════════════════════════════════════════════════════════
//  COMMANDES MOTEURS
// ════════════════════════════════════════════════════════════

void avancer(uint8_t vitesse) {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  analogWrite(ENA, vitesse);
  analogWrite(ENB, vitesse);
}

void reculer(uint8_t vitesse) {
  digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  analogWrite(ENA, vitesse);
  analogWrite(ENB, vitesse);
}

void tournerGauche(uint8_t vitesse) {
  // Moteur gauche recule, moteur droit avance
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  analogWrite(ENA, vitesse);
  analogWrite(ENB, vitesse);
}

void tournerDroite(uint8_t vitesse) {
  // Moteur gauche avance, moteur droit recule
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);  digitalWrite(IN4, HIGH);
  analogWrite(ENA, vitesse);
  analogWrite(ENB, vitesse);
}

void stopper() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
}

// ════════════════════════════════════════════════════════════
//  CAPTEUR ULTRASON
// ════════════════════════════════════════════════════════════

unsigned int lireDistance() {
  delay(30);  // Delai entre 2 mesures (evite les echos parasites)
  unsigned int d = sonar.ping_cm();
  if (d == 0) d = DISTANCE_MAX_CM;  // 0 = pas d'echo -> voie libre
  return d;
}

// Balayage servo : regarde gauche, droite, puis choisit
int choisirMeilleureDirection() {
  unsigned int distGauche, distDroite;

  // Regarder a droite
  servoTete.write(30);
  delay(400);
  distDroite = lireDistance();

  // Revenir au centre
  servoTete.write(90);
  delay(300);

  // Regarder a gauche
  servoTete.write(150);
  delay(400);
  distGauche = lireDistance();

  // Revenir au centre
  servoTete.write(90);
  delay(300);

  Serial.print(F("  Scan -> G:")); Serial.print(distGauche);
  Serial.print(F("cm  D:")); Serial.print(distDroite); Serial.println(F("cm"));

  if (distGauche >= distDroite) return -1;  // -1 = tourner gauche
  else                          return  1;  //  1 = tourner droite
}

// ════════════════════════════════════════════════════════════
//  STRATEGIE EVITEMENT D'OBSTACLE
// ════════════════════════════════════════════════════════════

void eviterObstacle() {
  nbEvitements++;
  Serial.print(F("[EVIT #")); Serial.print(nbEvitements);
  Serial.print(F("] obstacle a ")); Serial.print(distanceCm); Serial.println(F("cm"));

  int direction = choisirMeilleureDirection();

  if (direction == -1) {
    Serial.println(F("  -> Tourne GAUCHE"));
    tournerGauche(VITESSE_ROTATION);
  } else {
    Serial.println(F("  -> Tourne DROITE"));
    tournerDroite(VITESSE_ROTATION);
  }

  delay(DELAI_ROTATION);
  stopper();
  delay(100);
}

// ════════════════════════════════════════════════════════════
//  SUIVI DE LIGNE (mode secondaire, activer si besoin)
// ════════════════════════════════════════════════════════════

void suivreLigne() {
  bool ig = analogRead(IR_GAUCHE) < SEUIL_IR;   // true = ligne noire
  bool id = analogRead(IR_DROITE) < SEUIL_IR;

  if (ig && id) {
    avancer(VITESSE_NORMALE);
  } else if (!ig && id) {
    tournerGauche(VITESSE_LENTE);
  } else if (ig && !id) {
    tournerDroite(VITESSE_LENTE);
  } else {
    stopper();
  }
}

// ════════════════════════════════════════════════════════════
//  AFFICHAGE SERIAL MONITOR
// ════════════════════════════════════════════════════════════

void afficherSerial() {
  Serial.print(F("Distance: "));
  Serial.print(distanceCm);
  Serial.print(F(" cm | Evitements: "));
  Serial.println(nbEvitements);
}
