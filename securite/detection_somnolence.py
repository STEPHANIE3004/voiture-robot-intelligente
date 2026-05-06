"""
Détection de somnolence en temps réel — OpenCV + dlib
======================================================
Analyse le flux caméra et calcule l'Eye Aspect Ratio (EAR)
pour détecter si le conducteur s'endort.

Matériel : Raspberry Pi + caméra USB ou Pi Camera
Dépendances : pip install opencv-python dlib imutils scipy
"""

import cv2
import dlib
import numpy as np
from scipy.spatial import distance
from imutils import face_utils
import time

# ── Paramètres ────────────────────────────────────────────────────────────────
EAR_SEUIL       = 0.25   # En dessous = œil fermé
FRAMES_ALERTE   = 20     # Nb de frames consécutives avant alerte
GPIO_BUZZER     = 17     # Pin GPIO buzzer (Raspberry Pi)
GPIO_LED_ALERTE = 27     # Pin GPIO LED rouge

# ── Indices landmarks yeux (dlib 68 points) ───────────────────────────────────
OEIL_G_IDX = (42, 48)
OEIL_D_IDX = (36, 42)

def ear(oeil):
    """Eye Aspect Ratio : mesure l'ouverture de l'œil."""
    A = distance.euclidean(oeil[1], oeil[5])
    B = distance.euclidean(oeil[2], oeil[4])
    C = distance.euclidean(oeil[0], oeil[3])
    return (A + B) / (2.0 * C)

def declencher_alerte(actif):
    """Active/désactive buzzer et LED via GPIO."""
    try:
        import RPi.GPIO as GPIO
        GPIO.output(GPIO_BUZZER, GPIO.HIGH if actif else GPIO.LOW)
        GPIO.output(GPIO_LED_ALERTE, GPIO.HIGH if actif else GPIO.LOW)
    except ImportError:
        # Hors Raspberry Pi — simulation console
        if actif:
            print("[ALERTE] SOMNOLENCE DÉTECTÉE — Blocage démarrage !")

def init_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_BUZZER, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(GPIO_LED_ALERTE, GPIO.OUT, initial=GPIO.LOW)
    except ImportError:
        print("[INFO] Mode simulation (pas de Raspberry Pi)")

def main():
    init_gpio()

    # Chargeur modèle dlib
    detecteur   = dlib.get_frontal_face_detector()
    predicteur  = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
    cap         = cv2.VideoCapture(0)
    compteur    = 0
    alerte_active = False

    print("[INFO] Démarrage détection somnolence...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gris   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        visages = detecteur(gris, 0)

        for visage in visages:
            shape = predicteur(gris, visage)
            shape = face_utils.shape_to_np(shape)

            oeil_g = shape[OEIL_G_IDX[0]:OEIL_G_IDX[1]]
            oeil_d = shape[OEIL_D_IDX[0]:OEIL_D_IDX[1]]
            ear_val = (ear(oeil_g) + ear(oeil_d)) / 2.0

            # Dessin landmarks
            cv2.drawContours(frame, [cv2.convexHull(oeil_g)], -1, (0, 255, 0), 1)
            cv2.drawContours(frame, [cv2.convexHull(oeil_d)], -1, (0, 255, 0), 1)
            cv2.putText(frame, f"EAR: {ear_val:.2f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if ear_val < EAR_SEUIL:
                compteur += 1
                if compteur >= FRAMES_ALERTE:
                    if not alerte_active:
                        declencher_alerte(True)
                        alerte_active = True
                    cv2.putText(frame, "SOMNOLENCE DETECTEE !", (10, 70),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                if alerte_active:
                    declencher_alerte(False)
                    alerte_active = False
                compteur = 0

        cv2.imshow("Détection Somnolence", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    declencher_alerte(False)

if __name__ == "__main__":
    main()
