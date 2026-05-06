# 🚗 Voiture Robot Intelligente — Sécurité Active Conducteur

Système embarqué de sécurité intégré à une voiture robot, développé à l'**ESIEA**.  
Prévient les risques liés à la **somnolence** et à l'**alcoolémie** du conducteur, avec activation automatique d'un **mode de stationnement autonome** en cas d'urgence.

---

## 🎯 Fonctionnalités

| Exigence | Description | Implémentation |
|----------|-------------|----------------|
| **SR1** | Lecture alcool MQ-3 + blocage démarrage | Arduino — ADC A0 |
| **SR2** | Détection somnolence par caméra (EAR, MAR, tête) | Raspberry Pi — OpenCV + dlib |
| **SR3** | Alertes sonores (buzzer) et visuelles (LEDs + OLED) | Arduino — 3 niveaux d'alerte |
| **SR4** | Mode autonome si pas de réaction en 5 s (suivi ligne + RFID) | Arduino — L298N + TCRT5000 + MFRC522 |
| **SR5** | Affichage états temps réel sur OLED | Arduino — SSD1306 I2C |
| **SR6** | Tolérance erreurs vidéo, latence < 200 ms | Raspberry Pi — gestion exceptions |

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐     Serial UART     ┌────────────────────────────┐
│        Raspberry Pi             │ ◄──────────────────► │      Arduino Mega 2560     │
│                                 │   JSON + Commandes   │                            │
│  main.py — Machine à états      │                      │  MQ-3   → A0              │
│  IDLE → VERIF → AUTORISE        │                      │  RFID   → SPI             │
│       ↕              ↕          │                      │  L298N  → D7-D12          │
│  ALERTE(1,2,3)    BLOQUE        │                      │  OLED   → I2C             │
│       ↓                         │                      │  LEDs   → D4-D6           │
│  PARKING → ARRET                │                      │  Buzzer → D3              │
│                                 │                      │  Bouton → D2              │
│  detection_somnolence.py        │                      └────────────────────────────┘
│  OpenCV + dlib                  │
│  EAR / MAR / Angle tête         │
│  Niveaux 0 → 3                  │
└─────────────────────────────────┘
         │ USB / Pi Camera
         ▼
    [ Caméra conducteur ]
```

---

## 📟 Machine à états

```
          [Bouton]
IDLE ──────────────► VERIFICATION
                         │
              ┌──────────┴──────────┐
         [Alcool OK]          [Alcool > seuil]
              │                     │
           AUTORISE              BLOQUE
              │
         [EAR < 0.25, 20 frames]
              │
           ALERTE_1  ◄──── [Réaction conducteur]
              │  5 s sans réaction
           ALERTE_2  ◄──── [Réaction conducteur]
              │  5 s sans réaction
           ALERTE_3
              │
           PARKING  (suivi ligne + RFID zone)
              │  RFID détecté
            ARRET
```

---

## 🔧 Matériel

| Composant | Rôle | Broche |
|-----------|------|--------|
| Arduino Mega 2560 | Contrôleur matériel | — |
| Raspberry Pi 3/4 | Traitement vidéo + logique | — |
| Caméra USB / Pi Camera | Flux visage conducteur | USB |
| Capteur MQ-3 | Taux d'alcool (analogique) | A0 |
| MFRC522 | Détection RFID zone parking | SPI (D50-D53) |
| L298N | Pilote moteurs DC | D7-D12 |
| TCRT5000 × 2 | Suivi de ligne (parking auto) | A1, A2 |
| SSD1306 OLED 128×64 | Affichage états | I2C (D20-D21) |
| LED verte / jaune / rouge | Indicateurs visuels | D4, D5, D6 |
| Buzzer actif | Alertes sonores | D3 (PWM) |
| Bouton poussoir | Démarrage | D2 (INT0) |

---

## 📁 Structure du projet

```
voiture-robot-intelligente/
├── arduino/
│   └── voiture_securisee/
│       └── voiture_securisee.ino   ← Firmware Arduino Mega
├── raspberry/
│   ├── main.py                     ← Machine à états principale
│   ├── detection_somnolence.py     ← Détection somnolence 3 niveaux (EAR/MAR/angle)
│   ├── serial_comm.py              ← Communication UART thread-safe
│   └── requirements.txt
└── README.md
```

---

## ⚙️ Installation & Lancement

### Arduino
1. Ouvrir `arduino/voiture_securisee/voiture_securisee.ino` dans l'IDE Arduino
2. Installer les bibliothèques : `MFRC522`, `Adafruit_SSD1306`, `ArduinoJson`
3. Sélectionner **Arduino Mega 2560**, flasher

### Raspberry Pi
```bash
pip install -r raspberry/requirements.txt

# Télécharger le modèle dlib (obligatoire)
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2
mv shape_predictor_68_face_landmarks.dat raspberry/

# Lancer
cd raspberry/
python main.py --port /dev/ttyAMA0 --camera 0

# Mode debug (fenêtre caméra + logs détaillés)
python main.py --debug
```

---

## 📡 Protocole Arduino ↔ RPi

**Arduino → RPi** (JSON, 200 ms) : `{"mq3": 450, "rfid": false, "btn": false, "mot": true}`

**RPi → Arduino** :

| Commande | Effet |
|----------|-------|
| `CMD:AUTORISER` | Moteurs ON, LED verte, OLED "AUTORISÉ" |
| `CMD:BLOQUER` | Moteurs OFF, LED rouge, OLED "BLOQUÉ" |
| `CMD:ALERTE:1` | Bip court, LED jaune, OLED "SOMNOLENCE" |
| `CMD:ALERTE:2` | Bip long, LED orange, OLED "VOUS DORMEZ?" |
| `CMD:ALERTE:3` | Sirène, LED rouge, OLED "URGENCE" |
| `CMD:PARKING` | Suivi ligne autonome + arrêt sur RFID |
| `CMD:RESET` | Arrêt total |

---

## 📚 Contexte

Projet académique ESIEA — Systèmes Embarqués.  
Système de sécurité conducteur réaliste combinant traitement d'image temps réel (Raspberry Pi + OpenCV) et contrôle matériel bas-niveau (Arduino Mega + capteurs/actionneurs).
