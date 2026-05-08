"""
Sécurité Active — Intégration somnolence + alcoolémie
======================================================
Lance les deux pipelines en parallèle (threads) et bloque
le démarrage si l'un ou l'autre détecte un risque.

Détection somnolence : MediaPipe Face Mesh — 5 signaux indépendants
  EAR + HEAD PITCH + PERCLOS + BLINK RATE + MAR
  Score de fatigue fusionné 0-100
  Calibration personnalisée par conducteur

Détection alcoolémie : Capteur MQ-3 via ADC (MCP3008)
  Blocage si ADC ≥ SEUIL_DANGER (défaut 650)

Usage : python securite_active.py

Auteur : Vanelle Stéphanie MANGOUA
"""

import threading
import time
import logging

# Module principal MediaPipe (raspberry/)
from detection_somnolence import (
    DetecteurSomnolence,
    BLINK_LOW,
    PERCLOS_SEUIL,
)
from detection_alcoolemie import lire_adc, SEUIL_DANGER, CANAL_ADC

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ── État partagé entre threads ────────────────────────────────────────────────
etat = {
    "somnolence":    False,
    "alcoolemie":    False,
    "niveau":        0,
    "fatigue_score": 0.0,
    "blink_rate":    0,
    "perclos":       0.0,
}
lock = threading.Lock()

GPIO_RELAIS = 25


def set_relais(autoriser: bool):
    """Autorise ou bloque le démarrage selon l'état combiné."""
    try:
        import RPi.GPIO as GPIO
        GPIO.output(GPIO_RELAIS, GPIO.HIGH if autoriser else GPIO.LOW)
    except ImportError:
        statut = "AUTORISÉ" if autoriser else "BLOQUÉ"
        print(f"[RELAIS] Démarrage {statut}")


def thread_alcoolemie():
    """Thread de lecture continue du capteur MQ-3."""
    while True:
        valeur = lire_adc(CANAL_ADC)
        with lock:
            etat["alcoolemie"] = valeur >= SEUIL_DANGER
        time.sleep(0.5)


def thread_somnolence():
    """
    Thread de détection somnolence — MediaPipe + 5 signaux.
    Calibration personnalisée au démarrage.
    """
    detecteur = DetecteurSomnolence(camera_id=0)
    if not detecteur.initialiser():
        logger.error("Caméra inaccessible — thread somnolence désactivé")
        return

    # Calibration personnalisée
    logger.info("=== CALIBRATION — regardez la caméra, yeux ouverts, tête droite ===")
    seuil_ear = detecteur.calibrer(afficher=True)
    logger.info(
        f"Seuil EAR={seuil_ear:.3f}  "
        f"Seuil HEAD={detecteur.head_seuil:.3f}"
    )

    while True:
        res = detecteur.update()
        if res.get("erreur"):
            time.sleep(0.1)
            continue

        niveau        = res.get("niveau", 0)
        fatigue_score = res.get("fatigue_score", 0.0)
        blink_rate    = res.get("blink_rate", 0)
        perclos       = res.get("perclos", 0.0)

        with lock:
            etat["somnolence"]    = niveau >= 1
            etat["niveau"]        = niveau
            etat["fatigue_score"] = fatigue_score
            etat["blink_rate"]    = blink_rate
            etat["perclos"]       = perclos


def main():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_RELAIS, GPIO.OUT, initial=GPIO.HIGH)
    except ImportError:
        print("[INFO] Mode simulation (pas de Raspberry Pi détecté)")

    # Lancer les deux threads
    t1 = threading.Thread(target=thread_alcoolemie, daemon=True)
    t2 = threading.Thread(target=thread_somnolence,  daemon=True)
    t1.start()
    t2.start()

    print("[INFO] Sécurité active démarrée — surveillance en cours…")
    print("       Ctrl+C pour quitter\n")

    try:
        while True:
            with lock:
                risque        = etat["somnolence"] or etat["alcoolemie"]
                niveau        = etat["niveau"]
                fatigue_score = etat["fatigue_score"]
                blink_rate    = etat["blink_rate"]
                perclos       = etat["perclos"]

            set_relais(not risque)

            if risque:
                raisons = []
                if etat["alcoolemie"]: raisons.append("ALCOOLÉMIE")
                if etat["somnolence"]: raisons.append(f"SOMNOLENCE niv.{niveau}")
                print(
                    f"[DANGER] Démarrage bloqué — {' + '.join(raisons)} | "
                    f"Score={fatigue_score:.0f}/100  "
                    f"Blink={blink_rate}/min  "
                    f"PERCLOS={perclos:.0%}"
                )
            else:
                print(
                    f"[OK]     Système nominal — démarrage autorisé | "
                    f"Score={fatigue_score:.0f}/100  "
                    f"Blink={blink_rate}/min  "
                    f"PERCLOS={perclos:.0%}"
                )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Arrêt sécurité active.")
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except ImportError:
            pass


if __name__ == "__main__":
    main()
