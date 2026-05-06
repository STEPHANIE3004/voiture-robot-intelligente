"""
Sécurité Active — Intégration somnolence + alcoolémie
======================================================
Lance les deux pipelines en parallèle (threads) et bloque
le démarrage si l'un ou l'autre détecte un risque.

Usage : python securite_active.py
"""

import threading
import time
import cv2
import numpy as np

# Import des modules locaux
from detection_somnolence import ear, OEIL_G_IDX, OEIL_D_IDX, EAR_SEUIL, FRAMES_ALERTE
from detection_alcoolemie  import lire_adc, SEUIL_DANGER, CANAL_ADC

# ── État partagé entre threads ────────────────────────────────────────────────
etat = {
    "somnolence": False,
    "alcoolemie": False,
}
lock = threading.Lock()

GPIO_RELAIS = 25

def set_relais(autoriser):
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
    """Thread de détection somnolence via caméra."""
    try:
        import dlib
        from imutils import face_utils
        detecteur  = dlib.get_frontal_face_detector()
        predicteur = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
    except Exception as e:
        print(f"[WARNING] dlib non disponible : {e} — thread somnolence désactivé")
        return

    cap      = cv2.VideoCapture(0)
    compteur = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        gris    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        visages = detecteur(gris, 0)

        detecte = False
        for visage in visages:
            shape  = predicteur(gris, visage)
            shape  = face_utils.shape_to_np(shape)
            oeil_g = shape[OEIL_G_IDX[0]:OEIL_G_IDX[1]]
            oeil_d = shape[OEIL_D_IDX[0]:OEIL_D_IDX[1]]
            ear_val = (ear(oeil_g) + ear(oeil_d)) / 2.0

            if ear_val < EAR_SEUIL:
                compteur += 1
                if compteur >= FRAMES_ALERTE:
                    detecte = True
            else:
                compteur = 0

        with lock:
            etat["somnolence"] = detecte

    cap.release()

def main():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_RELAIS, GPIO.OUT, initial=GPIO.HIGH)
    except ImportError:
        print("[INFO] Mode simulation")

    # Lancer les deux threads
    t1 = threading.Thread(target=thread_alcoolemie,  daemon=True)
    t2 = threading.Thread(target=thread_somnolence,  daemon=True)
    t1.start()
    t2.start()

    print("[INFO] Sécurité active démarrée — surveillance en cours...")
    print("       Ctrl+C pour quitter\n")

    try:
        while True:
            with lock:
                risque = etat["somnolence"] or etat["alcoolemie"]

            set_relais(not risque)

            if risque:
                raisons = []
                if etat["somnolence"]: raisons.append("SOMNOLENCE")
                if etat["alcoolemie"]: raisons.append("ALCOOLÉMIE")
                print(f"[DANGER] Démarrage bloqué — {' + '.join(raisons)}")
            else:
                print("[OK] Système nominal — démarrage autorisé")

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
