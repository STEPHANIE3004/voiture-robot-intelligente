/*
 * Voiture Robot Sécurisée — Arduino Mega 2560
 * ============================================
 * Couche matérielle : lecture capteurs, contrôle moteurs,
 * affichage OLED, alertes sonores/visuelles, RFID.
 * Reçoit des commandes de la Raspberry Pi via Serial1 (UART).
 * Envoie les données capteurs en JSON toutes les 200 ms.
 *
 * Auteur  : Vanelle Stéphanie MANGOUA
 * Matériel: Arduino Mega 2560
 *
 * ── Brochage ────────────────────────────────────────────────────────────────
 *  A0          → MQ-3 (alcool, analogique)
 *  D2          → Bouton démarrage (INPUT_PULLUP, INT0)
 *  D3          → Buzzer (PWM)
 *  D4          → LED verte  (autorisé)
 *  D5          → LED jaune  (alerte)
 *  D6          → LED rouge  (bloqué / danger)
 *  D7          → L298N IN1  (moteur gauche sens A)
 *  D8          → L298N IN2  (moteur gauche sens B)
 *  D9          → L298N IN3  (moteur droit  sens A)
 *  D10         → L298N IN4  (moteur droit  sens B)
 *  D11 (PWM)   → L298N ENA  (vitesse moteur gauche)
 *  D12 (PWM)   → L298N ENB  (vitesse moteur droit)
 *  D18/D19     → Serial1 TX/RX  ↔ Raspberry Pi (9600 bauds)
 *  D20 (SDA)   → OLED SSD1306 I2C
 *  D21 (SCL)   → OLED SSD1306 I2C
 *  D48         → MFRC522 RST
 *  D53         → MFRC522 SS (SPI)
 *  D50         → MISO (SPI)
 *  D51         → MOSI (SPI)
 *  D52         → SCK  (SPI)
 * ────────────────────────────────────────────────────────────────────────────
 *
 * Protocole Serial1 ↔ RPi :
 *   Arduino → RPi  (JSON, 200 ms) : {"mq3":450,"rfid":false,"btn":false}
 *   RPi     → Arduino (texte)     : CMD:BLOQUER | CMD:AUTORISER |
 *                                   CMD:ALERTE:1 | CMD:ALERTE:2 |
 *                                   CMD:ALERTE:3 | CMD:PARKING
 */

#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// ── Broches ──────────────────────────────────────────────────────────────────
#define PIN_MQ3         A0
#define PIN_BOUTON       2
#define PIN_BUZZER       3
#define PIN_LED_VERTE    4
#define PIN_LED_JAUNE    5
#define PIN_LED_ROUGE    6
#define PIN_IN1          7
#define PIN_IN2          8
#define PIN_IN3          9
#define PIN_IN4         10
#define PIN_ENA         11
#define PIN_ENB         12
#define PIN_RFID_RST    48
#define PIN_RFID_SS     53

// ── OLED 128×64 I2C ──────────────────────────────────────────────────────────
#define OLED_LARGEUR    128
#define OLED_HAUTEUR     64
#define OLED_ADDR      0x3C
Adafruit_SSD1306 oled(OLED_LARGEUR, OLED_HAUTEUR, &Wire, -1);

// ── RFID ─────────────────────────────────────────────────────────────────────
MFRC522 rfid(PIN_RFID_SS, PIN_RFID_RST);

// ── Paramètres ────────────────────────────────────────────────────────────────
#define VITESSE_NORMALE     180    // 0–255
#define VITESSE_PARKING     120
#define SEUIL_MQ3_ALERTE    400    // Valeur ADC  ~0.4 mg/L
#define SEUIL_MQ3_DANGER    600    // Valeur ADC  ~0.8 mg/L (limite légale)
#define INTERVALLE_JSON     200    // ms entre deux trames JSON

// ── Variables d'état ─────────────────────────────────────────────────────────
volatile bool bouton_presse   = false;
bool          rfid_detecte    = false;
bool          moteurs_actifs  = false;
uint16_t      valeur_mq3      = 0;
String        cmd_buffer      = "";
unsigned long dernier_json    = 0;

// ── Buzzer — tonalités ────────────────────────────────────────────────────────
void bip_court()   { tone(PIN_BUZZER, 1000, 200); }
void bip_long()    { tone(PIN_BUZZER, 800,  800); }
void bip_urgence() { for(int i=0;i<5;i++){tone(PIN_BUZZER,1500,100);delay(150);} }
void bip_ok()      { tone(PIN_BUZZER, 1200, 100); delay(120);
                     tone(PIN_BUZZER, 1500, 100); }
