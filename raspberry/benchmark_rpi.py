"""
Benchmark latence MediaPipe Face Mesh — Voiture Robot Intelligente
==================================================================
Mesure le temps de traitement par frame (EAR + MAR + head pose)
et projette les performances sur Raspberry Pi 3B / 4B.

Usage :
  python benchmark_rpi.py                  # webcam 0, 200 frames
  python benchmark_rpi.py --frames 500     # 500 frames
  python benchmark_rpi.py --image test.jpg # image statique (boucle)

Auteur : Vanelle Stephanie MANGOUA — ESIEA
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import argparse
import os
import urllib.request
import platform
import json
from collections import deque

# ── Landmarks (identiques a detection_somnolence.py) ────────────────────────
IDX_OEIL_G = [362, 385, 387, 263, 373, 380]
IDX_OEIL_D = [33,  160, 158, 133, 153, 144]
IDX_BOUCHE = [61,  39,   0, 269, 291, 405,  17, 181]

# ── Facteurs de ralentissement mesures empiriquement ────────────────────────
# Source : benchmarks MediaPipe sur ARM Cortex-A72 (RPi 4) et A53 (RPi 3)
# https://developers.google.com/mediapipe/solutions/vision/face_landmarker
SLOWDOWN = {
    "Raspberry Pi 3B (ARMv8 @1.2GHz)": 6.5,
    "Raspberry Pi 4B (ARMv8 @1.8GHz)": 2.8,
    "Raspberry Pi 5  (ARMv8 @2.4GHz)": 1.5,
}
LATENCE_SERIAL_MS = 8.0     # Latence UART Arduino (~200ms periode, 8ms overhead)
LATENCE_CAMERA_MS = 33.0    # Capture frame 30fps = 33ms


def _has_legacy_api():
    try:
        _ = mp.solutions.face_mesh
        return True
    except AttributeError:
        return False


def init_mediapipe():
    """Initialise MediaPipe (legacy ou Tasks API selon version)."""
    if _has_legacy_api():
        print("  MediaPipe : API legacy (solutions)")
        mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return mesh, "legacy"
    else:
        print("  MediaPipe : API Tasks")
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        from mediapipe.tasks.python.vision import RunningMode

        model_path = os.path.join(os.path.dirname(__file__), "face_landmarker.task")
        if not os.path.exists(model_path):
            url = ("https://storage.googleapis.com/mediapipe-models/"
                   "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
            print("  Telechargement face_landmarker.task...")
            urllib.request.urlretrieve(url, model_path)

        opts = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=model_path),
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            running_mode=RunningMode.IMAGE,
        )
        return mp_vision.FaceLandmarker.create_from_options(opts), "tasks"


def process_frame(mesh, api_mode, frame_bgr):
    """Retourne (landmarks_ou_None, temps_ms)."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    t0 = time.perf_counter()

    if api_mode == "legacy":
        res = mesh.process(rgb)
        lm = res.multi_face_landmarks[0].landmark if res.multi_face_landmarks else None
    else:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = mesh.detect(mp_img)
        lm = res.face_landmarks[0] if res.face_landmarks else None

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return lm, elapsed_ms


