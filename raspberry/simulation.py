"""
Mode Simulation — Tests sans matériel physique
===============================================
Remplace CommunicationSerie et DetecteurSomnolence par des classes
qui génèrent des données synthétiques réalistes.

Scénarios disponibles :
  normal     → conducteur éveillé, EAR stable ~0.32
  somnolence → EAR descend progressivement sous le seuil
  danger     → EAR très bas, maintenu, déclenche parking auto
  alcool     → MQ-3 > seuil dès le début
  mixte      → alternance normal / somnolence / réveil

Usage :
  python main.py --simulate
  python main.py --simulate --scenario danger

Auteur : Vanelle Stéphanie MANGOUA
"""

import math
import random
import time
import logging

logger = logging.getLogger(__name__)

# ── Scénarios ─────────────────────────────────────────────────────────────────
SCENARIOS = {
    "normal":     "Conducteur éveillé — EAR stable (test de non-régression)",
    "somnolence": "Somnolence progressive → alerte 1 → réveil → retour normal",
    "danger":     "Somnolence sévère → alerte 3 → parking autonome",
    "alcool":     "Alcool détecté au démarrage → blocage moteur",
    "mixte":      "Cycles normal / somnolence / réveil aléatoires",
}


# ════════════════════════════════════════════════════════════════════════════
#  SimulationSerie — remplace CommunicationSerie
# ════════════════════════════════════════════════════════════════════════════

class SimulationSerie:
    """
    Simule la communication Arduino.
    Génère des valeurs MQ-3 et RFID selon le scénario.
    Logue les commandes reçues.
    """

    def __init__(self, scenario: str = "somnolence"):
        self.scenario      = scenario
        self._mq3          = 200     # Valeur ADC initiale (pas d'alcool)
        self._rfid         = False
        self._bouton       = False
        self._moteurs      = False
        self._debut        = None
        self._commandes    = []
        self._rfid_envoye  = False

    def connecter(self) -> bool:
        self._debut = time.time()
        logger.info(f"[SIM] Connexion série simulée — scénario : {self.scenario}")
        logger.info(f"[SIM] {SCENARIOS.get(self.scenario, '?')}")

        # Simuler appui bouton après 1 seconde
        self._bouton = True

        # Alcool simulé dès le départ si scénario 'alcool'
        if self.scenario == "alcool":
            self._mq3 = 700

        return True

    def deconnecter(self):
        logger.info(f"[SIM] Déconnexion — {len(self._commandes)} commandes reçues")
        if self._commandes:
            logger.info(f"[SIM] Historique commandes : {self._commandes}")

    def envoyer(self, commande: str) -> bool:
        self._commandes.append((round(time.time() - self._debut, 2), commande))
        logger.info(f"[SIM] → Arduino : {commande}")

        # Simuler RFID quand CMD:PARKING est reçu (après 8s)
        if commande == "CMD:PARKING":
            self._rfid_envoye = True

        return True

    def _t(self) -> float:
        return time.time() - self._debut if self._debut else 0

    @property
    def donnees(self) -> dict:
        return {"mq3": self._mq3, "rfid": self._rfid,
                "btn": self._bouton, "mot": self._moteurs}

    @property
    def mq3(self) -> int:
        # Légère variation aléatoire ±15
        return self._mq3 + random.randint(-15, 15)

    @property
    def rfid(self) -> bool:
        # RFID déclenché 8s après CMD:PARKING
        if self._rfid_envoye and self._t() > 8:
            self._rfid = True
        return self._rfid

    @property
    def bouton(self) -> bool:
        val = self._bouton
        self._bouton = False
        return val

    @property
    def connecte(self) -> bool:
        return True

    def alcool_detecte(self, seuil: int = 600) -> bool:
        return self.mq3 >= seuil

    def alcool_alerte(self, seuil: int = 400) -> bool:
        return self.mq3 >= seuil


# ════════════════════════════════════════════════════════════════════════════
#  SimulationDetecteur — remplace DetecteurSomnolence
# ════════════════════════════════════════════════════════════════════════════

