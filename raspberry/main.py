"""
Voiture Robot Sécurisée — Machine à États Principale
=====================================================
Orchestre la détection de somnolence (MediaPipe) et d'alcoolémie (MQ-3)
et envoie les commandes correspondantes à l'Arduino.

Machine à états :
  CALIBRATION → IDLE → VERIFICATION → AUTORISE ←→ ALERTE(1,2,3) → PARKING → ARRET
                                    ↘ BLOQUE

Auteur  : Vanelle Stéphanie MANGOUA
Usage   :
  python main.py                        # mode réel
  python main.py --simulate             # mode simulation (sans matériel)
  python main.py --debug                # fenêtre caméra + logs détaillés
  python main.py --port /dev/ttyUSB0   # port série personnalisé
"""

import argparse
import logging
import sys
import time
import cv2
from enum import Enum, auto

from detection_somnolence import DetecteurSomnolence
from serial_comm import CommunicationSerie

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  États
# ════════════════════════════════════════════════════════════════════════════

class Etat(Enum):
    CALIBRATION  = auto()  # Mesure EAR personnalisée au démarrage
    IDLE         = auto()  # En attente du bouton
    VERIFICATION = auto()  # Vérification alcool
    AUTORISE     = auto()  # Conduite normale
    BLOQUE       = auto()  # Alcool détecté
    ALERTE_1     = auto()  # Somnolence légère
    ALERTE_2     = auto()  # Somnolence avancée
    ALERTE_3     = auto()  # Urgence
    PARKING      = auto()  # Stationnement autonome
    ARRET        = auto()  # Système arrêté


# ════════════════════════════════════════════════════════════════════════════
#  Contrôleur
# ════════════════════════════════════════════════════════════════════════════