void sirene()      { for(int f=600;f<1400;f+=20){tone(PIN_BUZZER,f,30);delay(30);}
                     for(int f=1400;f>600;f-=20){tone(PIN_BUZZER,f,30);delay(30);} }

// ── LEDs ──────────────────────────────────────────────────────────────────────
void leds_off() {
    digitalWrite(PIN_LED_VERTE, LOW);
    digitalWrite(PIN_LED_JAUNE, LOW);
    digitalWrite(PIN_LED_ROUGE, LOW);
}
void led_vert()   { leds_off(); digitalWrite(PIN_LED_VERTE, HIGH); }
void led_jaune()  { leds_off(); digitalWrite(PIN_LED_JAUNE, HIGH); }
void led_rouge()  { leds_off(); digitalWrite(PIN_LED_ROUGE, HIGH); }
void led_orange() { leds_off(); digitalWrite(PIN_LED_JAUNE, HIGH);
                                digitalWrite(PIN_LED_ROUGE, HIGH); }

// ── Moteurs L298N ─────────────────────────────────────────────────────────────
void moteurs_avant(uint8_t vitesse) {
    digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENA, vitesse);
    analogWrite(PIN_ENB, vitesse);
    moteurs_actifs = true;
}
void moteurs_droite(uint8_t vitesse) {
    digitalWrite(PIN_IN1, HIGH); digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, LOW);  digitalWrite(PIN_IN4, HIGH);
    analogWrite(PIN_ENA, vitesse);
    analogWrite(PIN_ENB, vitesse / 2);
}
void moteurs_gauche(uint8_t vitesse) {
    digitalWrite(PIN_IN1, LOW);  digitalWrite(PIN_IN2, HIGH);
    digitalWrite(PIN_IN3, HIGH); digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENA, vitesse / 2);
    analogWrite(PIN_ENB, vitesse);
}
void moteurs_stop() {
    digitalWrite(PIN_IN1, LOW); digitalWrite(PIN_IN2, LOW);
    digitalWrite(PIN_IN3, LOW); digitalWrite(PIN_IN4, LOW);
    analogWrite(PIN_ENA, 0);
    analogWrite(PIN_ENB, 0);
    moteurs_actifs = false;
}

// ── OLED ──────────────────────────────────────────────────────────────────────
void afficher(const char* ligne1, const char* ligne2 = "",
              const char* ligne3 = "", uint8_t taille = 2) {
    oled.clearDisplay();
    oled.setTextColor(SSD1306_WHITE);

    oled.setTextSize(taille);
    oled.setCursor(0, 0);
    oled.println(ligne1);

    oled.setTextSize(1);
    oled.setCursor(0, 20);
    oled.println(ligne2);

    oled.setCursor(0, 32);
    oled.println(ligne3);

    oled.display();
}

void afficher_mq3(uint16_t val) {
    char buf[32];
    sprintf(buf, "MQ3: %d", val);
    afficher("VERIF...", buf, "Analysez...", 1);
}

// ── Interruption bouton ───────────────────────────────────────────────────────
void ISR_bouton() {
    static unsigned long dernier_appui = 0;
    unsigned long now = millis();
    if (now - dernier_appui > 300) {   // Anti-rebond 300 ms
        bouton_presse = true;
        dernier_appui = now;
    }
}

// ── Lecture RFID ──────────────────────────────────────────────────────────────
bool lire_rfid() {
    if (!rfid.PICC_IsNewCardPresent())   return false;
    if (!rfid.PICC_ReadCardSerial())     return false;
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return true;
}

// ── Mode stationnement autonome ───────────────────────────────────────────────
/*
 * Suit la ligne au sol (capteur TCRT5000 sur A1/A2) et s'arrête
 * dès qu'une étiquette RFID est détectée (zone de stationnement).
 */
void mode_parking() {
    afficher("MODE", "PARKING", "AUTONOME");
    sirene();

    unsigned long debut = millis();
    const unsigned long TIMEOUT_PARKING = 30000UL;  // 30 s max

    while (millis() - debut < TIMEOUT_PARKING) {
        // Vérifier RFID — arrêt si zone détectée
        if (lire_rfid()) {
            moteurs_stop();
            afficher("STATIONNE", "Zone sure", "Moteur OFF");
            bip_ok();
            led_vert();
            return;
        }

        // Suivi de ligne (TCRT5000 sur A1 gauche, A2 droit)
        int gauche = analogRead(A1);
        int droit  = analogRead(A2);

        if (gauche < 500 && droit < 500) {
            moteurs_avant(VITESSE_PARKING);
        } else if (gauche >= 500 && droit < 500) {
            moteurs_droite(VITESSE_PARKING);
        } else if (gauche < 500 && droit >= 500) {
            moteurs_gauche(VITESSE_PARKING);
        } else {
            // Ligne perdue — avancer doucement
            moteurs_avant(VITESSE_PARKING / 2);
        }

        delay(20);
    }

    // Timeout — arrêt d'urgence
    moteurs_stop();
    afficher("TIMEOUT", "Arret force", "Verif systeme");
    led_rouge();
}

