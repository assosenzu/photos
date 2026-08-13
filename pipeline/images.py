"""Miniatures, versions web et horodatage EXIF."""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

# Support des photos HEIC/HEIF (iPhone) quand pillow-heif est installé —
# sans lui, seuls JPEG et PNG sont lus.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_DISPONIBLE = True
except ImportError:
    HEIF_DISPONIBLE = False

TAILLE_MINIATURE = 800
TAILLE_WEB = 1600
QUALITE_MINIATURE = 80
QUALITE_WEB = 85

EXIF_DATE_ORIGINALE = 36867  # DateTimeOriginal
EXIF_IFD = 0x8769


def horodatage_exif(chemin):
    """Date de prise de vue au format ISO ('2026-05-17T10:23:45'), ou None."""
    try:
        with Image.open(chemin) as img:
            exif = img.getexif()
            brut = exif.get_ifd(EXIF_IFD).get(EXIF_DATE_ORIGINALE) or exif.get(306)
        if not brut:
            return None
        return datetime.strptime(str(brut).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
    except Exception:
        return None


def generer_versions(chemin, dossier_miniatures, dossier_web):
    """Écrit la miniature et la version web ; retourne leurs chemins.

    Quel que soit le format d'entrée (JPEG, PNG, HEIC), les sorties sont
    toujours des JPEG.
    """
    nom = Path(chemin).stem + ".jpg"
    chemin_miniature = Path(dossier_miniatures) / nom
    chemin_web = Path(dossier_web) / nom

    with Image.open(chemin) as brut:
        image = ImageOps.exif_transpose(brut).convert("RGB")

    web = image.copy()
    web.thumbnail((TAILLE_WEB, TAILLE_WEB), Image.LANCZOS)
    web.save(chemin_web, "JPEG", quality=QUALITE_WEB, optimize=True)

    image.thumbnail((TAILLE_MINIATURE, TAILLE_MINIATURE), Image.LANCZOS)
    image.save(chemin_miniature, "JPEG", quality=QUALITE_MINIATURE, optimize=True)

    return chemin_miniature, chemin_web
