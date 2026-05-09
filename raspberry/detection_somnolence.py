"""
Détection de Somnolence — MediaPipe Face Mesh
==============================================
Analyse le flux caméra en temps réel avec MediaPipe (468 landmarks 3D).
Plus rapide que dlib sur Raspberry Pi (pas de modèle .dat externe requis).

Niveaux de somnolence :
  0 = éveillé
  1 = somnole  (signal détecté ≥ EAR_FRAMES_SEUIL frames consécutives,
                ou PERCLOS > 30 %, ou blink_rate < 10/min)
  2 = dort     (niveau 1 persistant > DELAI_NV2 secondes sans réaction)
  3 = urgence  (niveau 2 persistant > DELAI_NV3 secondes → parking auto)

Signaux de détection — 5 sources indépendantes :
  - EAR        (Eye Aspect Ratio)         — fermeture des yeux
  - HEAD PITCH (ratio nez/yeux/hauteur)   — tête tombant vers le bas
  - PERCLOS    (% frames yeux fermés)     — seuil 30 % sur 60 frames
  - BLINK RATE (clignements/min)          — < 10/min = somnolence
  - MAR        (Mouth Aspect Ratio)       — bâillements

Score de fatigue fusionné 0-100 (synchro demo.html) :
  EAR(30) + HEAD(25) + PERCLOS(20) + BLINK(15) + MAR(10)

Calibration personnalisée par conducteur :
  - EAR seuil  = mean_EAR  × 0.75
  - HEAD seuil = mean_HEAD + 0.08
  Mesure sur CALIB_FRAMES=150 frames (~5 s à 30 fps)

Références datasets :
  - NTHU-DDD  : seuils EAR validés sur conducteurs asiatiques/occidentaux
  - UTA-RLDD  : conditions réelles (éclairage variable, lunettes, barbe)
  → Voir dataset_info.py pour les détails.

Auteur  : Vanelle Stéphanie MANGOUA
Dépend. : pip install opencv-python mediapipe numpy scipy
"""

import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial import distance
from collections import deque
import time
import math
import logging

logger = logging.getLogger(__name__)

# ── Landmarks MediaPipe Face Mesh (468 points) ───────────────────────────────
# Œil gauche — 6 points EAR (P1=coin ext, P4=coin int, P2/P3/P5/P6=paupières)
IDX_OEIL_G = [362, 385, 387, 263, 373, 380]
# Œil droit
IDX_OEIL_D = [33,  160, 158, 133, 153, 144]
# Bouche — 8 points MAR
IDX_BOUCHE = [61, 39, 0, 269, 291, 405, 17, 181]

# Head pose solvePnP — 6 points clés
IDX_POSE = {
    "nez":      1,
    "menton":   152,
    "oeil_g":   226,
    "oeil_d":   446,
    "bouche_g": 57,
    "bouche_d": 287,
}

# Modèle 3D de référence (mm, visage générique)
MODEL_3D = np.array([
    (0.0,     0.0,    0.0),
    (0.0,  -330.0,  -65.0),
    (-225.0,  170.0, -135.0),
    (225.0,   170.0, -135.0),
    (-150.0, -150.0, -125.0),
    (150.0,  -150.0, -125.0),
], dtype=np.float64)

# ── Paramètres (synchronisés avec demo.html) ─────────────────────────────────
EAR_DEFAUT        = 0.261    # Seuil EAR par défaut (avant calibration)
EAR_FRAMES_SEUIL  = 40      # Frames consécutives avant niveau 1  [demo: FAT_FRAMES=40]
MAR_SEUIL         = 0.650   # Bâillement (validé UTA-RLDD)
PERCLOS_SEUIL     = 0.30    # >30% frames yeux fermés → somnolence [demo: 30%]
PERCLOS_FENETRE   = 60      # Fenêtre PERCLOS (nb de frames)
BLINK_LOW         = 10      # Clignements/min en dessous = somnolence [demo: 10]
BLINK_FENETRE_S   = 60      # Fenêtre blink rate (secondes)
HEAD_THR_OFFSET   = 0.08    # Offset calibration HEAD pitch [demo: +0.08]
ANGLE_ROULIS_MAX  = 20      # Degrés inclinaison latérale max (solvePnP)
ANGLE_TANGAGE_MAX = 15      # Degrés inclinaison avant/arrière max (solvePnP)

