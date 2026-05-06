
# NTHU-DDD Dataset - Telechargement et Analyse EAR
# Auteur : Vanelle Stephanie MANGOUA
# Usage  : .\telecharger_et_analyser.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NTHU-DDD Dataset - Telechargement et Validation seuils" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Localiser kaggle.json ---------------------------------------------

$kaggleDir  = "$env:USERPROFILE\.kaggle"
$kaggleJson = "$kaggleDir\kaggle.json"

if (-not (Test-Path $kaggleJson)) {
    $candidates = @(
        "$env:USERPROFILE\Downloads\kaggle.json",
        "$env:USERPROFILE\Telechargements\kaggle.json",
        "$env:USERPROFILE\Desktop\kaggle.json"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($found) {
        Write-Host "[1/5] kaggle.json trouve : $found" -ForegroundColor Green
        New-Item -ItemType Directory -Force -Path $kaggleDir | Out-Null
        Copy-Item $found $kaggleJson
        Write-Host "      Copie vers $kaggleJson" -ForegroundColor Green
    } else {
        Write-Host "[ERREUR] kaggle.json introuvable." -ForegroundColor Red
        Write-Host "  Cree-le manuellement dans : $kaggleDir\" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "[1/5] kaggle.json deja en place : $kaggleJson" -ForegroundColor Green
}

$kaggleCreds = Get-Content $kaggleJson | ConvertFrom-Json
Write-Host "      Connecte en tant que : $($kaggleCreds.username)" -ForegroundColor Gray

# -- 2. Installer dependances Python --------------------------------------

Write-Host ""
Write-Host "[2/5] Installation des dependances Python..." -ForegroundColor Cyan

$packages = @("kagglehub", "scikit-learn", "matplotlib", "opencv-python", "mediapipe", "numpy", "scipy")
foreach ($pkg in $packages) {
    Write-Host "      pip install $pkg" -ForegroundColor Gray
    $result = python -m pip install $pkg --quiet
}

Write-Host "      Dependances OK" -ForegroundColor Green

# -- 3. Telecharger le dataset NTHU-DDD -----------------------------------

Write-Host ""
Write-Host "[3/5] Telechargement NTHU-DDD (environ 2 Go)..." -ForegroundColor Cyan
Write-Host "      Dataset : samymesbah/nthu-dataset-ddd-multi-class" -ForegroundColor Gray
Write-Host "      Patience - premiere fois 5 a 15 minutes selon connexion" -ForegroundColor Gray
Write-Host ""

$downloadScript = @'
import kagglehub, os
print("Connexion Kaggle...")
path = kagglehub.dataset_download("samymesbah/nthu-dataset-ddd-multi-class")
print("DATASET_PATH=" + path)
with open("_dataset_path.txt", "w") as f:
    f.write(path)
'@

$downloadScript | python -

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Telechargement echoue. Verifie ta connexion et ton token Kaggle." -ForegroundColor Red
    exit 1
}

$datasetPath = Get-Content "_dataset_path.txt" -ErrorAction Stop
Remove-Item "_dataset_path.txt" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "      Dataset telecharge : $datasetPath" -ForegroundColor Green

# -- 4. Lancer l'analyse EAR/MAR/PERCLOS ---------------------------------

Write-Host ""
Write-Host "[4/5] Analyse du dataset avec MediaPipe..." -ForegroundColor Cyan
Write-Host "      Traitement des videos - 10 a 30 minutes selon config" -ForegroundColor Gray
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

python "$scriptDir\analyse_nthu.py" `
    --dataset "$datasetPath" `
    --max_images 8000 `
    --sortie "$scriptDir\resultats_nthu"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Analyse echouee. Voir les logs ci-dessus." -ForegroundColor Red
    exit 1
}

# -- 5. Afficher les seuils et patcher detection_somnolence.py -----------

Write-Host ""
Write-Host "[5/5] Mise a jour des seuils dans detection_somnolence.py..." -ForegroundColor Cyan

$seuilsFile = "$scriptDir\resultats_nthu\seuils_valides_nthu.json"
if (Test-Path $seuilsFile) {
    $seuils = Get-Content $seuilsFile | ConvertFrom-Json
    Write-Host ""
    Write-Host "  Seuils valides sur NTHU-DDD :" -ForegroundColor Green
    Write-Host "  ----------------------------"
    Write-Host "  EAR optimal     = $($seuils.EAR)   (defaut 0.25)" -ForegroundColor White
    Write-Host "  MAR optimal     = $($seuils.MAR)   (defaut 0.65)" -ForegroundColor White
    Write-Host "  PERCLOS optimal = $($seuils.PERCLOS)   (defaut 0.35)" -ForegroundColor White
    Write-Host "  AUC EAR         = $($seuils.auc_ear)" -ForegroundColor White
    Write-Host "  Frames traites  = $($seuils.n_frames)  sur $($seuils.n_videos) videos" -ForegroundColor White
    Write-Host ""
    Write-Host "  Rapport    : $scriptDir\resultats_nthu\rapport_nthu.txt" -ForegroundColor Cyan
    Write-Host "  Courbe ROC : $scriptDir\resultats_nthu\roc_curves_nthu.png" -ForegroundColor Cyan
    Write-Host "  Distrib.   : $scriptDir\resultats_nthu\distribution_ear_nthu.png" -ForegroundColor Cyan

    Write-Host ""
    Write-Host "      Patching detection_somnolence.py..." -ForegroundColor Cyan
    python "$scriptDir\maj_seuils.py" `
        --seuils "$scriptDir\resultats_nthu\seuils_valides_nthu.json" `
        --detection "$scriptDir\detection_somnolence.py"
} else {
    Write-Host "  ATTENTION : seuils_valides_nthu.json non trouve" -ForegroundColor Yellow
    Write-Host "  Cherche dans : $seuilsFile" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  TERMINE - Seuils valides sur donnees reelles NTHU-DDD !" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Commit + push GitHub :" -ForegroundColor Yellow
Write-Host "  cd $scriptDir\.." -ForegroundColor White
Write-Host "  git add -A" -ForegroundColor White
Write-Host "  git commit -m 'feat: seuils EAR/MAR/PERCLOS valides NTHU-DDD (ROC + Youden)'" -ForegroundColor White
Write-Host "  git push origin main" -ForegroundColor White
Write-Host ""
