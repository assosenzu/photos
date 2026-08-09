"""Miniatures, versions web, watermark et horodatage EXIF."""

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

TAILLE_MINIATURE = 800
TAILLE_WEB = 1600
QUALITE_MINIATURE = 80
QUALITE_WEB = 85

# Watermark : largeur relative à la photo, marge et opacité
WATERMARK_LARGEUR = 0.14
WATERMARK_MARGE = 0.02
WATERMARK_OPACITE = 0.6

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


def charger_watermark(chemin):
    """Charge le logo en RGBA avec l'opacité réduite, ou None s'il n'existe pas."""
    p = Path(chemin)
    if not p.is_file():
        return None
    logo = Image.open(p).convert("RGBA")
    alpha = logo.getchannel("A").point(lambda v: int(v * WATERMARK_OPACITE))
    logo.putalpha(alpha)
    return logo


def _appliquer_watermark(image, logo):
    largeur_logo = max(1, int(image.width * WATERMARK_LARGEUR))
    ratio = largeur_logo / logo.width
    logo_redim = logo.resize(
        (largeur_logo, max(1, int(logo.height * ratio))), Image.LANCZOS
    )
    marge = int(image.width * WATERMARK_MARGE)
    position = (
        image.width - logo_redim.width - marge,
        image.height - logo_redim.height - marge,
    )
    image.paste(logo_redim, position, logo_redim)


def generer_versions(chemin, dossier_miniatures, dossier_web, watermark=None):
    """Écrit la miniature et la version web ; retourne leurs chemins.

    La version web reçoit le watermark (si un logo est fourni), la miniature
    reste sans — elle est trop petite pour que ce soit lisible.
    """
    nom = Path(chemin).name
    chemin_miniature = Path(dossier_miniatures) / nom
    chemin_web = Path(dossier_web) / nom

    with Image.open(chemin) as brut:
        image = ImageOps.exif_transpose(brut).convert("RGB")

    web = image.copy()
    web.thumbnail((TAILLE_WEB, TAILLE_WEB), Image.LANCZOS)
    if watermark is not None:
        _appliquer_watermark(web, watermark)
    web.save(chemin_web, "JPEG", quality=QUALITE_WEB, optimize=True)

    image.thumbnail((TAILLE_MINIATURE, TAILLE_MINIATURE), Image.LANCZOS)
    image.save(chemin_miniature, "JPEG", quality=QUALITE_MINIATURE, optimize=True)

    return chemin_miniature, chemin_web
