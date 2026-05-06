"""
Analyse NTHU-DDD Multi-Class -- Validation et calibration des seuils
=====================================================================
Dataset structure (Kaggle: samymesbah/nthu-dataset-ddd-multi-class) :
  Multi class/
    train/
      drowsy/         -> label 1 (somnolent)
      non_drowsy/     -> label 0 (eveille)
    test/  (idem)

Chaque sous-dossier contient des JPEG extraits frame par frame.
Le label est encode dans le chemin du fichier.

Resultats produits :
  resultats_nthu/seuils_valides_nthu.json
  resultats_nthu/rapport_nthu.txt
  resultats_nthu/roc_curves_nthu.png
  resultats_nthu/distribution_ear_nthu.png

Usage :
  python analyse_nthu.py --dataset "C:/Users/hp/.cache/kagglehub/.../versions/1"
  python analyse_nthu.py --dataset "..." --max_images 5000

Auteur : Vanelle Stephanie MANGOUA
"""

import cv2
import mediapipe as mp
import numpy as np
from scipy.spatial import distance
from sklearn.metrics import roc_curve, auc, classification_report
import matplotlib
matplotlib.use('Agg')   # Pas de fenetre graphique -- sauvegarde uniquement
import matplotlib.pyplot as plt
import json
import os
import glob
import argparse
import logging
import urllib.request
import random

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

# -- Indices landmarks MediaPipe (identiques pour legacy et Tasks API) ---------
IDX_OEIL_G = [362, 385, 387, 263, 373, 380]
IDX_OEIL_D = [33,  160, 158, 133, 153, 144]
IDX_BOUCHE = [61,  39,  0,  269, 291, 405,  17, 181]

PERCLOS_FENETRE = 60


# ============================================================================
#  Couche de compatibilite MediaPipe
# ============================================================================

def _has_legacy_api():
    try:
        _ = mp.solutions.face_mesh
        return True
    except AttributeError:
        return False


class FaceMeshWrapper:
    """
    Wrapper unifie : ancienne API (solutions) OU nouvelle API (Tasks).
    Interface : process(rgb_frame) -> liste landmarks ou None
    """

    def __init__(self):
        self._legacy = _has_legacy_api()
        if self._legacy:
            logger.info("MediaPipe : API legacy (solutions)")
            self._mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._ts = None
        else:
            logger.info("MediaPipe : API Tasks (nouveau)")
            self._mesh = self._init_tasks()
            self._ts = 0

    def _init_tasks(self):
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
        if not os.path.exists(model_path):
            url = ("https://storage.googleapis.com/mediapipe-models/"
                   "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
            logger.info("Telechargement du modele face_landmarker.task...")
            urllib.request.urlretrieve(url, model_path)
            logger.info("Modele OK : " + model_path)

        from mediapipe.tasks.python.vision import RunningMode
        opts = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=RunningMode.IMAGE,   # Mode IMAGE pour des frames isolees
        )
        return mp_vision.FaceLandmarker.create_from_options(opts)

    def process(self, rgb_frame):
        """Retourne la liste de landmarks du premier visage, ou None."""
        if self._legacy:
            res = self._mesh.process(rgb_frame)
            if res.multi_face_landmarks:
                return res.multi_face_landmarks[0].landmark
            return None
        else:
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            res = self._mesh.detect(mp_img)
            if res.face_landmarks:
                return res.face_landmarks[0]
            return None

    def close(self):
        self._mesh.close()


# ============================================================================
#  Calcul EAR / MAR
# ============================================================================

