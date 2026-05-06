"""
Communication Série — Raspberry Pi ↔ Arduino Mega
==================================================
Gère la connexion UART, la réception JSON des capteurs
et l'envoi de commandes vers l'Arduino.

Protocole :
  Arduino → RPi  (toutes les 200 ms, JSON) :
    {"mq3": 450, "rfid": false, "btn": false, "mot": true}

  RPi → Arduino  (sur événement, texte + \\n) :
    CMD:AUTORISER | CMD:BLOQUER | CMD:ALERTE:1 |
    CMD:ALERTE:2  | CMD:ALERTE:3 | CMD:PARKING | CMD:RESET

Auteur : Vanelle Stéphanie MANGOUA
"""

import serial
import json
import threading
import time
import queue
import logging

logger = logging.getLogger(__name__)


class CommunicationSerie:
    """
    Interface thread-safe entre la RPi et l'Arduino.
    Tourne un thread de lecture en arrière-plan.
    Les données capteurs sont disponibles via la propriété `donnees`.
    """

    COMMANDES_VALIDES = {
        "CMD:AUTORISER",
        "CMD:BLOQUER",
        "CMD:ALERTE:1",
        "CMD:ALERTE:2",
        "CMD:ALERTE:3",
        "CMD:PARKING",
        "CMD:RESET",
    }

    def __init__(self, port: str = "/dev/ttyAMA0", baud: int = 9600, timeout: float = 2.0):
        self.port    = port
        self.baud    = baud
        self.timeout = timeout

        self._ser          = None
        self._lock         = threading.Lock()
        self._thread       = None
        self._running      = False
        self._file_attente = queue.Queue(maxsize=10)

        # Dernières données reçues de l'Arduino
        self._donnees = {
            "mq3":  0,
            "rfid": False,
            "btn":  False,
            "mot":  False,
        }
        self._erreurs      = 0
        self._connexion_ok = False

    # ── Connexion ─────────────────────────────────────────────────────────────

    def connecter(self) -> bool:
        """Ouvre le port série et démarre le thread de lecture."""
        try:
            self._ser = serial.Serial(
                port      = self.port,
                baudrate  = self.baud,
                timeout   = self.timeout,
                bytesize  = serial.EIGHTBITS,
                parity    = serial.PARITY_NONE,
                stopbits  = serial.STOPBITS_ONE,
            )
            time.sleep(2)   # Délai reset Arduino
            self._ser.reset_input_buffer()
            self._connexion_ok = True
            logger.info(f"Connecté à {self.port} @ {self.baud} bauds")
        except serial.SerialException as e:
            logger.error(f"Impossible d'ouvrir {self.port} : {e}")
            self._connexion_ok = False
            return False

        self._running = True
        self._thread  = threading.Thread(target=self._lire, daemon=True, name="SerialReader")
        self._thread.start()
        return True

    def deconnecter(self):
        """Arrête le thread et ferme le port."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._ser and self._ser.is_open:
            self._ser.close()
        logger.info("Port série fermé")

    # ── Lecture (thread) ──────────────────────────────────────────────────────

    def _lire(self):
        """Thread : lit les trames JSON de l'Arduino en continu."""
        while self._running:
            try:
                if not self._ser.is_open:
                    break

                ligne = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if not ligne:
                    continue

                # Ignorer les messages de debug (commençant par '[')
                if ligne.startswith("["):
                    logger.debug(f"Arduino: {ligne}")
                    continue

                data = json.loads(ligne)
                with self._lock:
                    self._donnees.update(data)
                    self._erreurs = 0

            except json.JSONDecodeError:
                pass   # Trame incomplète ou bruit — ignorer
            except serial.SerialException as e:
                logger.error(f"Erreur série : {e}")
                self._erreurs += 1
                if self._erreurs > 10:
                    logger.critical("Trop d'erreurs série — reconnexion...")
                    time.sleep(1)
                    self._reconnexion()
            except Exception as e:
                logger.error(f"Erreur inattendue : {e}")

    def _reconnexion(self):
        """Tente de rouvrir le port série après une erreur."""
        try:
            if self._ser.is_open:
                self._ser.close()
            time.sleep(2)
            self._ser.open()
            self._erreurs = 0
            logger.info("Reconnexion série réussie")
        except Exception as e:
            logger.error(f"Reconnexion échouée : {e}")

    # ── Propriétés données capteurs ───────────────────────────────────────────

    @property
    def donnees(self) -> dict:
        """Retourne une copie thread-safe des dernières données Arduino."""
        with self._lock:
            return dict(self._donnees)

    @property
    def mq3(self) -> int:
        with self._lock:
            return self._donnees["mq3"]

    @property
    def rfid(self) -> bool:
        with self._lock:
            return self._donnees["rfid"]

    @property
    def bouton(self) -> bool:
        with self._lock:
            val = self._donnees["btn"]
            self._donnees["btn"] = False  # Auto-reset après lecture
            return val

    @property
    def connecte(self) -> bool:
        return self._connexion_ok and self._running

    # ── Envoi commandes ───────────────────────────────────────────────────────

    def envoyer(self, commande: str) -> bool:
        """Envoie une commande à l'Arduino (thread-safe)."""
        if commande not in self.COMMANDES_VALIDES:
            logger.warning(f"Commande invalide : {commande}")
            return False

        if not self._ser or not self._ser.is_open:
            logger.error("Port série non ouvert")
            return False

        try:
            with self._lock:
                self._ser.write((commande + "\n").encode("utf-8"))
                self._ser.flush()
            logger.debug(f"→ Arduino : {commande}")
            return True
        except serial.SerialException as e:
            logger.error(f"Erreur envoi : {e}")
            return False

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def alcool_detecte(self, seuil_danger: int = 600) -> bool:
        return self.mq3 >= seuil_danger

    def alcool_alerte(self, seuil_alerte: int = 400) -> bool:
        return self.mq3 >= seuil_alerte

    def __enter__(self):
        self.connecter()
        return self

    def __exit__(self, *args):
        self.deconnecter()
