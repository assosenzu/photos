"""Upload vers Supabase Storage (bucket public photos-{slug})."""

from pathlib import Path


class ErreurStockage(Exception):
    pass


class StockageSupabase:
    def __init__(self, url, cle_service, bucket):
        if not url or not cle_service:
            raise ErreurStockage(
                "SUPABASE_URL et SUPABASE_SERVICE_KEY doivent être renseignés "
                "dans le fichier .env (voir README, section Supabase).\n"
                "Pour traiter les photos sans uploader, utilise --sans-upload."
            )
        from supabase import create_client

        self.bucket = bucket
        try:
            self._client = create_client(url, cle_service)
        except Exception as e:
            raise ErreurStockage(
                f"connexion à Supabase impossible : {e}\n"
                "Vérifie SUPABASE_URL (forme : https://xxxx.supabase.co) et la "
                "clé service_role dans le .env."
            )
        self._assurer_bucket()

    def _assurer_bucket(self):
        try:
            self._client.storage.get_bucket(self.bucket)
            return
        except Exception:
            pass
        try:
            self._client.storage.create_bucket(self.bucket, options={"public": True})
        except TypeError:
            # Anciennes versions du client : signature sans options
            self._client.storage.create_bucket(self.bucket)
        except Exception as e:
            raise ErreurStockage(
                f"impossible de créer le bucket '{self.bucket}' : {e}\n"
                "Vérifie que la clé utilisée est bien la clé service_role "
                "(pas la clé anon) — Supabase, Settings, API."
            )

    def deposer(self, chemin_local, chemin_distant, content_type="image/jpeg"):
        """Upload (écrase si déjà présent) et retourne l'URL publique."""
        contenu = Path(chemin_local).read_bytes()
        self._client.storage.from_(self.bucket).upload(
            chemin_distant,
            contenu,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return self.url_publique(chemin_distant)

    def url_publique(self, chemin_distant):
        url = self._client.storage.from_(self.bucket).get_public_url(chemin_distant)
        return url.rstrip("?")

    def supprimer(self, chemins_distants):
        """Supprime des fichiers du bucket (liste de chemins)."""
        self._client.storage.from_(self.bucket).remove(chemins_distants)

    def detruire_bucket(self):
        """Vide puis supprime le bucket entier."""
        self._client.storage.empty_bucket(self.bucket)
        self._client.storage.delete_bucket(self.bucket)