DELAI_NV2         = 4.0   # Secondes niveau 1 → niveau 2  [demo: ALERTE2_MS=4000]
DELAI_NV3         = 4.0   # Secondes niveau 2 → niveau 3  [demo: ALERTE3_MS=4000]
POST_CALIB_GRACE  = 3.0   # Secondes de grâce post-calibration (buffers vides) [demo: 3000ms]
CALIB_FRAMES      = 150   # Frames de calibration (~5 s à 30 fps)  [demo: 150]


# ── Fonctions utilitaires ────────────────────────────────────────────────────

def ear(points: np.ndarray) -> float:
    """
    Eye Aspect Ratio — Soukupová & Čech (2016).
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    """
    A = distance.euclidean(points[1], points[5])
    B = distance.euclidean(points[2], points[4])
    C = distance.euclidean(points[0], points[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def mar(points: np.ndarray) -> float:
    """
    Mouth Aspect Ratio — Abtahi et al. (2014).
    Mesure l'ouverture verticale de la bouche.
    """
    A = distance.euclidean(points[1], points[7])
    B = distance.euclidean(points[2], points[6])
    C = distance.euclidean(points[3], points[5])
    D = distance.euclidean(points[0], points[4])
    return (A + B + C) / (3.0 * D) if D > 0 else 0.0


def extraire_points(landmarks, indices, w, h):
    """Extrait les coordonnées pixel à partir des landmarks MediaPipe."""
    return np.array(
        [(landmarks[i].x * w, landmarks[i].y * h) for i in indices],
        dtype=np.float64
    )


def calcHeadPitch(landmarks) -> float:
    """
    Calcule l'inclinaison de la tête vers le bas (head pitch ratio).
    Formule : (noseY - eyeMidY) / faceHeight — synchronisé avec demo.html.

    Plus la tête s'incline vers l'avant, plus la valeur augmente.
    Valeur typique yeux droits : ~0.28–0.33
    Valeur alerte tête tombante : > HEAD_THR_OFFSET + baseline
    """
    eye_mid_y = (landmarks[33].y + landmarks[133].y +
                 landmarks[362].y + landmarks[263].y) / 4.0
    face_h = landmarks[152].y - landmarks[10].y
    if face_h < 0.01:
        return 0.5
    return (landmarks[4].y - eye_mid_y) / face_h


def estimer_head_pose(landmarks, w, h):
    """
    Estime l'orientation 3D de la tête (roulis, tangage, lacet) via solvePnP.
    Retourne (roulis_deg, tangage_deg, lacet_deg).
    Méthode complémentaire à calcHeadPitch (plus précise en 3D).
    """
    image_points = np.array([
        (landmarks[IDX_POSE["nez"]].x      * w, landmarks[IDX_POSE["nez"]].y      * h),
        (landmarks[IDX_POSE["menton"]].x   * w, landmarks[IDX_POSE["menton"]].y   * h),
        (landmarks[IDX_POSE["oeil_g"]].x   * w, landmarks[IDX_POSE["oeil_g"]].y   * h),
        (landmarks[IDX_POSE["oeil_d"]].x   * w, landmarks[IDX_POSE["oeil_d"]].y   * h),
        (landmarks[IDX_POSE["bouche_g"]].x * w, landmarks[IDX_POSE["bouche_g"]].y * h),
        (landmarks[IDX_POSE["bouche_d"]].x * w, landmarks[IDX_POSE["bouche_d"]].y * h),
    ], dtype=np.float64)

    focal   = w
    centre  = (w / 2.0, h / 2.0)
    K = np.array([
        [focal, 0,     centre[0]],
        [0,     focal, centre[1]],
        [0,     0,     1        ],
    ], dtype=np.float64)
    dist_coeffs = np.zeros((4, 1))

    ok, rvec, tvec = cv2.solvePnP(
        MODEL_3D, image_points, K, dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        return 0.0, 0.0, 0.0

    rmat, _ = cv2.Rodrigues(rvec)
    sy      = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    lacet   = math.degrees(math.atan2( rmat[1, 0], rmat[0, 0]))
    tangage = math.degrees(math.atan2(-rmat[2, 0], sy))
    roulis  = math.degrees(math.atan2( rmat[2, 1], rmat[2, 2]))
    return abs(roulis), abs(tangage), abs(lacet)


def calc_fatigue_score(ear_val, ear_seuil, head_pitch, head_seuil,
                        perclos, blink_rate, mar_val, calib_done) -> float:
    """
    Score de fatigue fusionné 0-100 — synchronisé avec demo.html.
    Poids : EAR(30) + HEAD(25) + PERCLOS(20) + BLINK(15) + MAR(10)
    """
    eye_down  = ear_val < ear_seuil
    head_down = head_pitch > head_seuil
    blink_bad = (blink_rate < BLINK_LOW and blink_rate > 0 and calib_done)

    score = 0.0
    if eye_down:
        score += 30
    if head_down:
        score += 25
    score += min(20.0, perclos * 100.0 * 0.67)
    if blink_bad:
        score += min(15.0, (BLINK_LOW - blink_rate) * 1.5)
    if mar_val > MAR_SEUIL:
        score += 10
    return min(100.0, score)


# ── Classe principale ────────────────────────────────────────────────────────

class DetecteurSomnolence:
    """
    Détecteur de somnolence basé sur MediaPipe Face Mesh.
    5 signaux indépendants : EAR, HEAD PITCH, PERCLOS, BLINK RATE, MAR.
    Score de fatigue fusionné 0-100.
    Calibration personnalisée EAR + HEAD par conducteur.
    """

    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id

        # Seuils (remplacés après calibration)
        self.ear_seuil   = EAR_DEFAUT
        self.head_seuil  = 0.310       # HEAD pitch threshold
        self.calibre     = False

        # Compteurs état
        self.compteur_ear = 0
        self.compteur_mar = 0
        self.fenetre_perclos = []

        # Période de grâce post-calibration
        self.calibre_a = None   # timestamp fin calibration

        # Horodatages niveaux
        self.ts_nv1 = None
        self.ts_nv2 = None
        self.niveau  = 0

        # Métriques courantes
        self.ear_val       = 1.0
        self.mar_val       = 0.0
        self.perclos       = 0.0
        self.roulis        = 0.0
        self.tangage       = 0.0
        self.head_pitch    = 0.3
        self.baillement    = False
        self.tete_inclinee = False
        self.fatigue_score = 0.0

        # Blink rate — fenêtre glissante 60 s
        self._prev_ear_below   = False
        self._blink_timestamps = deque()   # timestamps des clignements
        self.blink_rate        = 0         # clignements/min

        # MediaPipe
        self._mp_mesh = mp.solutions.face_mesh
        self._mesh    = None
        self._cap     = None

    # ── Init / libération ─────────────────────────────────────────────────────

    def initialiser(self) -> bool:
        """Lance MediaPipe Face Mesh et ouvre la caméra."""
        self._mesh = self._mp_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self._cap = cv2.VideoCapture(self.camera_id)
        if not self._cap.isOpened():
            logger.error(f"Caméra {self.camera_id} inaccessible")
            return False
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        logger.info("MediaPipe Face Mesh initialisé")
        return True

    def liberer(self):
        """Libère la caméra et MediaPipe."""
        if self._cap:
            self._cap.release()
        if self._mesh:
            self._mesh.close()
        cv2.destroyAllWindows()

    # ── Calibration ───────────────────────────────────────────────────────────

    def calibrer(self, duree: float = 5.0, afficher: bool = True) -> float:
        """
        Phase de calibration personnalisée.
        Mesure EAR et HEAD PITCH sur CALIB_FRAMES frames (~5 s à 30 fps).

        Seuils calculés :
          EAR seuil  = max(0.15,  mean_EAR  × 0.75)
          HEAD seuil = min(0.55,  mean_HEAD + 0.08)

        Méthode inspirée de Reddy et al. (2017).
        Returns : seuil EAR calibré
        """
        logger.info(
            f"Calibration démarrée ({CALIB_FRAMES} frames) — "
            "regardez droit devant, yeux grand ouverts, tête droite"
        )
        valeurs_ear  = []
        valeurs_head = []
        debut   = time.time()
        timeout = max(duree, CALIB_FRAMES / 30.0 + 3.0)

        while len(valeurs_ear) < CALIB_FRAMES and (time.time() - debut) < timeout:
            ret, frame = self._cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res  = self._mesh.process(rgb)

            if res.multi_face_landmarks:
                lm  = res.multi_face_landmarks[0].landmark
                og  = extraire_points(lm, IDX_OEIL_G, w, h)
                od  = extraire_points(lm, IDX_OEIL_D, w, h)
                e   = (ear(og) + ear(od)) / 2.0
                hp  = calcHeadPitch(lm)
                valeurs_ear.append(e)
                valeurs_head.append(hp)

            if afficher:
                pct    = int(len(valeurs_ear) / CALIB_FRAMES * 100)
                ear_m  = np.mean(valeurs_ear)  if valeurs_ear  else 0.0
                head_m = np.mean(valeurs_head) if valeurs_head else 0.0
                cv2.putText(frame, "CALIBRATION — yeux ouverts, tete droite",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(frame, f"{pct}%  ({len(valeurs_ear)}/{CALIB_FRAMES})",
                            (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 3)
                cv2.putText(frame, f"EAR: {ear_m:.3f}   HEAD: {head_m:.3f}",
                            (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)
                cv2.imshow("Calibration", frame)
                cv2.waitKey(1)

        cv2.destroyWindow("Calibration")

        if len(valeurs_ear) < 10:
            logger.warning("Pas assez de mesures — seuils par défaut utilisés")
            self.ear_seuil  = EAR_DEFAUT
            self.head_seuil = 0.310
        else:
            mean_ear       = np.mean(valeurs_ear)
            std_ear        = np.std(valeurs_ear)
            mean_head      = np.mean(valeurs_head)
            self.ear_seuil  = max(0.15, round(max(mean_ear * 0.75,
                                                   mean_ear - 2 * std_ear), 3))
            self.head_seuil = min(0.55, round(mean_head + HEAD_THR_OFFSET, 3))
            logger.info(
                f"Calibration OK — "
                f"EAR baseline={mean_ear:.3f} std={std_ear:.3f} → seuil={self.ear_seuil} | "
                f"HEAD baseline={mean_head:.3f} → seuil={self.head_seuil}"
            )

        self.calibre   = True
        self.calibre_a = time.time()
        # Pré-remplir le buffer PERCLOS avec des "yeux ouverts" pour éviter
        # un pic PERCLOS=100% dès le 1er clignement après calibration
        self.fenetre_perclos = [False] * PERCLOS_FENETRE
        self.compteur_ear    = 0
        return self.ear_seuil

    # ── Blink rate ────────────────────────────────────────────────────────────

    def _maj_blink_rate(self, ear_val: float):
        """
        Détecte les clignements complets (transition EAR above → below → above)
        et calcule le taux en clignements/min sur une fenêtre glissante de 60 s.
        Synchronisé avec l'algorithme demo.html.
        """
        now       = time.time()
        ear_below = ear_val < self.ear_seuil

        # Fin de clignement = transition below→above
        if self._prev_ear_below and not ear_below:
            self._blink_timestamps.append(now)

        self._prev_ear_below = ear_below

        # Purge timestamps > 60 s
        cutoff = now - BLINK_FENETRE_S
        while self._blink_timestamps and self._blink_timestamps[0] < cutoff:
            self._blink_timestamps.popleft()

        self.blink_rate = len(self._blink_timestamps)

    # ── Machine à états somnolence ────────────────────────────────────────────

    def _maj_niveau(self, yeux_fermes: bool):
        """
        Machine à états 0→1→2→3.
        Signal combiné : EAR OU PERCLOS OU HEAD OU BLINK RATE OU (MAR+HEAD).
        """
        now = time.time()

        # Période de grâce post-calibration — buffers pas encore stables
        if self.calibre_a and (now - self.calibre_a) < POST_CALIB_GRACE:
            self.compteur_ear = 0
            self.ts_nv1       = None
            self.niveau       = 0
            # PERCLOS continue de se remplir mais les alertes restent suspendues

        # PERCLOS
        self.fenetre_perclos.append(yeux_fermes)
        if len(self.fenetre_perclos) > PERCLOS_FENETRE:
            self.fenetre_perclos.pop(0)
        self.perclos = sum(self.fenetre_perclos) / len(self.fenetre_perclos)

        head_down = self.head_pitch > self.head_seuil or self.tete_inclinee
        blink_bad = self.blink_rate < BLINK_LOW and self.blink_rate > 0 and self.calibre

        # Signal combiné — 5 sources indépendantes
        signal = (
            yeux_fermes
            or self.perclos >= PERCLOS_SEUIL
            or head_down
            or blink_bad
            or (self.baillement and head_down)
        )

        if not signal:
            self.compteur_ear = 0
            self.ts_nv1       = None
            self.ts_nv2       = None
            self.niveau       = 0
            return

        self.compteur_ear += 1

        if self.compteur_ear >= EAR_FRAMES_SEUIL:
            if self.ts_nv1 is None:
                self.ts_nv1 = now
                self.niveau = 1
                reasons = []
                if yeux_fermes:                       reasons.append("EAR")
                if head_down:                         reasons.append("HEAD")
                if self.perclos >= PERCLOS_SEUIL:     reasons.append(f"PERCLOS={self.perclos:.0%}")
                if blink_bad:                         reasons.append(f"BLINK={self.blink_rate}/min")
                logger.warning(f"Niveau 1 — {' + '.join(reasons) or 'signal combiné'}")

            if self.niveau == 1 and (now - self.ts_nv1) >= DELAI_NV2:
                if self.ts_nv2 is None:
                    self.ts_nv2 = now
                    self.niveau = 2
                    logger.warning("Niveau 2 — pas de récupération après DELAI_NV2")

            if self.niveau == 2 and (now - self.ts_nv2) >= DELAI_NV3:
                self.niveau = 3
                logger.critical("Niveau 3 — URGENCE — parking autonome")

    # ── Update principal ──────────────────────────────────────────────────────

    def update(self) -> dict:
        """
        Lit une frame, calcule les 5 signaux, met à jour le niveau et le score.

        Returns : dict {
            niveau, ear, mar, perclos, head_pitch, roulis, tangage,
            blink_rate, baillement, tete_inclinee, fatigue_score,
            visage_detecte, frame, ear_seuil, head_seuil, calibre
        }
        """
        if not self._cap:
            return {"erreur": "Non initialisé", "niveau": -1}

        ret, frame = self._cap.read()
        if not ret:
            return {"erreur": "Lecture caméra échouée", "niveau": -1}

        h, w = frame.shape[:2]
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        res  = self._mesh.process(rgb)
        rgb.flags.writeable = True

        if not res.multi_face_landmarks:
            return {
                "niveau":         self.niveau,
                "ear":            None,
                "mar":            None,
                "perclos":        round(self.perclos, 2),
                "head_pitch":     None,
                "roulis":         None,
                "tangage":        None,
                "blink_rate":     self.blink_rate,
                "baillement":     False,
                "tete_inclinee":  False,
                "fatigue_score":  0.0,
                "visage_detecte": False,
                "frame":          frame,
            }

        lm = res.multi_face_landmarks[0].landmark

        # ── EAR ──────────────────────────────────────────────────────────────
        og = extraire_points(lm, IDX_OEIL_G, w, h)
        od = extraire_points(lm, IDX_OEIL_D, w, h)
        self.ear_val  = (ear(og) + ear(od)) / 2.0
        yeux_fermes   = self.ear_val < self.ear_seuil

        # ── Blink rate ────────────────────────────────────────────────────────
        self._maj_blink_rate(self.ear_val)

        # ── MAR (bâillement) ──────────────────────────────────────────────────
        bm = extraire_points(lm, IDX_BOUCHE, w, h)
        self.mar_val = mar(bm)
        if self.mar_val > MAR_SEUIL:
            self.compteur_mar += 1
            self.baillement = self.compteur_mar >= 3
        else:
            self.compteur_mar = max(0, self.compteur_mar - 1)
            if self.compteur_mar == 0:
                self.baillement = False

        # ── Head pitch (ratio simple — synchro demo.html) ─────────────────────
        self.head_pitch = calcHeadPitch(lm)

        # ── Head pose 3D solvePnP (roulis / tangage) ──────────────────────────
        self.roulis, self.tangage, _ = estimer_head_pose(lm, w, h)
        self.tete_inclinee = (
            self.roulis  > ANGLE_ROULIS_MAX or
            self.tangage > ANGLE_TANGAGE_MAX
        )

        # ── Score de fatigue fusionné 0-100 ───────────────────────────────────
        self.fatigue_score = calc_fatigue_score(
            self.ear_val, self.ear_seuil,
            self.head_pitch, self.head_seuil,
            self.perclos, self.blink_rate,
            self.mar_val, self.calibre
        )

        # ── Machine à états ───────────────────────────────────────────────────
        self._maj_niveau(yeux_fermes)

        # ── Annotations frame ─────────────────────────────────────────────────
        self._annoter(frame, og, od, bm)

        return {
            "niveau":         self.niveau,
            "ear":            round(self.ear_val, 3),
            "mar":            round(self.mar_val, 3),
            "perclos":        round(self.perclos, 2),
            "head_pitch":     round(self.head_pitch, 3),
            "roulis":         round(self.roulis, 1),
            "tangage":        round(self.tangage, 1),
            "blink_rate":     self.blink_rate,
            "baillement":     self.baillement,
            "tete_inclinee":  self.tete_inclinee,
            "fatigue_score":  round(self.fatigue_score, 1),
            "visage_detecte": True,
            "frame":          frame,
            "ear_seuil":      self.ear_seuil,
            "head_seuil":     self.head_seuil,
            "calibre":        self.calibre,
        }

    # ── Annotations visuelles ─────────────────────────────────────────────────

    def _annoter(self, frame, og, od, bm):
        """Dessine les landmarks et métriques sur la frame OpenCV."""
        COULEURS = {0: (0, 220, 0), 1: (0, 165, 255), 2: (0, 80, 255), 3: (0, 0, 255)}
        c = COULEURS.get(self.niveau, (255, 255, 255))

        # Points landmarks (yeux + bouche)
        for pt in np.vstack([og, od, bm]):
            cv2.circle(frame, (int(pt[0]), int(pt[1])), 2, c, -1)

        # Message d'alerte
        MSGS = {1: "SOMNOLENCE", 2: "VOUS DORMEZ ?", 3: "URGENCE — PARKING AUTO"}
        if self.niveau in MSGS:
            cv2.putText(frame, MSGS[self.niveau], (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, c, 2)

        # Métriques — 5 signaux + score
        lignes = [
            f"EAR    {self.ear_val:.3f}  / seuil {self.ear_seuil:.3f}",
            f"HEAD   {self.head_pitch:.3f}  / seuil {self.head_seuil:.3f}",
            f"PERCLOS {self.perclos:.0%}   / seuil {PERCLOS_SEUIL:.0%}",
            f"BLINK  {self.blink_rate}/min  / seuil {BLINK_LOW}",
            f"MAR    {self.mar_val:.3f}  / seuil {MAR_SEUIL:.3f}",
            f"FATIGUE {self.fatigue_score:.0f}/100",
        ]
        y0 = 55 if self.niveau in MSGS else 30
        for i, txt in enumerate(lignes):
            cv2.putText(frame, txt, (10, y0 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, c, 1)