class SimulationDetecteur:
    """
    Simule la détection de somnolence selon différents scénarios.
    Reproduit un EAR réaliste avec bruit gaussien et transitions progressives.
    """

    # EAR de référence selon état
    EAR_EVEILLE  = 0.32
    EAR_SOMNOLE  = 0.22   # Juste sous le seuil calibré
    EAR_DORT     = 0.12
    EAR_BRUIT    = 0.02   # Écart-type du bruit

    def __init__(self, scenario: str = "somnolence"):
        self.scenario    = scenario
        self._debut      = None
        self._calibre    = False
        self.ear_seuil   = 0.25

        # État interne
        self.niveau      = 0
        self._compteur   = 0
        self._ts_nv1     = None
        self._ts_nv2     = None
        self._fenetre    = []
        self._phase      = "eveille"
        self._phase_debut= None

    def initialiser(self) -> bool:
        self._debut       = time.time()
        self._phase_debut = time.time()
        logger.info(f"[SIM] Détecteur somnolence simulé — scénario : {self.scenario}")
        return True

    def liberer(self):
        logger.info("[SIM] Détecteur libéré")

    def calibrer(self, duree: float = 3.0, afficher: bool = False) -> float:
        logger.info(f"[SIM] Calibration simulée ({duree}s)")
        time.sleep(min(duree, 1.0))   # Simulation rapide
        self.ear_seuil = 0.24
        self._calibre  = True
        logger.info(f"[SIM] Seuil EAR simulé : {self.ear_seuil}")
        return self.ear_seuil

    def _t(self) -> float:
        return time.time() - self._debut if self._debut else 0

    def _ear_cible(self) -> float:
        """Retourne l'EAR cible selon le scénario et le temps écoulé."""
        t = self._t()

        if self.scenario == "normal":
            return self.EAR_EVEILLE

        elif self.scenario == "somnolence":
            # 0-8s : éveillé → 8-20s : somnole → 20-25s : réveil → normal
            if t < 8:    return self.EAR_EVEILLE
            elif t < 20: return self.EAR_SOMNOLE
            elif t < 25: return self.EAR_EVEILLE
            else:        return self.EAR_EVEILLE

        elif self.scenario == "danger":
            # 0-5s : éveillé → 5s+ : dort (niveau 3 → parking)
            if t < 5:    return self.EAR_EVEILLE
            else:        return self.EAR_DORT

        elif self.scenario == "alcool":
            return self.EAR_EVEILLE   # Bloqué avant même d'analyser la caméra

        elif self.scenario == "mixte":
            # Cycles de 15s : éveillé / somnolent / réveil
            cycle = t % 45
            if cycle < 15:  return self.EAR_EVEILLE
            elif cycle < 30: return self.EAR_SOMNOLE
            else:            return self.EAR_EVEILLE

        return self.EAR_EVEILLE

    def _maj_niveau(self, yeux_fermes: bool):
        """Machine à états interne (identique à DetecteurSomnolence)."""
        now = time.time()
        self._fenetre.append(yeux_fermes)
        if len(self._fenetre) > 60:
            self._fenetre.pop(0)
        perclos = sum(self._fenetre) / len(self._fenetre)

        signal = yeux_fermes or perclos >= 0.35

        if not signal:
            self._compteur = 0
            self._ts_nv1   = None
            self._ts_nv2   = None
            self.niveau    = 0
            return

        self._compteur += 1

        if self._compteur >= 20:
            if self._ts_nv1 is None:
                self._ts_nv1 = now
                self.niveau = 1
            if self.niveau == 1 and (now - self._ts_nv1) >= 5.0:
                if self._ts_nv2 is None:
                    self._ts_nv2 = now
                    self.niveau = 2
            if self.niveau == 2 and (now - self._ts_nv2) >= 5.0:
                self.niveau = 3

    def update(self) -> dict:
        """Génère des métriques synthétiques réalistes."""
        cible      = self._ear_cible()
        ear_val    = max(0.05, cible + random.gauss(0, self.EAR_BRUIT))
        yeux_fermes = ear_val < self.ear_seuil

        mar_val    = random.gauss(0.35, 0.05)
        roulis     = abs(random.gauss(0, 3))
        tangage    = abs(random.gauss(0, 2))

        self._maj_niveau(yeux_fermes)

        result = {
            "niveau":         self.niveau,
            "ear":            round(ear_val, 3),
            "mar":            round(mar_val, 3),
            "perclos":        round(sum(self._fenetre)/max(1,len(self._fenetre)), 2),
            "roulis":         round(roulis, 1),
            "tangage":        round(tangage, 1),
            "baillement":     mar_val > 0.65,
            "tete_inclinee":  roulis > 20,
            "visage_detecte": True,
            "frame":          None,
            "ear_seuil":      self.ear_seuil,
            "calibre":        self._calibre,
        }

        if self.niveau > 0:
            label = {1:"SOMNOLENCE", 2:"DORT", 3:"URGENCE"}[self.niveau]
            logger.debug(f"[SIM] t={self._t():.1f}s | EAR={ear_val:.3f} | {label}")

        return result


# ════════════════════════════════════════════════════════════════════════════
#  Lanceur autonome — test du scénario sans main.py
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="Test simulation somnolence")
    parser.add_argument("--scenario", default="somnolence",
                        choices=list(SCENARIOS.keys()))
    parser.add_argument("--duree",    type=float, default=40.0)
    args = parser.parse_args()

    print(f"\nScénario : {args.scenario}")
    print(f"Description : {SCENARIOS[args.scenario]}\n")

    serie     = SimulationSerie(scenario=args.scenario)
    detecteur = SimulationDetecteur(scenario=args.scenario)
    serie.connecter()
    detecteur.initialiser()
    detecteur.calibrer()

    debut = time.time()
    try:
        while time.time() - debut < args.duree:
            res = detecteur.update()
            print(
                f"t={time.time()-debut:5.1f}s | "
                f"EAR={res['ear']:.3f} | "
                f"Niveau={res['niveau']} | "
                f"MQ3={serie.mq3:4d} | "
                f"RFID={serie.rfid}"
            )
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nArrêt.")

    serie.deconnecter()
