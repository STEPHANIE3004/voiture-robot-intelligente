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
**Détection somnolence · Contrôle alcoolémie · Stationnement autonome d’urgence**

<br>

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-AI-ff6f00?style=for-the-badge&logo=google&logoColor=white)](https://mediapipe.dev)
[![Arduino](https://img.shields.io/badge/Arduino-Mega_2560-00979d?style=for-the-badge&logo=arduino&logoColor=white)](https://arduino.cc)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry_Pi-3%2F4-c51a4a?style=for-the-badge&logo=raspberry-pi&logoColor=white)](https://raspberrypi.org)

[![Dataset](https://img.shields.io/badge/Validé_sur-NTHU--DDD_133K_images-22c55e?style=flat-square)](https://github.com)
[![Norme](https://img.shields.io/badge/Norme_EAD-EN_50436-f59e0b?style=flat-square)](https://www.en-standard.eu)
[![ADAS](https://img.shields.io/badge/Timing-ADAS_Bosch%2FarXiv_2408.05836-8b5cf6?style=flat-square)](https://arxiv.org/abs/2408.05836)
[![Licence](https://img.shields.io/badge/Licence-MIT-6366f1?style=flat-square)](LICENSE)

</div>

---

## 💡 C’est quoi ce projet ?

La somnolence au volant est responsable de **20 à 30 % des accidents mortels** sur autoroute. Ce projet implémente un système embarqué qui surveille le conducteur en temps réel via une caméra, détecte les signes de fatigue ou d’alcoolémie, et prend le contrôle du véhicule si nécessaire — **sans aucune connexion à internet**.

Le système est entièrement autonome : il tourne sur un **Raspberry Pi** couplé à un **Arduino Mega 2560**, lit 5 signaux biométriques du visage du conducteur à 30 images par seconde, et peut déclencher un stationnement automatique d’urgence si le conducteur ne réagit plus.

**Une démo interactive dans le navigateur** permet de tester l’intégralité du système avec sa propre webcam, sans aucun matériel.

---

## 🎬 Démo — testez en 2 minutes, aucun install

<div align="center">

| Étape | Action |
|:-----:|--------|
| **1** | Cloner le dépôt |
| **2** | Ouvrir `demo.html` via **VS Code Live Server** *(obligatoire : la webcam nécessite HTTP)* |
| **3** | Choisir votre profil → calibration 5 s → surveillance en temps réel |

</div>

Ce que la démo fait réellement :

- ✅ Calibration personnalisée sur **150 images (~5 s)** — les seuils s’adaptent à votre visage
- ✅ **5 signaux biométriques** analysés en temps réel, fusionnés en score de fatigue 0–100
- ✅ **3 chemins de détection indépendants** pour déclencher l’alerte (yeux, PERCLOS, fréquence de clignement)
- ✅ Cascade d’alertes complète : Normal → Alerte 1 → Alerte 2 → **Alerte 3 (irréversible) → Pilotage automatique**
- ✅ Protocole alcool complet : souffler → blocage 30 s → retest → retour au menu conducteur
- ✅ Simulation de stationnement autonome en 5 phases avec animation, arrêt définitif

---

## 🧠 Comment la fatigue est-elle détectée ?

Le système analyse simultanément **5 signaux extraits du visage** à chaque image capturée par la caméra. Chacun mesure un aspect différent de la vigilance du conducteur.

### Les 5 signaux et leur rôle

| Signal | Ce que ça mesure | Méthode | Seuil d’alerte |
|--------|-----------------|---------|----------------|
| 👁 **EAR** *(Eye Aspect Ratio)* | Fermeture des yeux | Rapport géométrique entre 6 points autour de l’œil | `baseline × 0.75` (calibré) |
| 🔻 **HEAD PITCH** | Tête qui tombe vers l’avant | Ratio position nez / yeux / hauteur du visage | `baseline + 0.08` (calibré) |
| 📊 **PERCLOS** | % du temps les yeux sont fermés sur 2 s | Fenêtre glissante de 60 images | **> 30 %** (norme NHTSA) |
| 👁‍🗨 **BLINK RATE** | Nombre de clignements par minute | Comptage sur la dernière minute | **< 10/min** |
| 💬 **MAR** *(Mouth Aspect Ratio)* | Bâillements | Rapport géométrique de 8 points autour de la bouche | **> 0.65** |

> **EAR, MAR** sont des formules géométriques calculées à partir des 478 points du visage détectés par MediaPipe — aucun modèle entraîné sur des visages «somnolents», tout est calculé mathématiquement.

### Score de fatigue en temps réel

Les 5 signaux contribuent chacun à un **score de fatigue affiché de 0 à 100** :

```
  EAR (yeux fermés?)  →  +30 pts
  HEAD (tête tombée?) →  +25 pts
  PERCLOS             →  jusqu’à +20 pts  (proportionnel au %)
  BLINK RATE          →  jusqu’à +15 pts  (proportionnel au déficit)
  MAR (bâillement?)   →  +10 pts
                         ───────
                         Max 100 pts
```

### 3 chemins indépendants pour déclencher l’Alerte 1

Le score est un indicateur visuel. La logique de déclenchement d’alerte, elle, utilise 3 chemins distincts — ce qui rend le système bien plus robuste :

```
  CHEMIN 1 — EAR / HEAD PITCH
  Yeux fermés OU tête tombée pendant 40 images consécutives (~1,3 s)
  → C’est le signal principal, visible sur la barre de progression

  CHEMIN 2 — PERCLOS  (déclenche directement, sans attendre 40 images)
  Plus de 30 % des images des 2 dernières secondes : yeux fermés
  → Détecte les micro-endormissements, même si la tête reste droite

  CHEMIN 3 — BLINK RATE  (déclenche directement)
  Moins de 10 clignements par minute
  → Détecte la baisse de vigilance AVANT que les yeux ne se ferment
```

> ⚠️ Le **MAR** (bâillement) contribue au score et incrémente un compteur affiché, mais ne déclenche pas d’alerte seul — un bâillement isolé est tout à fait normal.

### Pourquoi une calibration personnalisée ?

Les seuils EAR et HEAD ne sont pas fixes : ils sont **mesurés sur votre propre visage** pendant 5 secondes au démarrage.

```python
EAR_seuil  = max(0.15,  moyenne_EAR  × 0.75)   # plancher de sécurité
HEAD_seuil = min(0.55,  moyenne_HEAD + 0.08)    # plafond anti-faux-positifs
```

Sans ça, un conducteur aux yeux naturellement petits serait en alerte permanente. Une période de grâce de **3 secondes** suit la calibration pour laisser les buffers PERCLOS et blink rate se remplir avant d’autoriser les alertes.

---

## 🚨 Cascade d’alertes — du signal à l’action

Le système réagit de façon **graduée** : d’abord un avertissement discret, puis de plus en plus fort, jusqu’au pilotage automatique si le conducteur ne réagit jamais.

```
                                 +==============+
                                 | CALIBRATION  |  <- 5 secondes, yeux ouverts
                                 +======+========+
                                        |
                                 +======v=======+
                                 |     IDLE     |  <- attend le demarrage
                                 +======+========+
                                        | bouton presse
                                 +======v=======+
                                 | VERIFICATION |  <- lecture capteur alcool MQ-3
                                 +======+========+
                        +---------------+------------------+
                    alcool OK                         alcool > seuil
                        |                                   |
                 +======v======+                   +========v========+
                 |   CONDUITE  |                   |     BLOQUE      |
                 |  autorisee  |                   |  30 min lock    |
                 +======+======+                   |  retest -> menu |
                        |                          +=================+
         +--------------+----------------+
    EAR/HEAD 40 img   PERCLOS>30%   BLINK<10/min
         +--------------+----------------+
                 +======v======+
                 |  ALERTE 1   |  -> bip court + LED jaune
                 +======+======+
       reveil <--------- |  --------------------------> retour CONDUITE
                         | 4 s sans reaction
                 +======v======+
                 |  ALERTE 2   |  -> bip long + LED orange + ecran "VOUS DORMEZ ?"
                 +======+======+
       reveil <--------- |  --------------------------> retour CONDUITE
                         | 4 s sans reaction
                 +======v======+
                 |  ALERTE 3   |  -> sirene + LED rouge
                 |  [1,3 s]    |  <- aucune recuperation possible
                 +======+======+
                         | automatique apres 1,3 s
                 +======v======+
                 |  PILOTAGE   |  -> camera coupee, overlay plein ecran
                 |    AUTO     |
                 +======+======+
                         | animation 5 phases
                 +======v======+
                 |    ARRET    |  <- arret definitif, aucun reset
                 +=============+
```

### Timing des transitions

| Transition | Durée | Pourquoi cette valeur |
|------------|:-----:|-----------------------|
| Conduite → Alerte 1 (EAR/HEAD) | **~1,3 s** | 40 images à 30 fps — standard académique (arXiv 2408.05836) |
| Conduite → Alerte 1 (PERCLOS/BLINK) | **immédiat** | Dès que le seuil est franchi |
| Alerte 1 → Alerte 2 | **4 s** | Temps de réaction moyen : 1,5–2 s · microsommeil : jusqu’à 15 s |
| Alerte 2 → Alerte 3 | **4 s** | Fenêtre d’intervention ADAS totale : 5–8 s (Bosch / Valeo / Mobileye) |
| Alerte 3 → Pilotage | **1,3 s** | Affichage visible avant engagement — irréversible |
| Alerte 1 ou 2 → Conduite | **immédiat** | Dès que EAR > seuil (conducteur a rouvert les yeux) |

---

## 🔐 Protocole alcool — Norme EN 50436

L’Éthylotest Anti-Démarrage (EAD) est une **norme européenne réelle** (EN 50436-1/2). Le système l’implémente fidèlement avec le capteur MQ-3.

```
  Conducteur souffle dans le capteur MQ-3
           |
    +-------+-------------------------------------+
    | Niveau OK      (ADC < 400)                  | -> OK  Conduite autorisee
    | Niveau eleve   (400 <= ADC < 650)           | -> Avertissement, tolere
    | Niveau illegal (ADC >= 650)                 | -> BLOQUE - Moteurs coupes
    +---------------------------------------------+
              | si bloque
    +---------v-----------------------------------------+
    |  BLOCAGE 30 min (norme EN 50436)                  |
    |  - Compte a rebours affiche en direct             |
    |  - Relais moteur maintenu ouvert (hardware)       |
    |  - Aucun bouton "recommencer"                     |
    +------------------+---------------------------------+
                       | delai ecoule
               +-------v----------+
               |   Nouveau test   |
               +-------+----------+
          positif       |              negatif
                        |                 |
              +30 min de blocage    Retour au menu
                                  (conducteur reconfirme lui-meme)
```

---

## 🛸 Pilotage automatique — ce qui se passe à l’Alerte 3

Une fois l’Alerte 3 déclenchée, après 1,3 s d’affichage irréversible, le système prend entièrement le contrôle :

```
  Camera coupee - Interface de surveillance masquee
  Overlay plein ecran active
         |
         +-- Animation canvas vue aerienne - 5 phases en temps reel :
         |       Phase 1 - Scan radar de la zone
         |       Phase 2 - Detection d'une place disponible
         |       Phase 3 - Calcul et suivi de la trajectoire
         |       Phase 4 - Validation RFID de la place
         |       Phase 5 - Arret moteurs confirme
         |
         +-- Journal horodate en direct + ecran de fin sans reset
                 -> Realisme : urgence medicale = immobilisation definitive
```

Sur le vrai véhicule : suivi de ligne par capteurs TCRT5000, validation par tag RFID (MFRC522), timeout 45 s si aucune place trouvée.

---

## 🏗️ Architecture matérielle

```
+-------------------------------------+   UART 115 200 bauds   +-----------------------------------+
|         Raspberry Pi 3 / 4          | <--------------------> |       Arduino Mega 2560           |
|                                     |   JSON toutes 200 ms   |                                   |
|  main.py                            |                         |  CAPTEURS                        |
|  -> Controleur principal            |                         |  MQ-3      -> A0  (alcool)       |
|  -> Machine a etats 9 etapes        |                         |  MFRC522   -> SPI (RFID parking) |
|  -> Protocole EAD EN 50436          |                         |  TCRT5000  -> A1, A2 (ligne)     |
|                                     |                         |  Bouton    -> D2  (demarrage)    |
|  detection_somnolence.py            |                         |                                   |
|  -> MediaPipe Face Mesh (468 pts)   |                         |  ACTIONNEURS                     |
|  -> 5 signaux + calibration         |                         |  L298N  -> D7-D12 (moteurs)      |
|  -> Score fatigue 0-100             |                         |  Buzzer -> D3  (PWM)             |
|                                     |                         |  LEDs   -> D4, D5, D6            |
|  serial_comm.py                     |                         |  OLED   -> I2C D20-D21           |
|  -> UART thread-safe                |                         |                                   |
+-------------------------------------+                        +-----------------------------------+
               | USB / Pi Camera
               v
   [ Camera conducteur - 640 x 480 - 30 fps ]
```

> La démo navigateur utilise **MediaPipe Face Landmarker** (JS, 478 points) chargé depuis CDN. Le code Raspberry Pi utilise **MediaPipe Face Mesh** (Python, 468 points) avec le modèle embarqué localement — aucune connexion internet requise en production.

**Tester sans matériel :**
```bash
python main.py --simulate --scenario danger
# Autres scénarios : normal · somnolence · alcool · mixte
```

---

## 📊 Validation sur dataset académique — NTHU-DDD

Les seuils retenus ont été validés sur le **NTHU Driver Drowsiness Detection dataset** : 133 042 images, 35 conducteurs, 4 ethnies.

```
  Script : telecharger_et_analyser.ps1
  +-- Telecharge NTHU-DDD via Kaggle Hub (1,99 Go)
  +-- analyse_nthu.py -> MediaPipe sur 8 000 images echantillonnees
  |       +-- Courbes ROC par signal
  |       +-- Seuil optimal = Indice de Youden (meilleur compromis detection / faux positifs)
  +-- maj_seuils.py -> met a jour automatiquement le code source
```

| Métrique | AUC ROC | Seuil retenu | Validé | Note |
|----------|:-------:|:------------:|:------:|------|
| **EAR** | **0.678** | **0.261** | ✅ | Cohérent littérature — minimise les faux négatifs (sécurité critique) |
| **MAR** | 0.454 | 0.655 | ✅ | AUC modeste mais seuil confirmé par Abtahi 2014 |
| **HEAD** | — | calibré | ✅ | Pas de seuil universel possible — calibration individuelle |
| **PERCLOS** | — | 30 % | ✅ | Standard NHTSA — indépendant du dataset |
| **BLINK** | — | 10 /min | ✅ | Consensus clinique somnolence |

> L’AUC EAR de 0.678 (contre > 0.85 en littérature) s’explique par l’absence de calibration individuelle dans NTHU-DDD — ce qui confirme précisément l’intérêt de la calibration personnalisée de ce projet.

---

## 📁 Structure du projet

```
voiture-robot-intelligente/
|
+-- demo.html                        <- Demo navigateur complete (webcam, zero install)
|
+-- raspberry/                       <- Code Raspberry Pi
|   +-- main.py                      <- Controleur principal (machine a etats 9 etapes)
|   +-- detection_somnolence.py      <- Moteur IA : 5 signaux + calibration + alertes
|   +-- serial_comm.py               <- Communication UART thread-safe avec Arduino
|   +-- simulation.py                <- Simulateur materiel (tester sans RPi)
|   +-- face_landmarker.task         <- Modele MediaPipe embarque (hors-ligne)
|   +-- requirements.txt             <- Dependances Python
|   +-- analyse_nthu.py              <- Validation seuils sur NTHU-DDD
|   +-- maj_seuils.py                <- Patch automatique seuils post-analyse
|   +-- telecharger_et_analyser.ps1  <- Telechargement + analyse NTHU-DDD
|
+-- arduino/
|   +-- voiture_securisee/
|       +-- voiture_securisee.ino   <- Firmware Arduino Mega 2560
|
+-- securite/                        <- Module securite active
+-- simulation/                      <- Scenarios de test avances
+-- docs/                            <- Documentation technique
```

---

## 🚀 Lancer le projet

### Démo navigateur (recommandé — zéro dépendance)

```bash
git clone https://github.com/<votre-username>/voiture-robot-intelligente
cd voiture-robot-intelligente
# Ouvrir demo.html avec VS Code -> bouton "Go Live"
# Ne pas ouvrir en double-cliquant (file://) - la webcam exige HTTP
```

### Raspberry Pi

```bash
pip install -r raspberry/requirements.txt
python raspberry/main.py

# Sans Arduino connecte :
python raspberry/main.py --simulate --scenario somnolence
```

### Arduino Mega 2560

Ouvrir `arduino/voiture_securisee/voiture_securisee.ino` dans l’IDE Arduino et flasher.
Bibliothèques requises : `MFRC522` · `Adafruit SSD1306` · `Adafruit GFX` · `ArduinoJson`

---

## 🔧 Paramètres clés du système

| Constante | Valeur | Signification |
|-----------|:------:|---------------|
| `CALIB_FRAMES` | 150 | Images de calibration (~5 s) |
| `POST_CALIB_GRACE` | 3 s | Attente post-calibration (stabilisation buffers) |
| `FAT_FRAMES` | 40 | Images fatigue consécutives avant Alerte 1 (~1,3 s) |
| `EAR_FACTOR` | × 0.75 | Seuil yeux = `max(0.15, baseline × 0.75)` |
| `HEAD_OFFSET` | + 0.08 | Seuil tête = `min(0.55, baseline + 0.08)` |
| `PERCLOS_ALERT` | 30 % | Seuil PERCLOS → Alerte 1 directe (NHTSA) |
| `BLINK_LOW` | 10 /min | Seuil clignements → Alerte 1 directe |
| `MAR_THR` | 0.65 | Seuil bâillement (score uniquement) |
| `ALERTE2_MS` | 4 000 ms | Délai Alerte 1 → Alerte 2 |
| `ALERTE3_MS` | 4 000 ms | Délai Alerte 2 → Alerte 3 |
| `ALERTE3_HOLD_MS` | 1 300 ms | Affichage Alerte 3 avant pilotage (irréversible) |
| `DUREE_BLOCAGE_S` | 1 800 s | Blocage EAD (30 min — EN 50436) |

---

## 📚 Références

| Source | Utilisation |
|--------|-------------|
| Soukupová & Čech (2016) — *Real-Time Eye Blink Detection using Facial Landmarks* | Formule EAR, 6 landmarks / œil |
| Abtahi et al. (2014) — *YawDD: A yawning detection dataset* | Formule MAR, seuil 0.65 |
| NHTSA — *PERCLOS: A Valid Psychophysiological Measure of Alertness* | Seuil PERCLOS 30 % |
| arXiv 2408.05836 — *Driver Drowsiness Detection Systems* | Timing Alerte 1→2 (4 s) |
| Bosch / Valeo / Mobileye — spécifications ADAS | Fenêtre d’intervention totale 5–8 s |
| Norme EN 50436-1/2 — *Alcohol Interlock Systems* | Protocole EAD complet |
| Weng et al. — *NTHU-DDD Dataset* | Validation seuils (133 042 images) |

---

## 🛠️ Technologies

**Python 3.9+** · **MediaPipe** (Face Mesh / Face Landmarker) · **OpenCV** · **NumPy** · **pyserial** · **JavaScript ES2022** · **Arduino C++** · **UART / JSON** · **I2C** · **SPI** · **PWM**

---

## 👩‍💻 Auteure

**Vanelle Stéphanie MANGOUA** — Recherche d’alternance en IA & Systèmes Embarqués
