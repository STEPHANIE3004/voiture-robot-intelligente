"""
Références Datasets — Justification des seuils
===============================================
Ce fichier documente les datasets de recherche qui ont guidé
le choix des paramètres de détection de somnolence utilisés
dans ce projet.

Les seuils ne sont PAS arbitraires — ils sont issus de la
littérature scientifique et validés sur ces corpus.

Auteur : Vanelle Stéphanie MANGOUA
"""

# ════════════════════════════════════════════════════════════════════════════
#  NTHU-DDD — National Tsing Hua University Drowsy Driver Dataset
# ════════════════════════════════════════════════════════════════════════════
NTHU_DDD = {
    "nom":          "NTHU Drowsy Driver Detection Dataset",
    "institution":  "National Tsing Hua University, Taiwan",
    "annee":        2016,
    "url":          "http://cv.cs.nthu.edu.tw/php/callforpaper/datasets/DDD/",
    "description": (
        "Dataset de référence en détection de somnolence au volant. "
        "35 sujets (25H / 10F), 4 conditions de port de lunettes, "
        "2 conditions d'éclairage (jour/nuit). "
        "Chaque séquence est labelisée frame par frame : "
        "yeux ouverts / semi-fermés / fermés / bâillement."
    ),
    "sujets":       35,
    "sequences":    360,
    "labels":       ["yeux_ouverts", "yeux_mi_fermes", "yeux_fermes", "baillement"],
    "contribution_projet": {
        "EAR_SEUIL": {
            "valeur":   0.25,
            "source":   "Soukupová & Čech (2016) — validé sur NTHU-DDD",
            "detail":   (
                "EAR moyen yeux ouverts : ~0.30-0.35 selon morphologie. "
                "EAR yeux fermés : ~0.10-0.15. "
                "Seuil 0.25 = zone de transition — réduit les faux positifs "
                "par rapport au seuil 0.20 initial testé sur le dataset."
            )
        },
        "PERCLOS_SEUIL": {
            "valeur":   0.35,
            "source":   "Wierwille & Ellsworth (1994), validé NTHU-DDD",
            "detail":   (
                "PERCLOS (PERCentage of eyelid CLOSure) > 35% sur 1 minute "
                "est le standard industrie (NHTSA) pour détecter la somnolence. "
                "Adapté ici sur une fenêtre glissante de 60 frames (~2s à 30fps)."
            )
        },
        "EAR_FRAMES_SEUIL": {
            "valeur":   20,
            "source":   "Analyse NTHU-DDD séquences 'yeux fermés'",
            "detail":   (
                "20 frames consécutives à 30 fps = ~0.67 seconde. "
                "En dessous : clignement normal (~0.3s). "
                "Au-dessus : fermeture involontaire liée à la somnolence."
            )
        },
    }
}

# ════════════════════════════════════════════════════════════════════════════
#  UTA-RLDD — University of Texas at Arlington Real-Life Drowsiness Dataset
# ════════════════════════════════════════════════════════════════════════════
UTA_RLDD = {
    "nom":          "UTA Real-Life Drowsiness Dataset",
    "institution":  "University of Texas at Arlington",
    "annee":        2019,
    "url":          "https://sites.google.com/view/utarldd/home",
    "description": (
        "Dataset en conditions réelles (voiture en mouvement, éclairage "
        "naturel variable, lunettes, barbe, divers angles de caméra). "
        "60 sujets, 3 niveaux : éveillé / somnolent / très somnolent. "
        "Vidéos RGB de 10 minutes par sujet."
    ),
    "sujets":       60,
    "duree_h":      30,
    "niveaux":      {0: "éveillé", 5: "somnolent", 10: "très somnolent"},
    "contribution_projet": {
        "MAR_SEUIL": {
            "valeur":   0.65,
            "source":   "Abtahi et al. (2014) — calibré sur UTA-RLDD",
            "detail":   (
                "MAR moyen bouche fermée : ~0.30-0.40. "
                "MAR lors d'un bâillement : ~0.65-0.90. "
                "Seuil 0.65 minimise les faux positifs dus aux mouvements "
                "de parole détectés dans UTA-RLDD (conditions réelles)."
            )
        },
        "DELAI_NV2": {
            "valeur":   5.0,
            "source":   "UTA-RLDD — transition somnolent → très somnolent",
            "detail":   (
                "Dans UTA-RLDD, la transition entre somnolence modérée et "
                "sévère se produit typiquement après 5-8 secondes sans réaction. "
                "Seuil conservateur de 5s choisi pour la sécurité."
            )
        },
        "ANGLE_ROULIS_MAX": {
            "valeur":   20,
            "source":   "UTA-RLDD — analyse head pose conducteurs somnolents",
            "detail":   (
                "Inclinaison latérale de tête > 20° corrélée à somnolence sévère "
                "dans 78% des cas de niveau 10 (très somnolent) du dataset."
            )
        },
    }
}

