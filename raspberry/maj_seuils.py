"""
Mise à jour des seuils dans detection_somnolence.py
====================================================
Lit seuils_valides_nthu.json produit par analyse_nthu.py
et patch les constantes dans detection_somnolence.py.

Usage :
  python maj_seuils.py
  python maj_seuils.py --seuils resultats_nthu/seuils_valides_nthu.json

Auteur : Vanelle Stéphanie MANGOUA
"""

import json
import re
import os
import argparse
import shutil
from datetime import datetime

def maj_seuils(chemin_seuils: str, chemin_detection: str):
    # Charger les nouveaux seuils
    with open(chemin_seuils, 'r') as f:
        seuils = json.load(f)

    ear_opt     = seuils.get("EAR",     0.25)
    mar_opt     = seuils.get("MAR",     0.65)
    perclos_opt = seuils.get("PERCLOS", 0.35)
    auc_ear     = seuils.get("auc_ear", 0.0)
    auc_mar     = seuils.get("auc_mar", 0.5)
    n_frames    = seuils.get("n_frames", "?")
    n_videos    = seuils.get("n_videos", "?")

    # Securite : si AUC MAR < 0.5, le dataset n'est pas pertinent pour MAR
    # (NTHU-DDD est centre sur les yeux, pas les baillement)
    if isinstance(auc_mar, float) and auc_mar < 0.5:
        print(f"  AVERTISSEMENT : AUC MAR={auc_mar:.3f} < 0.5 -- MAR non discriminant sur ce dataset")
        print(f"  MAR_SEUIL maintenu a la valeur par defaut (0.650)")
        mar_opt = 0.650

    print(f"\nSeuils lus depuis {chemin_seuils} :")
    print(f"  EAR     = {ear_opt:.3f}  (AUC={auc_ear:.3f})")
    print(f"  MAR     = {mar_opt:.3f}  (AUC={auc_mar:.3f})")
    print(f"  PERCLOS = {perclos_opt:.3f}")
    print(f"  Valides sur {n_frames} frames ({n_videos} videos NTHU-DDD)\n")

    # Backup
    backup = chemin_detection + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(chemin_detection, backup)
    print(f"Backup : {backup}")

    # Lire le fichier source
    with open(chemin_detection, 'r', encoding='utf-8') as f:
        contenu = f.read()

    contenu_original = contenu

    # Patch EAR_DEFAUT
    contenu = re.sub(
        r'(EAR_DEFAUT\s*=\s*)[\d.]+',
        f'\\g<1>{ear_opt:.3f}',
        contenu
    )

    # Patch MAR_SEUIL
    contenu = re.sub(
        r'(MAR_SEUIL\s*=\s*)[\d.]+',
        f'\\g<1>{mar_opt:.3f}',
        contenu
    )

    # Patch PERCLOS_SEUIL
    contenu = re.sub(
        r'(PERCLOS_SEUIL\s*=\s*)[\d.]+',
        f'\\g<1>{perclos_opt:.3f}',
        contenu
    )

    if contenu == contenu_original:
        print("AVERTISSEMENT : aucune constante remplacée — vérifier les noms dans detection_somnolence.py")
    else:
        with open(chemin_detection, 'w', encoding='utf-8') as f:
            f.write(contenu)
        print(f"detection_somnolence.py mis à jour :")
        print(f"  EAR_DEFAUT   → {ear_opt:.3f}")
        print(f"  MAR_SEUIL    → {mar_opt:.3f}")
        print(f"  PERCLOS_SEUIL→ {perclos_opt:.3f}")

    # Mettre à jour dataset_info.py — ajouter note de validation réelle
    ds_path = os.path.join(os.path.dirname(chemin_detection), "dataset_info.py")
    if os.path.isfile(ds_path):
        with open(ds_path, 'r', encoding='utf-8') as f:
            ds_contenu = f.read()

        note = f'''
# ════════════════════════════════════════════════════════════════════════════
#  Seuils validés par analyse réelle du dataset NTHU-DDD
#  Généré le {datetime.now().strftime("%Y-%m-%d %H:%M")} par analyse_nthu.py
# ════════════════════════════════════════════════════════════════════════════
SEUILS_VALIDES_NTHU = {{
    "EAR":         {ear_opt:.3f},   # seuil F1-optimal (AUC={auc_ear:.3f})
    "MAR":         {mar_opt:.3f},
    "PERCLOS":     {perclos_opt:.3f},
    "n_frames":    {n_frames},
    "n_videos":    {n_videos},
    "dataset":     "samymesbah/nthu-dataset-ddd-multi-class",
    "methode":     "ROC + indice de Youden + F1-optimal",
}}
'''
        # Ajouter seulement si pas déjà présent
        if "SEUILS_VALIDES_NTHU" not in ds_contenu:
            with open(ds_path, 'a', encoding='utf-8') as f:
                f.write(note)
            print(f"dataset_info.py enrichi avec les seuils validés")

    print("\nProchaine étape :")
    print("  git add -A")
    print("  git commit -m 'feat: seuils EAR/MAR/PERCLOS validés sur NTHU-DDD (ROC + Youden)'")
    print("  git push origin main")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seuils",    default="resultats_nthu/seuils_valides_nthu.json")
    p.add_argument("--detection", default="detection_somnolence.py")
    args = p.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    chemin_seuils    = os.path.join(script_dir, args.seuils)
    chemin_detection = os.path.join(script_dir, args.detection)

    if not os.path.isfile(chemin_seuils):
        print(f"[ERREUR] Fichier seuils introuvable : {chemin_seuils}")
        print("  Lance d'abord : python analyse_nthu.py --dataset <chemin_dataset>")
        return

    if not os.path.isfile(chemin_detection):
        print(f"[ERREUR] Fichier introuvable : {chemin_detection}")
        return

    maj_seuils(chemin_seuils, chemin_detection)


if __name__ == "__main__":
    main()
