<div align="center">

```
██╗   ██╗ ██████╗ ██╗████████╗██╗   ██╗██████╗ ███████╗
██║   ██║██╔═══██╗██║╚══██╔══╝██║   ██║██╔══██╗██╔════╝
██║   ██║██║   ██║██║   ██║   ██║   ██║██████╔╝█████╗  
╚██╗ ██╔╝██║   ██║██║   ██║   ██║   ██║██╔══██╗██╔══╝  
 ╚████╔╝ ╚██████╔╝██║   ██║   ╚██████╔╝██║  ██║███████╗
  ╚═══╝   ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝
        R O B O T   I N T E L L I G E N T E
```

### Système embarqué de sécurité active conducteur
**Détection somnolence · Contrôle alcoolémie · Stationnement autonome d'urgence**

<br>

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-AI-ff6f00?style=for-the-badge&logo=google&logoColor=white)](https://mediapipe.dev)
[![Arduino](https://img.shields.io/badge/Arduino-Mega_2560-00979d?style=for-the-badge&logo=arduino&logoColor=white)](https://arduino.cc)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-3%2F4-c51a4a?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://raspberrypi.org)

[![Dataset](https://img.shields.io/badge/Validé_sur-NTHU--DDD_133K_images-22c55e?style=flat-square)](https://github.com)
[![Norme](https://img.shields.io/badge/Norme_EAD-EN_50436-f59e0b?style=flat-square)](https://www.en-standard.eu)
[![ADAS](https://img.shields.io/badge/Timing-ADAS_Bosch%2FarXiv_2408.05836-8b5cf6?style=flat-square)](https://arxiv.org/abs/2408.05836)
[![Licence](https://img.shields.io/badge/Licence-MIT-6366f1?style=flat-square)](LICENSE)

<br>

> *Un conducteur somnolent tue. Ce projet embarque une IA de surveillance continue directement dans le véhicule —*  
> *de la détection au stationnement autonome d'urgence, sans dépendance au cloud.*

</div>

---

## 🎬 Démo interactive — aucun matériel requis

<div align="center">

| Étape | Action |
|:-----:|--------|
| **1** | Cloner le dépôt |
| **2** | Ouvrir `demo.html` via **VS Code Live Server** *(ES module + webcam = HTTP obligatoire)* |
| **3** | Choisir votre profil → calibration automatique → surveillance en temps réel |

</div>

Ce que la démo fait **réellement** :

- ✅ Calibration EAR personnalisée sur 150 frames (~5 s) — seuils adaptés à votre visage
- ✅ Fusion de **5 signaux biométriques** indépendants en score 0–100 en temps réel
- ✅ Machine à états complète : Normal → Alerte 1 → Alerte 2 → **Alerte 3 → Pilotage automatique**
- ✅ Protocole EAD complet : test alcool → blocage → countdown 30 s → retest → retour au choix conducteur
- ✅ Overlay plein écran de stationnement autonome avec animation canvas aérienne

---

## 🧠 Détection somnolence — 5 signaux indépendants

La force du système est la **fusion** : aucun signal seul ne déclenche une alerte — c'est le score combiné qui décide.

```
                    ┌─────────────────────────────────────────────────┐
  Caméra 30 fps ──► │          MediaPipe Face Mesh — 468 pts 3D       │
                    └──┬──────┬──────┬──────┬──────┬──────────────────┘
                       │      │      │      │      │
                      EAR   HEAD  PERCLOS BLINK   MAR
                      30%   25%    20%    15%    10%    ← pondération du score
                       │      │      │      │      │
                    └──┴──────┴──────┴──────┴──────┘
                                   │
                         Score de fatigue 0–100
                                   │
                    ┌──────────────┼──────────────┐
                  0–39           40–69          70–100
                 NORMAL         ALERTE          URGENCE
```

| Signal | Ce qu'il mesure | Méthode | Seuil |
|--------|-----------------|---------|-------|
| 👁 **EAR** | Fermeture des yeux | 6 landmarks / œil — Soukupová & Čech 2016 | `baseline × 0.75` calibré |
| 🔻 **HEAD PITCH** | Inclinaison tête avant | Ratio nez/yeux/hauteur visage | `baseline + 0.08` calibré |
| 📊 **PERCLOS** | % frames yeux fermés / 2 s | Fenêtre glissante 60 frames | **30 %** — standard NHTSA |
| 👁‍🗨 **BLINK RATE** | Clignements / minute | Détection transitions EAR, fenêtre 60 s | **< 10 /min** |
| 💬 **MAR** | Bâillements | 8 landmarks bouche — Abtahi 2014 | **0.65** |

### Calibration personnalisée par conducteur

```python
# 150 frames (~5 s), yeux grand ouverts → seuils adaptés à chaque morphologie
EAR_seuil  = max(0.15,  moyenne_EAR  × 0.75)
HEAD_seuil = min(0.55,  moyenne_HEAD + 0.08)

# Période de grâce 3 s post-calibration
# → élimine les fausses alertes dues au buffer PERCLOS vide
POST_CALIB_GRACE = 3.0  # secondes
```

---

## 🚨 Machine à états graduée — du signal à l'action

```
                                      ╔═════════════╗
                                      ║ CALIBRATION ║  ← 150 frames, ~5 s
                                      ╚══════╤══════╝
                                             │
                                      ╔══════▼══════╗
                                      ║    IDLE     ║  ← attend le bouton démarrage
                                      ╚══════╤══════╝
                                             │  bouton pressé
                                      ╔══════▼══════╗
                                      ║ VÉRIFICATION║  ← lecture MQ-3, 3 secondes
                                      ╚══════╤══════╝
                               ┌─────────────┴──────────────┐
                           alcool OK                    alcool > seuil
                               │                             │
                        ╔══════▼══════╗             ╔═══════▼════════╗
                        ║   AUTORISÉ  ║             ║     BLOQUÉ     ║  ← EN 50436
                        ║  conduite   ║             ║  30 min lock   ║  ← countdown
                        ╚══════╤══════╝             ║  retest → choix║
                               │ score ≥ 40         ╚════════════════╝
                        ╔══════▼══════╗
                        ║  ALERTE 1   ║  → bip court · LED jaune
                        ╚══════╤══════╝
              réveil ◄──────── │ ──────────────────────────────────► retour AUTORISÉ
                                │ 4 s sans réaction [arXiv 2408.05836]
                        ╔══════▼══════╗
                        ║  ALERTE 2   ║  → bip long · LED orange · OLED "VOUS DORMEZ ?"
                        ╚══════╤══════╝
              réveil ◄──────── │ ──────────────────────────────────► retour AUTORISÉ
                                │ 3,5 s sans réaction [Bosch ADAS]
                        ╔══════▼══════╗
                        ║  ALERTE 3   ║  → sirène · LED rouge
                        ║  PILOTAGE   ║  → overlay plein écran activé
                        ║    AUTO     ║  → webcam stoppée
                        ╚══════╤══════╝
                                │
                        ╔══════▼══════╗
                        ║   PARKING   ║  → suivi de ligne + détection tag RFID
                        ╚══════╤══════╝
                                │ RFID détecté  (ou timeout 45 s)
                        ╔══════▼══════╗
                        ║    ARRÊT    ║  ← arrêt définitif, aucun reset
                        ╚═════════════╝
```

### Timing des alertes — valeurs basées sur la recherche ADAS

| Transition | Délai | Justification |
|------------|:-----:|---------------|
| Alerte 1 → Alerte 2 | **4 000 ms** | Réaction conducteur à un avertissement : 1,5–2 s · microsommeil moyen : 0,5–15 s (arXiv 2408.05836) |
| Alerte 2 → Alerte 3 | **3 500 ms** | Fenêtre ADAS standard Bosch/Valeo/Mobileye : intervention totale à 5–8 s |
| Alerte 1 ou 2 → Normal | **immédiat** | Dès que le conducteur réouvre les yeux (EAR > seuil) |

---

## 🔐 Protocole EAD — Norme EN 50436

> L'Éthylotest Anti-Démarrage est une **norme européenne réelle** (EN 50436-1/2). L'implémentation suit son protocole.

```
  Conducteur souffle dans MQ-3
           │
    ┌──────┴───────────────┐
    │  ADC < 400           │ ──► ✅ LED verte — moteurs autorisés
    │  400 ≤ ADC < 650     │ ──► ⚠️  LED jaune — taux élevé, autorisé
    │  ADC ≥ 650           │ ──► 🚫 LED rouge — MOTEURS COUPÉS (relais physique)
    └──────────────────────┘
           │ (si bloqué)
    ┌──────▼──────────────────────────────────────┐
    │  BLOCAGE 30 min — EN 50436                  │
    │  • Countdown visuel affiché en temps réel   │
    │  • Log toutes les 5 min : X min restantes   │
    │  • Relais moteur maintenu ouvert (hardware) │
    └──────────────────┬──────────────────────────┘
                       │ délai écoulé
               ┌───────▼────────┐
               │  Retest MQ-3   │
               └───────┬────────┘
          encore positif│                    négatif
                        │                       │
              prolongé +30 min        Retour ÉCRAN DE CHOIX
                                   (pas de démarrage automatique —
                                    le conducteur re-confirme son état)
```

---

## 🛸 Mode Pilotage Automatique — Alerte Niveau 3

Quand l'Alerte 3 se déclenche, le système bascule en mode d'urgence total :

```
  [Alerte 3 déclenchée]
          │
          ├── Webcam stoppée  (stream.getTracks().stop())
          ├── Interface surveillance masquée
          └── Overlay plein écran activé
                  │
                  ├── Canvas aérien 490 × 300 px — animation temps réel
                  │       Phase 1 · 🔍 Scan de zone    (radar tournant)
                  │       Phase 2 · 🅿  Détection spot  (highlight)
                  │       Phase 3 · 🚗 Navigation       (arc de Bézier)
                  │       Phase 4 · 📡 Scan RFID        (validation)
                  │       Phase 5 · ✅ Arrêt confirmé
                  │
                  ├── Panneau de logs horodatés (#apLogBox)
                  ├── Barre de statut de phase (#apStatusRow)
                  └── Écran de fin (#apDoneCard)
                          └── Aucun bouton reset — arrêt DÉFINITIF
                              (réalisme : urgence médicale = immobilisation complète)
```

---

## 🏗️ Architecture complète

```
┌───────────────────────────────────────────┐   UART 115 200 baud   ┌────────────────────────────────────┐
│            Raspberry Pi 3 / 4             │ ◄───────────────────► │         Arduino Mega 2560          │
│                                           │   JSON toutes 200 ms  │                                    │
│  ┌─────────────────────────────────────┐  │                        │  ┌──────────────────────────────┐  │
│  │  main.py — Contrôleur principal     │  │                        │  │  CAPTEURS                    │  │
│  │  Machine à états 9 étapes           │  │                        │  │  MQ-3      → ADC A0          │  │
│  │  Protocole EAD EN 50436             │  │                        │  │  MFRC522   → SPI             │  │
│  └────────────────┬────────────────────┘  │                        │  │  TCRT5000  → A1, A2          │  │
│                   │                       │                        │  │  Bouton    → D2              │  │
│  ┌────────────────▼────────────────────┐  │                        │  └──────────────────────────────┘  │
│  │  detection_somnolence.py            │  │                        │  ┌──────────────────────────────┐  │
│  │  MediaPipe Face Mesh 468 pts 3D     │  │                        │  │  ACTIONNEURS                 │  │
│  │  EAR · HEAD · PERCLOS · BLINK · MAR │  │                        │  │  L298N  → D7–D12 (moteurs)   │  │
│  │  Calibration + grâce 3 s           │  │                        │  │  Buzzer → D3 (PWM)           │  │
│  │  Score fatigue 0–100               │  │                        │  │  LEDs   → D4, D5, D6         │  │
│  └────────────────┬────────────────────┘  │                        │  │  OLED   → I2C D20–D21        │  │
│                   │                       │                        │  └──────────────────────────────┘  │
│  ┌────────────────▼────────────────────┐  │                        │                                    │
│  │  serial_comm.py — UART thread-safe  │  │                        │  Biblio : MFRC522 · SSD1306        │
│  └─────────────────────────────────────┘  │                        │           ArduinoJson              │
└───────────────────────────────────────────┘                        └────────────────────────────────────┘
               │ USB / Pi Camera
               ▼
   [ Caméra conducteur — 640 × 480 · 30 fps ]
```

**Mode simulation** (sans aucun matériel) :
```bash
python main.py --simulate --scenario danger
# Scénarios disponibles : normal · somnolence · danger · alcool · mixte
```

---

## 📊 Validation scientifique — Dataset NTHU-DDD

Les seuils ne sont **pas arbitraires** : ils ont été validés sur le dataset académique de référence.

```
  .\telecharger_et_analyser.ps1
           │
           ├─ Kaggle Hub → NTHU-DDD (1,99 Go · 133 042 images · 35 sujets · 4 ethnies)
           ├─ analyse_nthu.py → MediaPipe sur 8 000 images échantillonnées
           │       ├─ Labellisation automatique (drowsy / notdrowsy)
           │       ├─ Courbe ROC par signal
           │       └─ Seuil optimal = Indice de Youden  (argmax TPR − FPR)
           └─ maj_seuils.py → patch automatique du code source
```

| Métrique | AUC ROC | Seuil Youden | Retenu | Justification |
|----------|:-------:|:------------:|:------:|---------------|
| **EAR** | **0.678** | **0.261** | ✅ | Cohérent littérature ; minimise faux négatifs (sécurité critique) |
| **MAR** | 0.454 | 0.655 | ⚠️ Déf