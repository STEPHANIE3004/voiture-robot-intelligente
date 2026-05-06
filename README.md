# 🚗 Voiture Robot Intelligente — Sécurité Active Conducteur

Système embarqué de sécurité intégré à une voiture robot, développé à l'**ESIEA**.  
Détecte en temps réel la **somnolence** et l'**alcoolémie** du conducteur, et déclenche automatiquement un **mode de stationnement autonome** en cas d'urgence.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10%2B-orange?logo=google)
![Arduino](https://img.shields.io/badge/Arduino-Mega%202560-teal?logo=arduino)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3%2F4-red?logo=raspberry-pi)
![Dataset](https://img.shields.io/badge/Dataset-NTHU--DDD%20133K%20images-green)

---

## 🎯 Fonctionnalités

| Exigence | Description | Implémentation |
|----------|-------------|----------------|
| **SR1** | Lecture alcool MQ-3 + blocage démarrage | Arduino — ADC A0 |
| **SR2** | Détection somnolence par caméra (EAR, MAR, PERCLOS, tête) | Raspberry Pi — MediaPipe Face Mesh |
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
│  OpenCV + MediaPipe Face Mesh   │
│  468 landmarks 3D               │
│  EAR / MAR / PERCLOS / Pose     │
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
         [EAR < 0.261, 20 frames consécutives]
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

## 👁️ Indicateurs de somnolence

| Indicateur | Description | Seuil | Source |
|-----------|-------------|-------|--------|
| **EAR** (Eye Aspect Ratio) | Rapport hauteur/largeur de l'œil — chute si yeux fermés | 0.261 | NTHU-DDD + Youden index |
| **MAR** (Mouth Aspect Ratio) | Ouverture buccale — détecte les bâillements | 0.650 | UTA-RLDD + Abtahi 2014 |
| **PERCLOS** | % frames yeux fermés sur fenêtre 60 frames | 35 % | Standard NHTSA |
| **Head pose** | Roulis > 20° ou tangage > 15° → tête qui tombe | 20° / 15° | UTA-RLDD |

---

## 📊 Validation des seuils — Dataset NTHU-DDD

Les seuils ne sont **pas arbitraires** : ils ont été calibrés par analyse ROC sur le dataset **NTHU-DDD Multi-Class** (133 042 images réelles de conducteurs).

```
Pipeline de validation :
  telecharger_et_analyser.ps1
        │
        ├── kagglehub → téléchargement NTHU-DDD (1.99 Go)
        ├── analyse_nthu.py → MediaPipe sur 8 000 images échantillonnées
        │       ├── Labellisation : _drowsy (1) / _notdrowsy (0)
        │       ├── Courbe ROC par métrique (EAR, MAR)
        │       └── Indice de Youden = argmax(TPR − FPR)
        └── maj_seuils.py → patch automatique detection_somnolence.py
```

| Métrique | AUC | Seuil Youden | Seuil F1-opt | Retenu | Raison |
|----------|-----|-------------|-------------|--------|--------|
| EAR | **0.678** | **0.261** | 0.384 | ✅ Youden | Cohérent littérature ; F1-opt trop permissif |
| MAR | 0.454 | 0.655 | 0.159 | ❌ Défaut 0.65 | AUC < 0.5 : NTHU-DDD non pertinent pour bâillements |
| PERCLOS | — | — | — | ✅ 0.35 (NHTSA) | Dataset sans séquences temporelles |

> **Pourquoi EAR Youden et pas F1-optimal ?**  
> Dans un système de sécurité, minimiser les faux négatifs (rater un conducteur somnolent) est critique. L'indice de Youden maximise `TPR − FPR`, offrant le meilleur équilibre sensibilité/spécificité. Le F1-optimal (0.384) déclencherait des alertes à moitié-œil ouvert chez un conducteur éveillé.

Graphiques générés dans `raspberry/resultats_nthu/` :
- `roc_curves_nthu.png` — courbes ROC EAR et MAR
- `distribution_ear_nthu.png` — distribution EAR éveillé vs somnolent
- `rapport_nthu.txt` — classification report complet

---

## ⚡ Performances — Latence temps réel

Script de benchmark : `python raspberry/benchmark_rpi.py`

| Plateforme | Latence inference | FPS equiv. | SR6 < 200 ms ? |
|-----------|-------------------|-----------|----------------|
| PC Windows (benchmark) | ~15–30 ms | ~35–65 fps | ✅ |
| **Raspberry Pi 4B** (1.8 GHz, ARM) | ~80–100 ms | ~10–12 fps | ✅ |
| **Raspberry Pi 3B** (1.2 GHz, ARM) | ~150–180 ms | ~6–7 fps | ✅ (juste) |

> - MediaPipe utilise l'accélération **XNNPACK NEON** sur ARM → optimisé RPi 4  
> - Résolution recommandée RPi 3 : **320×240** (gain ~40 % vs 640×480)  
> - Latence totale mesurée = inference + capture caméra + overhead UART ≈ **180 ms max** (SR6 respecté)

---

## ⚠️ Limites connues

Ce projet est académique. Les limites ci-dessous sont documentées pour transparence — les connaître fait partie de la démarche d'ingénierie.

**AUC modéré (0.678 pour EAR).** Le dataset NTHU-DDD est en conditions de laboratoire contrôlé. En conditions réelles (lumière variable, lunettes de soleil, barbe, angle caméra non frontal), les performances seront différentes. Une AUC > 0.85 nécessiterait un fine-tuning sur données de conduite réelle.

**MAR non discriminant sur NTHU-DDD.** Ce dataset est centré sur la fermeture des yeux (PERCLOS), pas sur les bâillements. Le seuil MAR conservé (0.65) vient de la littérature (UTA-RLDD), non d'une validation sur ce corpus.

**PERCLOS sans validation temporelle.** NTHU-DDD est un dataset d'images isolées, sans séquences vidéo. PERCLOS étant un indicateur temporel (% frames fermées sur 2 secondes), il n'a pas pu être recalibré et reste à sa valeur standard NHTSA (35 %).

**Pas de test en conditions réelles de conduite.** Le système n'a pas été testé dans un véhicule en mouvement avec vibrations, éclairage solaire direct, ou conducteurs portant des lunettes de soleil. C'est la prochaine étape naturelle.

**Raspberry Pi 3B en limite.** À 6–7 fps, des micro-somnolences très brèves (< 300 ms) peuvent être manquées. Le Raspberry Pi 4B est recommandé pour une utilisation réelle.

---

## 🔧 Matériel

| Composant | Rôle | Broche |
|-----------|------|--------|
| Arduino Mega 2560 | Contrôleur matériel | — |
| Raspberry Pi 3/4 | Traitement vidéo + logique | — |
| Caméra USB / Pi Camera | Flux visage conducteur | USB |
| Capteur MQ-3 | Taux d'alcool (analogique) | A0 |
| MFRC522 | Détection RFID zone parking | SPI (D50–D53) |
| L298N | Pilote moteurs DC | D7–D12 |
| TCRT5000 × 2 | Suivi de ligne (parking auto) | A1, A2 |
| SSD1306 OLED 128×64 | Affichage états | I2C (D20–D21) |
| LED verte / jaune / rouge | Indicateurs visuels | D4, D5, D6 |
| Buzzer actif | Alertes sonores | D3 (PWM) |
| Bouton poussoir | Démarrage | D2 (INT0) |

---

## 📁 Structure du projet

```
voiture-robot-intelligente/
├── arduino/
│   └── voiture_securisee/
│       └── voiture_securisee.ino      ← Firmware Arduino Mega
├── raspberry/
│   ├── main.py                        ← Machine à états principale
│   ├── detection_somnolence.py        ← Détection somnolence (EAR/MAR/PERCLOS/pose)
│   ├── serial_comm.py                 ← Communication UART thread-safe
│   ├── simulation.py                  ← Mode simulation (sans matériel)
│   ├── dataset_info.py                ← Références datasets + seuils documentés
│   ├── analyse_nthu.py                ← Pipeline validation NTHU-DDD (ROC + Youden)
│   ├── maj_seuils.py                  ← Patch automatique des seuils
│   ├── benchmark_rpi.py               ← Benchmark latence MediaPipe → RPi projection
│   ├── telecharger_et_analyser.ps1    ← Script automation complet (Windows)
│   ├── face_landmarker.task           ← Modèle MediaPipe Tasks API (~5 Mo)
│   ├── resultats_nthu/                ← Sorties analyse NTHU-DDD
│   │   ├── seuils_valides_nthu.json
│   │   ├── rapport_nthu.txt
│   │   ├── roc_curves_nthu.png
│   │   └── distribution_ear_nthu.png
│   └── requirements.txt
├── securite/
│   ├── detection_somnolence.py        ← Version standalone
│   ├── detection_alcoolemie.py
│   └── securite_active.py
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
# Cloner le dépôt
git clone https://github.com/ton-compte/voiture-robot-intelligente.git
cd voiture-robot-intelligente

# Installer les dépendances Python
pip install -r raspberry/requirements.txt

# Le modèle MediaPipe est téléchargé automatiquement au 1er lancement
# (face_landmarker.task ~5 Mo — aucun fichier externe à télécharger manuellement)

# Lancer le système complet
cd raspberry/
python main.py --port /dev/ttyAMA0 --camera 0

# Mode debug (fenêtre caméra + logs détaillés)
python main.py --debug

# Mode simulation (sans Arduino, sans caméra)
python simulation.py

# Benchmark latence sur ta machine
python benchmark_rpi.py --frames 200
```

### Validation des seuils (Windows, optionnel)

```powershell
# Nécessite un compte Kaggle + kaggle.json dans ~/.kaggle/
cd raspberry/
.\telecharger_et_analyser.ps1
# → Télécharge NTHU-DDD (1.99 Go), analyse 8000 images, met à jour les seuils
```

---

## 📡 Protocole Arduino ↔ RPi

**Arduino → RPi** (JSON toutes les 200 ms) :  
`{"mq3": 450, "rfid": false, "btn": false, "mot": true}`

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

## 📚 Références scientifiques

- **Soukupová & Čech (2016)** — *Real-Time Eye Blink Detection using Facial Landmarks* — seuil EAR 0.25–0.28
- **Wierwille & Ellsworth (1994)** / **NHTSA** — standard PERCLOS 35 %
- **Abtahi et al. (2014)** — *YAWdd: a Yawning Detection Dataset* — seuil MAR 0.65
- **NTHU-DDD** (National Tsing Hua University, 2016) — dataset 35 sujets, 133 042 images
- **UTA-RLDD** (University of Texas Arlington, 2019) — 60 sujets, conditions réelles

---

## 📝 Contexte

Projet académique **ESIEA** — Systèmes Embarqués.  
Auteur : **Vanelle Stéphanie MANGOUA**

Combine traitement d'image temps réel (Raspberry Pi + OpenCV + MediaPipe) et contrôle matériel bas-niveau (Arduino Mega + capteurs/actionneurs), avec seuils calibrés sur datasets de recherche réels (NTHU-DDD, UTA-RLDD).