// ── Traitement commandes RPi ──────────────────────────────────────────────────
void traiter_commande(String cmd) {
    cmd.trim();

    if (cmd == "CMD:AUTORISER") {
        led_vert();
        moteurs_avant(VITESSE_NORMALE);
        afficher("AUTORISE", "Demarrage OK", "Bonne route!");
        bip_ok();

    } else if (cmd == "CMD:BLOQUER") {
        moteurs_stop();
        led_rouge();
        afficher("BLOQUE", "Alcool detecte", "Arret moteur");
        bip_urgence();

    } else if (cmd == "CMD:ALERTE:1") {
        led_jaune();
        afficher("SOMNOLENCE", "Niveau 1", "Reveillez-vous!");
        bip_court();

    } else if (cmd == "CMD:ALERTE:2") {
        led_orange();
        afficher("ATTENTION!", "Vous dormez?", "Reagissez!");
        bip_long();
        delay(200);
        bip_long();

    } else if (cmd == "CMD:ALERTE:3") {
        led_rouge();
        afficher("URGENCE!", "Sans reaction", "Mode auto...");
        bip_urgence();

    } else if (cmd == "CMD:PARKING") {
        mode_parking();

    } else if (cmd == "CMD:RESET") {
        moteurs_stop();
        leds_off();
        oled.clearDisplay();
        oled.display();
        bouton_presse = false;
    }
}

// ── Envoi JSON vers RPi ───────────────────────────────────────────────────────
void envoyer_json() {
    valeur_mq3   = analogRead(PIN_MQ3);
    rfid_detecte = lire_rfid();

    StaticJsonDocument<128> doc;
    doc["mq3"]  = valeur_mq3;
    doc["rfid"] = rfid_detecte;
    doc["btn"]  = bouton_presse;
    doc["mot"]  = moteurs_actifs;

    serializeJson(doc, Serial1);
    Serial1.println();

    // Réinitialiser bouton après envoi
    if (bouton_presse) bouton_presse = false;
}

// ════════════════════════════════════════════════════════════════════════════
//  SETUP
// ════════════════════════════════════════════════════════════════════════════
void setup() {
    // GPIO
    pinMode(PIN_BOUTON,    INPUT_PULLUP);
    pinMode(PIN_BUZZER,    OUTPUT);
    pinMode(PIN_LED_VERTE, OUTPUT);
    pinMode(PIN_LED_JAUNE, OUTPUT);
    pinMode(PIN_LED_ROUGE, OUTPUT);
    pinMode(PIN_IN1, OUTPUT); pinMode(PIN_IN2, OUTPUT);
    pinMode(PIN_IN3, OUTPUT); pinMode(PIN_IN4, OUTPUT);
    pinMode(PIN_ENA, OUTPUT); pinMode(PIN_ENB, OUTPUT);

    // Interruption bouton
    attachInterrupt(digitalPinToInterrupt(PIN_BOUTON), ISR_bouton, FALLING);

    // Serial USB (debug) + Serial1 (Raspberry Pi)
    Serial.begin(9600);
    Serial1.begin(9600);

    // SPI + RFID
    SPI.begin();
    rfid.PCD_Init();

    // OLED
    if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println(F("[ERR] OLED non détecté"));
    }
    oled.clearDisplay();

    // Séquence de démarrage
    afficher("VOITURE", "SECURISEE", "Init...", 1);
    delay(1000);

    // Test LEDs
    led_vert();  delay(300);
    led_jaune(); delay(300);
    led_rouge(); delay(300);
    leds_off();

    bip_ok();
    afficher("EN ATTENTE", "Appuyez sur", "le bouton", 1);
    Serial.println("[INFO] Système prêt");
}

// ════════════════════════════════════════════════════════════════════════════
//  LOOP
// ════════════════════════════════════════════════════════════════════════════
void loop() {
    // ── Lecture commandes RPi ─────────────────────────────────────────────
    while (Serial1.available()) {
        char c = Serial1.read();
        if (c == '\n') {
            if (cmd_buffer.length() > 0) {
                traiter_commande(cmd_buffer);
                cmd_buffer = "";
            }
        } else {
            cmd_buffer += c;
        }
    }

    // ── Envoi JSON toutes les 200 ms ──────────────────────────────────────
    unsigned long now = millis();
    if (now - dernier_json >= INTERVALLE_JSON) {
        envoyer_json();
        dernier_json = now;
    }
}
