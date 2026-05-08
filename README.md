# 🚗 Voiture Robot Intelligente — Sécurité Active Conducteur

<div align="center">

**Système embarqué de détection de somnolence et d'alcoolémie en temps réel**  
*Raspberry Pi · Arduino Mega · MediaPipe AI · Parking autonome RFID*

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.3-ff6f00?logo=google&logoColor=white)](https://mediapipe.dev)
[![Arduino](https://img.shields.io/badge/Arduino-Mega_2560-00979d?logo=arduino&logoColor=white)](https://arduino.cc)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-3%2F4-c51a4a?logo=raspberry-pi&logoColor=white)](https://raspberrypi.org)
[![Dataset](https://img.shields.io/badge/Dataset-NTHU--DDD_133K_images-22c55e)](https://github.com)
[![Licence](https://img.shields.io/badge/Licence-MIT-6366f1)](LICENSE)

</div>

---

## 🎬 Démo interactive

> **Aucun matériel requis pour tester.** La démo fonctionne directement dans le navigateur avec votre webcam.

```bash
# Ouvrir demo.html via VS Code Live Server (requis pour ES module + webcam)
# → Clic droit sur demo.html → Open with Live Server
```

La démo simule l'intégralité du système en temps réel :
- Détection somnolence par webcam (MediaPipe Face Landmarker)
- Calibration personnalisée automatique (~5 s)
- Machine à états alertes 1 → 2 → 3 → parking autonome RFID
- Choix du taux d'alcool au démarrage (blocage moteur si positif)

---

## 🎯 Concept

Un conducteur somnolent ou alcoolisé représente un danger immédiat. Ce système embarqué surveille en continu l'état du conducteur via **5 signaux biométriques indépendants** et réagit de manière graduée — de l'avertissement sonore jusqu'au stationnement autonome d'urgence.

```
Conducteur ──► Caméra ──► Raspberry Pi ──► Analyse IA ──► Arduino ──► Moteurs / Buzzer / LEDs
                                              │
                                    5 signaux fusionnés
                              EAR · HEAD · PERCLOS · BLINK · MAR
                                              │
                                   Score de fatigue 0-100
                                              │
                              ┌───────────────┼───────────────┐
                           Normal          Alertes 1-2-3     Parking auto
                                                               + RFID scan
```

---

## ✨ Fonctionnalités clés

### 🧠 Détection somnolence — 5 signaux indépendants

| Signal | Description | Méthode | Seuil |
|--------|-------------|---------|-------|
| **👁 EAR** | Fermeture des yeux (Eye Aspect Ratio) | 6 landmarks par œil — Soukupová & Čech 2016 | Calibré (baseline × 0.75) |
| **🔻 HEAD PITCH** | Inclinaison tête vers l'avant | Ratio nez/yeux/hauteur visage | Calibré (baseline + 0.08) |
| **📊 PERCLOS** | % frames yeux fermés sur 2 s | Fenêtre glissante 60 frames | **30 %** (NHTSA standard) |
| **👁‍🗨 BLINK RATE** | Clignements par minute | Détection transitions EAR, fenêtre 60 s | **< 10 /min** |
| **💬 MAR** | Bâillements (Mouth Aspect Ratio) | 8 landmarks bouche — Abtahi 2014 | 0.65 |

**Score de fatigue fusionné 0–100 :**
```
EAR(30) + HEAD PITCH(25) + PERCLOS(20) + BLINK RATE(15) + MAR(10)
```

### 🎯 Calibration personnalisée par conducteur

Au démarrage, le système mesure 150 frames (~5 s) pour calculer les seuils adaptés à **chaque conducteur** — morphologie, position de la caméra, conditions d'éclairage.

```
EAR seuil  = max(0.15,  moyenne_EAR  × 0.75)
HEAD seuil = min(0.55,  moyenne_HEAD + 0.08)
```

### 🚨 Machine à états graduée

```
                        ┌──── Réveil conducteur ◄────┐
                        │                            │
CALIBRATION ──► NORMAL ─┤                            │
                        │                        ALERTE 1 ──── [40 frames consécutives
                        │                            │          ou PERCLOS > 30%
                        │                            │          ou BLINK < 10/min]
                        │                        ALERTE 2 ──── [5 s sans réaction]
                        │                            │
                        │                        ALERTE 3 ──── [3 s sans réaction]
                        │                            │
                     BLOQUÉ                      PARKING ────── [Suivi ligne + RFID]
                  [Alcool > seuil]                   │
                                                   ARRÊT
```

### 🔐 Détection alcoolémie — blocage démarrage

Le capteur MQ-3 lit le taux d'alcool **avant** le démarrage. Si le seuil légal est dépassé, le relais coupe le circuit moteur et le démarrage est **physiquement impossible**.

```
ADC < 400    →  ✅ LED verte   — Démarrage autorisé
400 ≤ ADC < 650  →  ⚠️ LED jaune  — Attention, taux élevé
ADC ≥ 650    →  🚫 LED rouge  — BLOQUÉ — moteur coupé
```

---

## 🏗️ Architecture complète

```
┌─────────────────────────────────────────┐     UART 115200     ┌────────────────────────────────┐
│           Raspberry Pi 3/4              │ ◄──────────────────► │       Arduino Mega 2560        │
│                                         │   JSON 200 ms       │                                │
│  ┌─────────────────────────────────┐    │                      │  ┌─────────────────────────┐  │
│  │  main.py — Contrôleur principal │    │                      │  │  Capteurs               │  │
│  │  Machine à états 9 étapes       │    │                      │  │  MQ-3    → ADC A0       │  │
│  └──────────┬──────────────────────┘    │                      │  │  MFRC522 → SPI          │  │
│             │                           │                      │  │  TCRT5000 × 2 → A1, A2  │  │
│  ┌──────────▼──────────────────────┐    │                      │  └─────────────────────────┘  │
│  │  detection_somnolence.py        │    │                      │  ┌─────────────────────────┐  │
│  │  MediaPipe Face Mesh 468 pts    │    │                      │  │  Actionneurs            │  │
│  │  5 signaux + score 0-100        │    │                      │  │  L298N → D7–D12         │  │
│  │  Calibration personnalisée      │    │                      │  │  Buzzer  → D3 (PWM)     │  │
│  └──────────┬──────────────────────┘    │                      │  │  LEDs    → D4, D5, D6   │  │
│             │                           │                      │  │  OLED    → I2C D20–D21  │  │
│  ┌──────────▼──────────────────────┐    │                      │  └─────────────────────────┘  │
│  │  serial_comm.py                 │    │                      │                                │
│  │  Communication UART thread-safe │    │                      │  Firmware : voiture_securisee  │
│  └─────────────────────────────────┘    │                      │  Biblio : MFRC522, SSD1306,   │
│                                         │                      │           ArduinoJson          │
└─────────────────────────────────────────┘                      └────────────────────────────────┘
          │ USB / Pi Camera
          ▼
  [ Caméra conducteur — 640×480 30fps ]
```

**Mode simulation** disponible (sans aucun matériel) :
```bash
python main.py --simulate --scenario danger
# Scénarios : normal · somnolence · danger · alcool · mixte
```

---

## 📊 Validation scientifique des seuils — Dataset NTHU-DDD

Les seuils ne sont **pas arbitraires** : ils ont été validés par analyse ROC sur le dataset **NTHU-DDD Multi-Class** (133 042 images réelles de conducteurs, 35 sujets).

```
Pipeline de validation automatisé :
  .\telecharger_et_analyser.ps1
         │
         ├── Kaggle Hub → téléchargement NTHU-DDD (1.99 Go)
         ├── analyse_nthu.py → MediaPipe sur 8 000 images échantillonnées
         │       ├── Labellisation automatique (drowsy / notdrowsy)
         │       ├── Courbe ROC par métrique (EAR, MAR)
         │       └── Seuil optimal = Indice de Youden (argmax TPR − FPR)
         └── maj_seuils.py → mise à jour automatique du code
```

| Métrique | AUC ROC | Seuil Youden | Retenu | Justification |
|----------|---------|-------------|--------|---------------|
| **EAR** | **0.678** | **0.261** | ✅ | Cohérent littérature ; minimise faux négatifs (sécurité critique) |
| **MAR** | 0.454 | 0.655 | ⚠️ Défaut 0.65 | AUC < 0.5 : NTHU-DDD non centré sur bâillements → UTA-RLDD utilisé |
| **PERCLOS** | — | — | ✅ 30 % | Standard NHTSA ; validé sur base temporelle distincte |

> **Pourquoi Youden et pas F1-max ?**  
> Dans un système de sécurité, rater un conducteur endormi est catastrophique. L'indice de Youden maximise `TPR − FPR` pour le meilleur équilibre sensibilité/spécificité. Le seuil F1-optimal (0.384) déclencherait des alertes à demi-œil ouvert.

Sorties dans `raspberry/resultats_nthu/` : courbes ROC, distribution EAR, rapport complet.

---

## ⚡ Performances temps réel

| Plateforme | Latence inférence | FPS | Exigence SR6 (< 200 ms) |
|-----------|-------------------|-----|--------------------------|
| PC Windows | ~15–30 ms | ~35–65 fps | ✅ |
| **Raspberry Pi 4B** (1.8 GHz) | ~80–100 ms | ~10–12 fps | ✅ |
| **Raspberry Pi 3B** (1.2 GHz) | ~150–180 ms | ~6–7 fps | ✅ (limite) |

```bash
# Benchmark sur votre machine
python raspberry/benchmark_rpi.py --frames 200
```

> MediaPipe exploite l'accélération **XNNPACK NEON** sur ARM (optimisé RPi 4).  
> Sur RPi 3, résolution 320×240 recommandée (+40 % de performance).

---

## 🔧 Stack technique

```
Vision par ordinateur    MediaPipe Face Mesh · OpenCV · EAR / MAR / PERCLOS / Blink Rate
Machine d'états          Python · threading · UART JSON
Embarqué                 Raspberry Pi 3/4 · Arduino Mega 2560
Capteurs                 MQ-3 (alcool) · MFRC522 (RFID) · TCRT5000 (ligne) · Pi Camera
Actionneurs              L298N (moteurs) · SSD1306 (OLED) · Buzzer PWM · LEDs
Validation               NTHU-DDD · UTA-RLDD · ROC · Youden Index
```

---

## 📁 Structure du projet

```
voiture-robot-intelligente/
│
├── demo.html                          ← 🎬 Démo interactive navigateur (webcam + MediaPipe)
│
├── arduino/
│   └── voiture_securisee/
│       └── voiture_securisee.ino     ← Firmware Arduino Mega (MQ-3, RFID, moteurs, OLED)
│
├── raspberry/
│   ├── main.py                       ← Contrôleur principal — machine à états 9 étapes
│   ├── detection_somnolence.py       ← 5 signaux · calibration · score fatigue 0-100
│   ├── serial_comm.py                ← Communication UART thread-safe
│   ├── simulation.py                 ← Mode simulation — 5 scénarios sans matériel
│   ├── dataset_info.py               ← Documentation datasets + seuils justifiés
│   ├── analyse_nthu.py               ← Pipeline validation ROC + Youden sur NTHU-DDD
│   ├── maj_seuils.py                 ← Patch automatique des seuils
│   ├── benchmark_rpi.py              ← Benchmark latence MediaPipe
│   ├── telecharger_et_analyser.ps1   ← Automation complète Windows (Kaggle → seuils)
│   ├── face_landmarker.task          ← Modèle MediaPipe Tasks (~5 Mo)
│   ├── resultats_nthu/               ← ROC curves · distribution EAR · rapport
│   └── requirements.txt
│
├── securite/
│   ├── detection_somnolence.py       ← Module compatibilité (redirige vers raspberry/)
│   ├── detection_alcoolemie.py       ← Lecture MQ-3 · blocage relais GPIO
│   └── securite_active.py           ← Intégration somnolence + alcoolémie (threads)
│
├── arduino/
│   └── voiture_securisee.ino
│
└── docs/
    └── screenshot_robot.png
```

---

## 🚀 Installation & Lancement

### Prérequis

```bash
pip install -r raspberry/requirements.txt
# opencv-python · mediapipe · numpy · scipy
```

### Arduino

1. Ouvrir `arduino/voiture_securisee/voiture_securisee.ino` dans l'IDE Arduino
2. Bibliothèques à installer : `MFRC522`, `Adafruit_SSD1306`, `ArduinoJson`
3. Sélectionner **Arduino Mega 2560** → Téléverser

### Raspberry Pi — Système complet

```bash
git clone https://github.com/vanellemangoua/voiture-robot-intelligente.git
cd voiture-robot-intelligente/raspberry

# Lancement réel (Arduino branché)
python main.py --port /dev/ttyAMA0 --camera 0

# Mode debug — fenêtre caméra + logs détaillés
python main.py --debug

# Mode simulation — aucun matériel requis
python main.py --simulate --scenario somnolence
# Scénarios disponibles : normal · somnolence · danger · alcool · mixte
```

### Démo navigateur

```bash
# Ouvrir demo.html avec VS Code Live Server
# (obligatoire : ES module MediaPipe + accès webcam nécessitent HTTP)
```

---

## 📡 Protocole Arduino ↔ Raspberry Pi

**Arduino → RPi** — JSON toutes les 200 ms :
```json
{"mq3": 450, "rfid": false, "btn": false, "mot": true}
```

**RPi → Arduino** — Commandes texte :

| Commande | Effet Arduino |
|----------|--------------|
| `CMD:AUTORISER` | Moteurs ON · LED verte · OLED "AUTORISÉ" |
| `CMD:BLOQUER` | Moteurs OFF · LED rouge · OLED "ALCOOL DÉTECTÉ" |
| `CMD:ALERTE:1` | Bip court · LED jaune · OLED "SOMNOLENCE" |
| `CMD:ALERTE:2` | Bip long · LED orange · OLED "VOUS DORMEZ ?" |
| `CMD:ALERTE:3` | Sirène · LED rouge · OLED "URGENCE" |
| `CMD:PARKING` | Suivi ligne autonome + arrêt sur tag RFID |
| `CMD:RESET` | Arrêt total |

---

## ⚠️ Limites documentées

*Les connaître fait partie de la démarche d'ingénierie.*

**AUC modérée (0.678 pour EAR).** Le dataset NTHU-DDD est en conditions contrôlées. En conditions réelles (éclairage variable, lunettes de soleil, barbe, angle non frontal), les performances seront différentes. Une AUC > 0.85 nécessiterait un fine-tuning sur données de conduite réelle.

**MAR non discriminant sur NTHU-DDD.** Ce dataset est centré sur la fermeture des yeux, pas sur les bâillements. Le seuil MAR (0.65) provient de la littérature (UTA-RLDD / Abtahi 2014), pas d'une validation sur ce corpus.

**Raspberry Pi 3B en limite.** À 6–7 fps, des micro-somnolences très brèves (< 300 ms) peuvent être manquées. Le RPi 4B est recommandé pour une utilisation réelle.

**Non testé en conditions de conduite réelle.** Vibrations, soleil direct, lunettes de soleil — étape suivante naturelle du projet.

---

## 📚 Références scientifiques

| Auteurs | Année | Contribution |
|---------|-------|-------------|
| Soukupová & Čech | 2016 | *Real-Time Eye Blink Detection using Facial Landmarks* — base de l'EAR |
| Wierwille & Ellsworth + NHTSA | 1994 | Standard PERCLOS — indicateur de référence industrie |
| Abtahi et al. | 2014 | *YAWdd: a Yawning Detection Dataset* — seuil MAR 0.65 |
| NTHU (Weng et al.) | 2016 | Dataset NTHU-DDD — 35 sujets, 133 042 images, 4 ethnies |
| UTA-RLDD (Ghoddoosian et al.) | 2019 | 60 sujets en conditions réelles (lunettes, barbe, éclairage variable) |
| Reddy et al. | 2017 | Calibration EAR personnalisée par conducteur |

---

## 📝 Contexte

Projet académique — **ESIEA**, Systèmes Embarqués  
Auteur : **Vanelle Stéphanie MANGOUA**

Combine traitement d'image temps réel (Raspberry Pi · OpenCV · MediaPipe · 468 landmarks 3D), contrôle matériel bas-niveau (Arduino Mega · MQ-3 · MFRC522 · L298N) et validation scientifique sur datasets de recherche réels (NTHU-DDD · UTA-RLDD).