def ear(pts):
    A = distance.euclidean(pts[1], pts[5])
    B = distance.euclidean(pts[2], pts[4])
    C = distance.euclidean(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def mar(pts):
    A = distance.euclidean(pts[1], pts[7])
    B = distance.euclidean(pts[2], pts[6])
    C = distance.euclidean(pts[3], pts[5])
    D = distance.euclidean(pts[0], pts[4])
    return (A + B + C) / (3.0 * D) if D > 0 else 0.0


def extraire_pts(lm, indices, w, h):
    return np.array([(lm[i].x * w, lm[i].y * h) for i in indices],
                    dtype=np.float64)


# ============================================================================
#  Chargement des images NTHU-DDD Multi-Class
# ============================================================================

def charger_images(chemin_dataset: str, max_images: int = None):
    """
    Parcourt le dataset image par image.
    Detecte le label depuis le nom de fichier NTHU-DDD :
      - fichier contenant 'notdrowsy' (ex: 005_glasses_176_notdrowsy.jpg) -> 0
      - fichier contenant 'drowsy' mais PAS 'notdrowsy'                   -> 1
    Retourne deux listes : chemins_images, labels
    """
    extensions = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG")
    tous_fichiers = []
    for ext in extensions:
        tous_fichiers.extend(
            glob.glob(os.path.join(chemin_dataset, "**", ext), recursive=True)
        )

    if not tous_fichiers:
        logger.error("Aucune image trouvee dans : " + chemin_dataset)
        return [], []

    logger.info(f"{len(tous_fichiers)} images trouvees au total")

    # Determiner label depuis le nom de fichier
    # IMPORTANT : verifier 'notdrowsy' EN PREMIER car 'drowsy' est un sous-chaine de 'notdrowsy'
    images, labels = [], []
    n_skip = 0
    for fpath in tous_fichiers:
        nom = os.path.basename(fpath).lower()   # nom de fichier seulement
        parts = fpath.lower().replace("\\", "/")
        if "notdrowsy" in nom or "non_drowsy" in parts or "/alert/" in parts or "/awake/" in parts:
            lbl = 0
        elif "drowsy" in nom:
            lbl = 1
        else:
            n_skip += 1
            continue
        images.append(fpath)
        labels.append(lbl)

    logger.info(f"  Somnolent (1) : {sum(labels)}")
    logger.info(f"  Eveille   (0) : {len(labels) - sum(labels)}")
    if n_skip:
        logger.info(f"  Ignores (label inconnu) : {n_skip}")

    # Echantillonnage si max_images
    if max_images and len(images) > max_images:
        # Echantillonner de facon equilibree
        idx = list(range(len(images)))
        random.shuffle(idx)
        idx = idx[:max_images]
        images = [images[i] for i in idx]
        labels = [labels[i] for i in idx]
        logger.info(f"Echantillon : {len(images)} images (max_images={max_images})")

    return images, labels


# ============================================================================
#  Traitement d'une image
# ============================================================================

def traiter_image(chemin: str, mesh: FaceMeshWrapper, w_defaut=640, h_defaut=480):
    """
    Lit une image, extrait EAR et MAR via MediaPipe.
    Retourne (ear_val, mar_val) ou (None, None) si pas de visage.
    """
    img = cv2.imread(chemin)
    if img is None:
        return None, None

    h, w = img.shape[:2]
    rgb  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    lm   = mesh.process(rgb)

    if lm is None:
        return None, None

    og = extraire_pts(lm, IDX_OEIL_G, w, h)
    od = extraire_pts(lm, IDX_OEIL_D, w, h)
    bm = extraire_pts(lm, IDX_BOUCHE,  w, h)

    e = (ear(og) + ear(od)) / 2.0
    m = mar(bm)
    return e, m


# ============================================================================
#  Analyse ROC et seuil optimal
# ============================================================================

def trouver_seuil_optimal(valeurs, labels, metrique: str,
                           inverser: bool = True) -> dict:
    """
    Courbe ROC + indice de Youden + F1 optimal.
    inverser=True pour EAR (valeur basse = somnolent).
    """
    scores = -valeurs if inverser else valeurs

    fpr, tpr, seuils_roc = roc_curve(labels, scores)
    roc_auc = auc(fpr, tpr)

    youden_idx = np.argmax(tpr - fpr)
    seuil_youden = abs(seuils_roc[youden_idx])

    # F1 optimal
    best_f1, best_seuil = 0.0, seuil_youden
    for s in np.linspace(valeurs.min(), valeurs.max(), 300):
        preds = (valeurs < s).astype(int) if inverser else (valeurs > s).astype(int)
        vp = ((preds == 1) & (labels == 1)).sum()
        fp = ((preds == 1) & (labels == 0)).sum()
        fn = ((preds == 0) & (labels == 1)).sum()
        if (vp + fp) > 0 and (vp + fn) > 0:
            prec = vp / (vp + fp)
            rapp = vp / (vp + fn)
            f1   = 2 * prec * rapp / (prec + rapp) if (prec + rapp) > 0 else 0
            if f1 > best_f1:
                best_f1, best_seuil = f1, s

    logger.info(f"  {metrique:<10} Youden={seuil_youden:.3f}  "
                f"F1-opt={best_seuil:.3f} (F1={best_f1:.3f})  AUC={roc_auc:.3f}")

    return {
        "metrique":     metrique,
        "seuil_youden": round(float(seuil_youden), 3),
        "seuil_f1":     round(float(best_seuil),   3),
        "f1_score":     round(float(best_f1),       3),
        "auc":          round(float(roc_auc),       3),
        "fpr":          fpr,
        "tpr":          tpr,
    }


# ============================================================================
#  Visualisations
# ============================================================================

def tracer_roc(resultats: list, dossier_sortie: str):
    fig, axes = plt.subplots(1, len(resultats), figsize=(6 * len(resultats), 5))
    if len(resultats) == 1:
        axes = [axes]
    fig.suptitle("Courbes ROC -- NTHU-DDD Multi-Class (MediaPipe)\n"
                 "Voiture Robot Securisee -- MANGOUA Stephanie",
                 fontsize=11, fontweight='bold')

    couleurs = ['#e74c3c', '#3498db', '#2ecc71']
    for ax, res, col in zip(axes, resultats, couleurs):
        ax.plot(res['fpr'], res['tpr'], color=col, lw=2,
                label=f"AUC = {res['auc']:.3f}")
        ax.plot([0, 1], [0, 1], 'k--', alpha=0.4)
        ax.set_xlabel("Taux Faux Positifs (1 - Specificite)")
        ax.set_ylabel("Taux Vrais Positifs (Sensibilite)")
        ax.set_title(f"{res['metrique']}\nSeuil F1 = {res['seuil_f1']:.3f}")
        ax.legend(loc='lower right')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    chemin = os.path.join(dossier_sortie, "roc_curves_nthu.png")
    plt.savefig(chemin, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("ROC sauvegardee : " + chemin)


def tracer_distributions(ears, labels, seuil, dossier_sortie: str):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Distribution EAR -- NTHU-DDD Multi-Class\n"
                 "Voiture Robot Securisee -- MANGOUA Stephanie",
                 fontsize=11, fontweight='bold')

    ev  = ears[labels == 0]
    som = ears[labels == 1]

    ax1.hist(ev,  bins=60, alpha=0.6, color='#2ecc71', label='Eveille', density=True)
    ax1.hist(som, bins=60, alpha=0.6, color='#e74c3c', label='Somnolent', density=True)
    ax1.axvline(seuil, color='navy', lw=2, linestyle='--',
                label=f'Seuil optimal = {seuil:.3f}')
    ax1.axvline(0.25, color='orange', lw=1.5, linestyle=':',
                label='Seuil defaut = 0.25')
    ax1.set_xlabel("EAR (Eye Aspect Ratio)")
    ax1.set_ylabel("Densite")
    ax1.set_title("Distribution EAR par classe")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.boxplot([ev, som], labels=['Eveille', 'Somnolent'],
                patch_artist=True,
                boxprops=dict(facecolor='lightblue', alpha=0.7))
    ax2.axhline(seuil, color='navy', lw=2, linestyle='--',
                label=f'Seuil = {seuil:.3f}')
    ax2.set_ylabel("EAR")
    ax2.set_title("Boxplot EAR par classe")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    chemin = os.path.join(dossier_sortie, "distribution_ear_nthu.png")
    plt.savefig(chemin, dpi=150, bbox_inches='tight')
    plt.close()
    logger.info("Distribution sauvegardee : " + chemin)


# ============================================================================
#  Pipeline principal
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyse NTHU-DDD Multi-Class -- Validation seuils EAR/MAR")
    parser.add_argument("--dataset",    required=True,
                        help="Chemin dossier NTHU-DDD (contenant 'Multi class/')")
    parser.add_argument("--max_images", type=int, default=8000,
                        help="Nb max images a traiter (defaut 8000)")
    parser.add_argument("--sortie",     default="resultats_nthu",
                        help="Dossier de sortie")
    args = parser.parse_args()

    if not os.path.isdir(args.dataset):
        logger.error("Dataset introuvable : " + args.dataset)
        return

    os.makedirs(args.sortie, exist_ok=True)
    logger.info("Dataset : " + args.dataset)
    logger.info("Sortie  : " + args.sortie)

    # -- Init MediaPipe -------------------------------------------------------
    mesh = FaceMeshWrapper()

    # -- Charger images -------------------------------------------------------
    images, labels_list = charger_images(args.dataset, args.max_images)
    if not images:
        logger.error("Aucune image trouvee -- verifier la structure du dataset")
        mesh.close()
        return

    # -- Traitement frame par frame -------------------------------------------
    logger.info(f"\nTraitement de {len(images)} images...")
    ears_list, mars_list, labels_valides = [], [], []
    n_no_face = 0

    for i, (fpath, lbl) in enumerate(zip(images, labels_list)):
        if (i + 1) % 500 == 0:
            pct = 100 * (i + 1) / len(images)
            logger.info(f"  {i+1}/{len(images)} ({pct:.0f}%) -- "
                        f"visages: {len(ears_list)}  sans visage: {n_no_face}")

        e, m = traiter_image(fpath, mesh)
        if e is None:
            n_no_face += 1
            continue

        ears_list.append(e)
        mars_list.append(m)
        labels_valides.append(lbl)

    mesh.close()

    if not ears_list:
        logger.error("Aucun visage detecte -- verifier les images")
        return

    ears   = np.array(ears_list)
    mars   = np.array(mars_list)
    labels = np.array(labels_valides)

    n_total   = len(labels)
    n_eveille = (labels == 0).sum()
    n_somn    = (labels == 1).sum()
    logger.info(f"\nTotal avec visage : {n_total}  "
                f"(eveille={n_eveille} / somnolent={n_somn})")
    logger.info(f"Sans visage detecte : {n_no_face}")

    # -- Analyse ROC ----------------------------------------------------------
    logger.info("\n=== Analyse ROC ===")
    res_ear = trouver_seuil_optimal(ears, labels, "EAR", inverser=True)
    res_mar = trouver_seuil_optimal(mars, labels, "MAR", inverser=False)

    # -- Choisir le seuil EAR : Youden (securite) plutot que F1-optimal -------
    # Youden = max(TPR - FPR) : equilibre sensibilite/specificite
    # F1-optimal peut etre influe par le desequilibre de classes
    # Pour un systeme de securite, Youden est prefere (moins de faux negatifs)
    ear_retenu = res_ear['seuil_youden']

    # MAR : si AUC < 0.5, dataset non pertinent pour baillements -> garder defaut
    if res_mar['auc'] < 0.5:
        logger.warning(f"AUC MAR={res_mar['auc']:.3f} < 0.5 -- MAR non discriminant sur NTHU-DDD")
        logger.warning("MAR_SEUIL conserve a la valeur par defaut (0.650)")
        mar_retenu = 0.650
    else:
        mar_retenu = res_mar['seuil_youden']

    # -- Sauvegarder JSON -----------------------------------------------------
    seuils_valides = {
        "EAR":           ear_retenu,        # Youden index (securite optimale)
        "MAR":           mar_retenu,        # Youden ou defaut si AUC<0.5
        "PERCLOS":       0.35,              # Inchange (pas de sequence temporelle)
        "EAR_defaut":    0.25,
        "MAR_defaut":    0.65,
        "PERCLOS_defaut":0.35,
        "EAR_f1_opt":    res_ear['seuil_f1'],   # Info : F1-optimal (non retenu)
        "MAR_f1_opt":    res_mar['seuil_f1'],
        "dataset":       "samymesbah/nthu-dataset-ddd-multi-class",
        "n_images":      int(n_total),
        "n_no_face":     int(n_no_face),
        "n_frames":      int(n_total),      # Alias pour compatibilite maj_seuils.py
        "n_videos":      int(n_total),
        "auc_ear":       res_ear['auc'],
        "auc_mar":       res_mar['auc'],
        "auc_perclos":   0.0,
        "f1_ear":        res_ear['f1_score'],
        "f1_mar":        res_mar['f1_score'],
        "methode_ear":   "Youden (TPR-FPR optimal) -- recommande pour systeme de securite",
        "methode_mar":   "Youden ou defaut si AUC<0.5 (NTHU-DDD non pertinent pour MAR)",
    }

    json_path = os.path.join(args.sortie, "seuils_valides_nthu.json")
    with open(json_path, 'w') as f:
        json.dump(seuils_valides, f, indent=2)
    logger.info("Seuils sauvegardes : " + json_path)

    # -- Rapport texte --------------------------------------------------------
    rapport_path = os.path.join(args.sortie, "rapport_nthu.txt")
    preds_ear = (ears < res_ear['seuil_f1']).astype(int)
    with open(rapport_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("RAPPORT ANALYSE NTHU-DDD -- Voiture Robot Securisee\n")
        f.write("Auteur : Vanelle Stephanie MANGOUA\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Dataset    : {args.dataset}\n")
        f.write(f"Images     : {n_total} ({n_eveille} eveille / {n_somn} somnolent)\n")
        f.write(f"Sans visage: {n_no_face}\n\n")
        f.write("SEUILS VALIDES SUR NTHU-DDD :\n")
        f.write(f"  EAR : {res_ear['seuil_f1']:.3f}  "
                f"(defaut 0.25 | AUC={res_ear['auc']:.3f} | F1={res_ear['f1_score']:.3f})\n")
        f.write(f"  MAR : {res_mar['seuil_f1']:.3f}  "
                f"(defaut 0.65 | AUC={res_mar['auc']:.3f} | F1={res_mar['f1_score']:.3f})\n\n")
        f.write("CLASSIFICATION REPORT (EAR) :\n")
        f.write(classification_report(labels, preds_ear,
                                       target_names=['Eveille', 'Somnolent']))
    logger.info("Rapport sauvegarde : " + rapport_path)

    # -- Graphiques -----------------------------------------------------------
    logger.info("\nGeneration des graphiques...")
    tracer_roc([res_ear, res_mar], args.sortie)
    tracer_distributions(ears, labels, res_ear['seuil_f1'], args.sortie)

    # -- Resume ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESULTATS NTHU-DDD")
    print("=" * 60)
    print(f"  EAR optimal : {res_ear['seuil_f1']:.3f}  (AUC={res_ear['auc']:.3f}  F1={res_ear['f1_score']:.3f})")
    print(f"  MAR optimal : {res_mar['seuil_f1']:.3f}  (AUC={res_mar['auc']:.3f}  F1={res_mar['f1_score']:.3f})")
    print(f"\n  -> Mettre a jour detection_somnolence.py :")
    print(f"     EAR_DEFAUT = {res_ear['seuil_f1']:.3f}")
    print(f"     MAR_SEUIL  = {res_mar['seuil_f1']:.3f}")
    print(f"\n  Resultats : {args.sortie}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