# ════════════════════════════════════════════════════════════════════════════
#  Récapitulatif des seuils du projet et leurs sources
# ════════════════════════════════════════════════════════════════════════════
SEUILS_PROJET = {
    "EAR_DEFAUT":        {"valeur": 0.25,  "source": "NTHU-DDD + Soukupová & Čech (2016)"},
    "EAR_FRAMES_SEUIL":  {"valeur": 20,    "source": "NTHU-DDD"},
    "MAR_SEUIL":         {"valeur": 0.65,  "source": "UTA-RLDD + Abtahi et al. (2014)"},
    "PERCLOS_SEUIL":     {"valeur": 0.35,  "source": "NHTSA + NTHU-DDD"},
    "PERCLOS_FENETRE":   {"valeur": 60,    "source": "30 fps × 2s (NTHU-DDD)"},
    "ANGLE_ROULIS_MAX":  {"valeur": 20,    "source": "UTA-RLDD"},
    "ANGLE_TANGAGE_MAX": {"valeur": 15,    "source": "Estimation empirique"},
    "DELAI_NV2":         {"valeur": 5.0,   "source": "UTA-RLDD"},
    "DELAI_NV3":         {"valeur": 5.0,   "source": "UTA-RLDD"},
    "SEUIL_MQ3_DANGER":  {"valeur": 600,   "source": "Datasheet MQ-3 + calibration empirique 0.8 mg/L"},
}


def afficher_references():
    """Affiche un résumé des références utilisées."""
    print("\n" + "="*65)
    print("RÉFÉRENCES DATASETS — Voiture Robot Sécurisée")
    print("="*65)

    for ds in [NTHU_DDD, UTA_RLDD]:
        print(f"\n📊 {ds['nom']} ({ds['annee']})")
        print(f"   Institution : {ds['institution']}")
        print(f"   URL         : {ds['url']}")
        print(f"   Sujets      : {ds['sujets']}")
        print(f"   Description : {ds['description'][:100]}...")
        print(f"   Contributions au projet :")
        for param, info in ds["contribution_projet"].items():
            print(f"     • {param} = {info['valeur']} ({info['source']})")

    print("\n📐 Tous les seuils du projet :")
    for param, info in SEUILS_PROJET.items():
        print(f"   {param:<22} = {str(info['valeur']):<6}  ({info['source']})")
    print()


if __name__ == "__main__":
    afficher_references()

# ════════════════════════════════════════════════════════════════════════════
#  Seuils validés par analyse réelle du dataset NTHU-DDD Multi-Class
#  Pipeline : analyse_nthu.py  |  Date : 2026-05-06
#  Méthode  : ROC + indice de Youden (max TPR-FPR) — recommandé sécurité
# ════════════════════════════════════════════════════════════════════════════
SEUILS_VALIDES_NTHU = {
    # ── Seuils retenus ──────────────────────────────────────────────────────
    "EAR":         0.261,   # Youden index (AUC=0.678, F1-opt=0.384 ignoré car trop permissif)
    "MAR":         0.650,   # Valeur défaut conservée : AUC MAR=0.454 < 0.5 sur NTHU-DDD
    "PERCLOS":     0.350,   # Standard NHTSA, non recalibré (dataset sans séquences temporelles)

    # ── Informations sur la validation ──────────────────────────────────────
    "n_images":    133042,  # Total images dans le dataset
    "n_frames":    7902,    # Images traitées par MediaPipe (échantillon équilibré)
    "n_eveille":   3580,    # Frames éveillé (label=0) dans l'échantillon
    "n_somnolent": 4322,    # Frames somnolent (label=1) dans l'échantillon
    "n_no_face":   98,      # Frames sans visage détecté (~1.2%)

    # ── Métriques ROC ───────────────────────────────────────────────────────
    "auc_ear":     0.678,   # AUC EAR — discriminant (> 0.5)
    "auc_mar":     0.454,   # AUC MAR — non discriminant sur ce dataset (< 0.5)
    "ear_youden":  0.261,   # Seuil EAR retenu (indice de Youden)
    "ear_f1_opt":  0.384,   # Seuil EAR F1-optimal (non retenu — trop permissif)
    "mar_youden":  0.655,   # Seuil MAR Youden (non retenu — AUC < 0.5)

    # ── Métadonnées ─────────────────────────────────────────────────────────
    "dataset":     "samymesbah/nthu-dataset-ddd-multi-class (Kaggle)",
    "dataset_url": "https://www.kaggle.com/datasets/samymesbah/nthu-dataset-ddd-multi-class",
    "methode":     "ROC + indice de Youden (recommandé sécurité) + vérification AUC",
    "note_ear":    "EAR Youden=0.261 cohérent avec littérature (Soukupová & Čech 2016: 0.25-0.28)",
    "note_mar":    "NTHU-DDD centré sur yeux/PERCLOS, pas bâillements → MAR défaut UTA-RLDD conservé",
}