class VoitureSecurisee:

    DUREE_VERIF_ALCOOL = 3.0    # Secondes de lecture MQ-3

    def __init__(self, port: str, camera_id: int, debug: bool, simuler: bool):
        self.debug   = debug
        self.simuler = simuler
        self.etat    = Etat.CALIBRATION
        self._ts     = time.time()

        if simuler:
            from simulation import SimulationSerie, SimulationDetecteur
            self.serial    = SimulationSerie()
            self.detecteur = SimulationDetecteur()
            logger.info("*** MODE SIMULATION ACTIVÉ ***")
        else:
            self.serial    = CommunicationSerie(port=port)
            self.detecteur = DetecteurSomnolence(camera_id=camera_id)

    # ── Démarrage ─────────────────────────────────────────────────────────────

    def demarrer(self) -> bool:
        if self.simuler:
            self.serial.connecter()
            self.detecteur.initialiser()
            return True

        if not self.serial.connecter():
            logger.error("Connexion Arduino échouée")
            return False
        if not self.detecteur.initialiser():
            logger.error("Initialisation caméra/MediaPipe échouée")
            return False
        return True

    def arreter(self):
        logger.info("Arrêt propre du système")
        try:
            self.serial.envoyer("CMD:RESET")
            time.sleep(0.3)
        except Exception:
            pass
        self.serial.deconnecter()
        self.detecteur.liberer()

    # ── Transitions ───────────────────────────────────────────────────────────

    def _goto(self, nouvel_etat: Etat):
        if nouvel_etat != self.etat:
            logger.info(f"[ÉTAT] {self.etat.name} → {nouvel_etat.name}")
            self.etat = nouvel_etat
            self._ts  = time.time()

    def _duree(self) -> float:
        return time.time() - self._ts

    # ── Handlers par état ─────────────────────────────────────────────────────

    def _calibration(self):
        """
        Mesure l'EAR du conducteur pendant 3 secondes pour personnaliser
        le seuil de détection. Affiche le résultat avant de passer à IDLE.
        """
        logger.info("=== CALIBRATION — regardez la caméra, yeux grand ouverts ===")
        seuil = self.detecteur.calibrer(duree=3.0, afficher=self.debug)
        logger.info(f"Seuil EAR personnalisé : {seuil:.3f}")
        self._goto(Etat.IDLE)

    def _idle(self):
        if self.serial.bouton:
            logger.info("Bouton pressé → vérification alcool")
            self._goto(Etat.VERIFICATION)

    def _verification(self):
        if self._duree() < self.DUREE_VERIF_ALCOOL:
            return
        if self.serial.alcool_detecte():
            logger.warning(f"Alcool ! MQ-3={self.serial.mq3}")
            self.serial.envoyer("CMD:BLOQUER")
            self._goto(Etat.BLOQUE)
        else:
            logger.info(f"Alcool OK (MQ-3={self.serial.mq3})")
            self.serial.envoyer("CMD:AUTORISER")
            self._goto(Etat.AUTORISE)

    def _autorise(self, niv: int):
        if niv == 1:
            self.serial.envoyer("CMD:ALERTE:1")
            self._goto(Etat.ALERTE_1)
        elif niv >= 2:
            self.serial.envoyer("CMD:ALERTE:2")
            self._goto(Etat.ALERTE_2)

    def _bloque(self):
        if not self.serial.alcool_detecte():
            logger.info("Alcool OK → re-vérification")
            self._goto(Etat.VERIFICATION)

    def _alerte_1(self, niv: int):
        if niv == 0:
            logger.info("Conducteur réveillé → retour normal")
            self.serial.envoyer("CMD:AUTORISER")
            self._goto(Etat.AUTORISE)
        elif self._duree() >= 5.0:
            logger.warning("Pas de réaction → niveau 2")
            self.serial.envoyer("CMD:ALERTE:2")
            self._goto(Etat.ALERTE_2)

    def _alerte_2(self, niv: int):
        if niv == 0:
            logger.info("Conducteur réveillé → retour normal")
            self.serial.envoyer("CMD:AUTORISER")
            self._goto(Etat.AUTORISE)
        elif self._duree() >= 3.0:   # 3 s — synchronisé avec demo.html ALERTE3_MS=3000
            logger.critical("URGENCE — parking autonome activé")
            self.serial.envoyer("CMD:ALERTE:3")
            time.sleep(1)
            self.serial.envoyer("CMD:PARKING")
            self._goto(Etat.PARKING)

    def _parking(self):
        if self.serial.rfid:
            logger.info("Zone parking atteinte (RFID) → arrêt")
            self._goto(Etat.ARRET)
        if self._duree() > 45:
            logger.warning("Timeout parking → arrêt forcé")
            self.serial.envoyer("CMD:RESET")
            self._goto(Etat.ARRET)

    # ── Boucle principale ─────────────────────────────────────────────────────

    def boucle(self):
        logger.info("Boucle principale démarrée (20 Hz)")

        while self.etat != Etat.ARRET:
            niveau = 0
            frame  = None

            # Analyse caméra (sauf états ne nécessitant pas la vidéo)
            if self.etat not in (Etat.CALIBRATION, Etat.IDLE,
                                  Etat.BLOQUE, Etat.PARKING, Etat.ARRET):
                res = self.detecteur.update()
                if not res.get("erreur"):
                    niveau = res.get("niveau", 0)
                    frame  = res.get("frame")
                    if self.debug and frame is not None:
                        cv2.imshow("Surveillance conducteur", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

            # Dispatch
            if   self.etat == Etat.CALIBRATION:  self._calibration()
            elif self.etat == Etat.IDLE:          self._idle()
            elif self.etat == Etat.VERIFICATION:  self._verification()
            elif self.etat == Etat.AUTORISE:      self._autorise(niveau)
            elif self.etat == Etat.BLOQUE:        self._bloque()
            elif self.etat == Etat.ALERTE_1:      self._alerte_1(niveau)
            elif self.etat == Etat.ALERTE_2:      self._alerte_2(niveau)
            elif self.etat == Etat.PARKING:       self._parking()

            time.sleep(0.05)   # 20 Hz

        logger.info("=== Système arrêté proprement ===")


# ════════════════════════════════════════════════════════════════════════════
#  Entrée
# ════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description="Voiture Robot Sécurisée")
    p.add_argument("--port",     default="/dev/ttyAMA0")
    p.add_argument("--camera",   type=int, default=0)
    p.add_argument("--debug",    action="store_true",
                   help="Affiche la fenêtre caméra et les logs détaillés")
    p.add_argument("--simulate", action="store_true",
                   help="Mode simulation (sans Arduino ni caméra réelle)")
    args = p.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    voiture = VoitureSecurisee(
        port      = args.port,
        camera_id = args.camera,
        debug     = args.debug,
        simuler   = args.simulate,
    )

    if not voiture.demarrer():
        sys.exit(1)

    try:
        voiture.boucle()
    except KeyboardInterrupt:
        logger.info("Interruption clavier")
    finally:
        voiture.arreter()


if __name__ == "__main__":
    main()
