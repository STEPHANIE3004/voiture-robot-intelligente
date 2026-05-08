"""
[MIGRÉ] Détection de somnolence — Module de compatibilité
==========================================================
Ce fichier redirige vers le module principal MediaPipe dans raspberry/.

HISTORIQUE :
  Version initiale (dlib) — remplacée par MediaPipe Face Mesh
  pour de meilleures performances sur Raspberry Pi (sans .dat externe).

MIGRATION :
  Utiliser désormais : from raspberry.detection_somnolence import DetecteurSomnolence

DIFFÉRENCES AVEC L'ANCIENNE VERSION :
  - Ancien : dlib 68 landmarks, EAR seul, seuil fixe 0.25
  - Nouveau : MediaPipe 468 landmarks, 5 signaux (EAR + HEAD PITCH +
              PERCLOS + BLINK RATE + MAR), calibration personnalisée,
              score de fatigue 0-100

Auteur : Vanelle Stéphanie MANGOUA
"""

import sys
import os

# Permet d'importer raspberry/detection_somnolence.py depuis ce répertoire
_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from raspberry.detection_somnolence import (   # noqa: F401  (ré-export)
    DetecteurSomnolence,
    ear,
    mar,
    calcHeadPitch,
    calc_fatigue_score,
    extraire_points,
    estimer_head_pose,
    EAR_DEFAUT,
    EAR_FRAMES_SEUIL,
    MAR_SEUIL,
    PERCLOS_SEUIL,
    BLINK_LOW,
    DELAI_NV2,
    DELAI_NV3,
    IDX_OEIL_G,
    IDX_OEIL_D,
)

# Alias de rétrocompatibilité pour l'ancienne constante dlib
EAR_SEUIL     = EAR_DEFAUT          # était 0.25, maintenant 0.261 calibré
FRAMES_ALERTE = EAR_FRAMES_SEUIL    # était 20, maintenant 40
OEIL_G_IDX    = IDX_OEIL_G
OEIL_D_IDX    = IDX_OEIL_D
