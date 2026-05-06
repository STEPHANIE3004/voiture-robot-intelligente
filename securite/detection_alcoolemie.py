"""
Détection d'alcoolémie temps réel — Capteur MQ-3
=================================================
Lit la tension analogique du capteur MQ-3 via ADC (MCP3008)
sur Raspberry Pi et bloque le démarrage du véhicule si le seuil
est dépassé.

Matériel : Raspberry Pi + MQ-3 + MCP3008 (ADC SPI)
Dépendances : pip install spidev RPi.GPIO
"""

import time

# ── Paramètres ────────────────────────────────────────────────────────────────
SEUIL_ALERTE   = 400    # Valeur ADC (0–1023) correspondant à ~0.5 mg/L air
SEUIL_DANGER   = 650    # Valeur ADC correspondant à ~0.8 mg/L air (limite légale)
CANAL_ADC      = 0      # Canal MCP3008 connecté au MQ-3
GPIO_LED_VERT  = 22     # OK
GPIO_LED_JAUNE = 23     # Attention
GPIO_LED_ROUGE = 24     # Danger — blocage
GPIO_BUZZER    = 17
GPIO_RELAIS    = 25     # Relais coupant le circuit de démarrage

INTERVALLE_MS  = 500    # Lecture toutes les 500 ms

def lire_adc(canal):
    """Lecture MCP3008 via SPI."""
    try:
        import spidev
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1350000
        adc = spi.xfer2([1, (8 + canal) << 4, 0])
        spi.close()
        return ((adc[1] & 3) << 8) + adc[2]
    except ImportError:
        # Simulation hors Raspberry Pi
        import random
        return random.randint(200, 800)

def init_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        for pin in [GPIO_LED_VERT, GPIO_LED_JAUNE, GPIO_LED_ROUGE, GPIO_BUZZER, GPIO_RELAIS]:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(GPIO_LED_VERT, GPIO.HIGH)   # Vert par défaut
        GPIO.output(GPIO_RELAIS, GPIO.HIGH)      # Démarrage autorisé par défaut
    except ImportError:
        print("[INFO] Mode simulation (pas de Raspberry Pi)")

def set_etat(valeur_adc):
    """
    Applique l'état des LEDs, buzzer et relais selon la valeur ADC.
    Retourne True si démarrage bloqué.
    """
    try:
        import RPi.GPIO as GPIO
        GPIO.output(GPIO_LED_VERT,  GPIO.LOW)
        GPIO.output(GPIO_LED_JAUNE, GPIO.LOW)
        GPIO.output(GPIO_LED_ROUGE, GPIO.LOW)
        GPIO.output(GPIO_BUZZER,    GPIO.LOW)

        if valeur_adc < SEUIL_ALERTE:
            GPIO.output(GPIO_LED_VERT,  GPIO.HIGH)
            GPIO.output(GPIO_RELAIS,    GPIO.HIGH)  # Démarrage OK
            print(f"[OK]      ADC={valeur_adc:4d} — Taux normal")
            return False

        elif valeur_adc < SEUIL_DANGER:
            GPIO.output(GPIO_LED_JAUNE, GPIO.HIGH)
            GPIO.output(GPIO_RELAIS,    GPIO.HIGH)
            GPIO.output(GPIO_BUZZER,    GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(GPIO_BUZZER,    GPIO.LOW)
            print(f"[ALERTE]  ADC={valeur_adc:4d} — Taux élevé, soyez vigilant")
            return False

        else:
            GPIO.output(GPIO_LED_ROUGE, GPIO.HIGH)
            GPIO.output(GPIO_RELAIS,    GPIO.LOW)   # Blocage démarrage !
            GPIO.output(GPIO_BUZZER,    GPIO.HIGH)
            print(f"[DANGER]  ADC={valeur_adc:4d} — ALCOOLÉMIE DÉTECTÉE — Démarrage bloqué !")
            return True

    except ImportError:
        # Simulation console
        if valeur_adc < SEUIL_ALERTE:
            print(f"[OK]      ADC={valeur_adc:4d} — Taux normal")
        elif valeur_adc < SEUIL_DANGER:
            print(f"[ALERTE]  ADC={valeur_adc:4d} — Taux élevé")
        else:
            print(f"[DANGER]  ADC={valeur_adc:4d} — BLOCAGE démarrage !")
        return valeur_adc >= SEUIL_DANGER

def main():
    init_gpio()
    print("[INFO] Détection alcoolémie active — MQ-3")
    print(f"       Seuil alerte : {SEUIL_ALERTE} | Seuil danger : {SEUIL_DANGER}")
    print("       Ctrl+C pour quitter\n")

    try:
        while True:
            valeur = lire_adc(CANAL_ADC)
            bloque = set_etat(valeur)
            time.sleep(INTERVALLE_MS / 1000.0)
    except KeyboardInterrupt:
        print("\n[INFO] Arrêt.")
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
        except ImportError:
            pass

if __name__ == "__main__":
    main()
