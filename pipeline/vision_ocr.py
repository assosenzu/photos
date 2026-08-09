"""Appels à Google Cloud Vision (TEXT_DETECTION) avec limite de débit."""

import re
import threading
import time

# Tarif TEXT_DETECTION : 1,50 $ les 1000 images, les 1000 premières de
# chaque mois gratuites.
PRIX_PAR_IMAGE_USD = 1.50 / 1000
QUOTA_GRATUIT_MENSUEL = 1000

# Un dossard fait entre 1 et 5 chiffres. On capture large : le tri entre
# vrais dossards et faux positifs se fait ensuite contre le CSV.
RE_NOMBRE = re.compile(r"\b\d{1,5}\b")


def extraire_nombres(texte):
    """Nombres candidats du texte OCR, sans doublons, ordre d'apparition."""
    vus = []
    for m in RE_NOMBRE.findall(texte):
        if m not in vus:
            vus.append(m)
    return vus


class LecteurVision:
    """Client Vision partagé entre threads, avec un débit maximum global."""

    def __init__(self, requetes_par_seconde=5.0):
        from google.cloud import vision

        self._vision = vision
        self._client = vision.ImageAnnotatorClient()
        self._intervalle = 1.0 / max(requetes_par_seconde, 0.1)
        self._verrou = threading.Lock()
        self._prochain_depart = 0.0

    def _respecter_debit(self):
        with self._verrou:
            maintenant = time.monotonic()
            depart = max(maintenant, self._prochain_depart)
            self._prochain_depart = depart + self._intervalle
        attente = depart - time.monotonic()
        if attente > 0:
            time.sleep(attente)

    def lire_texte(self, chemin):
        """Texte complet détecté sur la photo (chaîne vide si rien)."""
        self._respecter_debit()
        image = self._vision.Image(content=self._contenu_image(chemin))
        reponse = self._client.text_detection(image=image)
        if reponse.error.message:
            raise RuntimeError(reponse.error.message)
        if not reponse.text_annotations:
            return ""
        return reponse.text_annotations[0].description

    @staticmethod
    def _contenu_image(chemin):
        """Octets à envoyer à Vision.

        JPEG et PNG partent tels quels ; les autres formats acceptés par le
        pipeline (HEIC…) sont réencodés en JPEG, que l'API ne les accepte pas
        directement.
        """
        chemin = str(chemin)
        if chemin.lower().endswith((".jpg", ".jpeg", ".png")):
            with open(chemin, "rb") as f:
                return f.read()
        import io

        from PIL import Image, ImageOps

        from pipeline import images  # noqa: F401 (active le support HEIF)

        with Image.open(chemin) as brut:
            image = ImageOps.exif_transpose(brut).convert("RGB")
        tampon = io.BytesIO()
        image.save(tampon, "JPEG", quality=90)
        return tampon.getvalue()