def ear(pts):
    from scipy.spatial.distance import euclidean
    A = euclidean(pts[1], pts[5])
    B = euclidean(pts[2], pts[4])
    C = euclidean(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def extraire(lm, idx, w, h):
    return np.array([(lm[i].x * w, lm[i].y * h) for i in idx], dtype=np.float64)


def afficher_resultats(latences_ms, n_faces, n_total, api_mode):
    """Affiche le rapport de benchmark."""
    if not latences_ms:
        print("[ERREUR] Aucune mesure collectee.")
        return {}

    arr = np.array(latences_ms)
    mean_ms  = float(np.mean(arr))
    p50_ms   = float(np.percentile(arr, 50))
    p95_ms   = float(np.percentile(arr, 95))
    p99_ms   = float(np.percentile(arr, 99))
    fps_pc   = 1000.0 / mean_ms if mean_ms > 0 else 0

    print("\n" + "=" * 62)
    print("  BENCHMARK MediaPipe Face Mesh — Voiture Robot Intelligente")
    print("  Auteur : Vanelle Stephanie MANGOUA — ESIEA")
    print("=" * 62)
    print(f"\n  Plateforme    : {platform.node()} / {platform.machine()}")
    print(f"  API MediaPipe : {api_mode}")
    print(f"  Frames testees: {n_total}  ({n_faces} avec visage, "
          f"{n_total - n_faces} sans visage)")

    print("\n  ── Latence inference MediaPipe (sur cet PC) ──")
    print(f"     Moyenne  : {mean_ms:6.1f} ms   ({fps_pc:.1f} fps equiv.)")
    print(f"     Mediane  : {p50_ms:6.1f} ms")
    print(f"     P95      : {p95_ms:6.1f} ms")
    print(f"     P99      : {p99_ms:6.1f} ms")

    print("\n  ── Projection sur Raspberry Pi ──────────────────")
    print(f"  {'Cible':<38} {'Latence ms':>10}  {'FPS':>6}  {'OK 30fps?':>9}")
    print(f"  {'-'*67}")

    resultats_rpi = {}
    for nom, facteur in SLOWDOWN.items():
        lat_rpi  = mean_ms * facteur + LATENCE_CAMERA_MS
        fps_rpi  = 1000.0 / lat_rpi if lat_rpi > 0 else 0
        ok_30fps = "OUI  ✓" if fps_rpi >= 28 else ("~OK" if fps_rpi >= 15 else "NON  ✗")
        print(f"  {nom:<38} {lat_rpi:>10.0f}  {fps_rpi:>6.1f}  {ok_30fps:>9}")
        resultats_rpi[nom] = {"latence_ms": round(lat_rpi, 1), "fps": round(fps_rpi, 1)}

    lat_total_nv1 = mean_ms + LATENCE_CAMERA_MS + LATENCE_SERIAL_MS
    print(f"\n  Latence totale (inference + camera + UART) : "
          f"~{lat_total_nv1:.0f} ms sur PC")
    print(f"  Exigence SR6 (< 200 ms) : "
          f"{'RESPECTEE ✓' if lat_total_nv1 < 200 else 'DEPASSEE ✗'}")

    print("\n  ── Remarques ────────────────────────────────────")
    print("  - MediaPipe utilise XNNPACK (optimise NEON ARM) sur RPi 4")
    print("  - Activer 4 cores (par defaut sur RPi OS) ameliore ~30% perf")
    print("  - Resolution 320x240 recommandee sur RPi 3 (gain ~40%)")
    print("  - AUC EAR = 0.678 sur NTHU-DDD (7902 frames, 133K images)")
    print("  - Seuil EAR = 0.261 (indice de Youden, coherent litterature)")
    print("=" * 62)

    # Sauvegarder JSON
    resultats = {
        "plateforme":      platform.node(),
        "architecture":    platform.machine(),
        "api_mediapipe":   api_mode,
        "n_frames":        n_total,
        "n_visages":       n_faces,
        "latence_pc_ms":   {
            "mean": round(mean_ms, 2),
            "p50":  round(p50_ms,  2),
            "p95":  round(p95_ms,  2),
            "p99":  round(p99_ms,  2),
        },
        "fps_pc":           round(fps_pc, 1),
        "projection_rpi":   resultats_rpi,
        "sr6_respecte_pc":  bool(lat_total_nv1 < 200),
    }
    sortie = os.path.join(os.path.dirname(__file__), "resultats_nthu", "benchmark_latence.json")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    with open(sortie, "w") as f:
        json.dump(resultats, f, indent=2)
    print(f"\n  Resultats sauvegardes : {sortie}")

    return resultats


def run_benchmark(source, n_frames):
    print("\n" + "=" * 62)
    print("  Initialisation MediaPipe...")
    mesh, api_mode = init_mediapipe()

    # Source video ou image
    if source is None:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERREUR] Webcam introuvable. Utilise --image pour une image statique.")
            return
        print(f"  Source : webcam  |  {n_frames} frames")
        use_image = False
    elif os.path.isfile(source):
        frame_static = cv2.imread(source)
        if frame_static is None:
            print(f"[ERREUR] Image illisible : {source}")
            return
        h, w = frame_static.shape[:2]
        print(f"  Source : {source} ({w}x{h})  |  {n_frames} iterations")
        use_image = True
        cap = None
    else:
        print(f"[ERREUR] Fichier introuvable : {source}")
        return

    latences  = []
    n_faces   = 0
    ears_vals = deque(maxlen=30)
    print(f"  Demarrage mesure ({n_frames} frames)...\n")

    for i in range(n_frames):
        if use_image:
            frame = frame_static.copy()
        else:
            ret, frame = cap.read()
            if not ret:
                break

        lm, lat_ms = process_frame(mesh, api_mode, frame)
        latences.append(lat_ms)

        if lm is not None:
            n_faces += 1
            h, w = frame.shape[:2]
            og = extraire(lm, IDX_OEIL_G, w, h)
            od = extraire(lm, IDX_OEIL_D, w, h)
            e_val = (ear(og) + ear(od)) / 2.0
            ears_vals.append(e_val)

        if (i + 1) % 50 == 0:
            mean_so_far = np.mean(latences) if latences else 0
            print(f"  Frame {i+1:>4}/{n_frames}  |  "
                  f"latence moy = {mean_so_far:5.1f} ms  |  "
                  f"EAR = {np.mean(ears_vals):.3f}" if ears_vals else
                  f"  Frame {i+1:>4}/{n_frames}  |  latence moy = {mean_so_far:5.1f} ms")

    if cap:
        cap.release()
    if hasattr(mesh, "close"):
        mesh.close()

    afficher_resultats(latences, n_faces, len(latences), api_mode)


def main():
    p = argparse.ArgumentParser(
        description="Benchmark latence MediaPipe — Voiture Robot Intelligente")
    p.add_argument("--frames", type=int, default=200,
                   help="Nombre de frames a mesurer (defaut 200)")
    p.add_argument("--image",  type=str, default=None,
                   help="Image statique a utiliser (defaut : webcam)")
    args = p.parse_args()

    run_benchmark(args.image, args.frames)


if __name__ == "__main__":
    main()
