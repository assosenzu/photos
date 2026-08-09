#!/usr/bin/env python3
"""Tests hors-ligne du pipeline — tout sauf les appels Vision et Supabase.

Se lance sans aucune clé ni réseau :
    python tests/hors_ligne.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from PIL import Image

from pipeline.config import charger_evenement
from pipeline.images import (
    HEIF_DISPONIBLE,
    charger_watermark,
    generer_versions,
    horodatage_exif,
)
from pipeline.index_builder import construire_index, ecrire_index
from pipeline.journal import Journal
from pipeline.matching import associer
from pipeline.participants import charger_participants
from pipeline.vision_ocr import LecteurVision, extraire_nombres

ok = 0


def check(cond, msg):
    global ok
    if not cond:
        print(f"FAIL: {msg}")
        sys.exit(1)
    ok += 1


def test_config_et_matching():
    ev = charger_evenement(RACINE / "events/exemple/event.yaml")
    check(ev["slug"] == "pauleenne-2026" and "5km" in ev["courses"], "event.yaml")
    check(ev["organisateur"]["nom"], "bloc organisateur lu")
    parts = charger_participants(ev["participants_csv"], ev["courses"])
    check(parts["245"]["course"] == "10km", "participants")

    texte = "SENZU\n10:23\n245\nKM 5\n23\n2026"
    cands = extraire_nombres(texte)
    check(cands == ["10", "23", "245", "5", "2026"], f"extraction: {cands}")
    m = associer(cands, parts)
    check({d["numero"] for d in m} == {"245"}, f"exact, ambigus rejetés: {m}")
    check(associer(["50"], parts) == [], "préfixe de deux dossards -> rejet")
    m3 = associer(["11"], parts)
    check(m3 == [{"numero": "115", "confiance": "moyenne", "lu": "11"}], f"préfixe unique: {m3}")
    check(associer(["58"], parts)[0]["numero"] == "258", "suffixe unique")
    m5 = associer(["245", "45"], parts)
    check(len(m5) == 1 and m5[0]["confiance"] == "haute", "pas de doublon exact+partiel")
    return ev, parts


def test_images(tmp):
    src = tmp / "src"
    src.mkdir()
    exif = Image.Exif()
    exif[306] = "2026:05:17 10:23:45"
    Image.new("RGB", (3000, 2000), (200, 30, 30)).save(src / "a.jpg", exif=exif)
    Image.new("RGB", (2000, 3000), (30, 30, 200)).save(src / "b.png")

    check(horodatage_exif(src / "a.jpg") == "2026-05-17T10:23:45", "date EXIF")
    check(horodatage_exif(src / "b.png") is None, "EXIF absente")

    thumbs, web = tmp / "thumbs", tmp / "web"
    thumbs.mkdir(), web.mkdir()

    logo = Image.new("RGBA", (400, 120), (255, 255, 255, 255))
    logo.save(tmp / "logo.png")
    wm = charger_watermark(tmp / "logo.png")
    check(wm is not None and charger_watermark(tmp / "absent.png") is None, "watermark")

    t, w = generer_versions(src / "a.jpg", thumbs, web, wm)
    with Image.open(t) as ti, Image.open(w) as wi:
        check(max(ti.size) == 800 and max(wi.size) == 1600, "tailles miniature/web")
    t2, w2 = generer_versions(src / "b.png", thumbs, web, None)
    check(t2.name == "b.jpg" and w2.name == "b.jpg", "PNG converti en .jpg")
    with Image.open(w2) as wi2:
        check(wi2.size == (1067, 1600), f"portrait: {wi2.size}")

    # PNG part tel quel vers Vision, pas de réencodage
    check(
        LecteurVision._contenu_image(src / "b.png") == (src / "b.png").read_bytes(),
        "PNG envoyé tel quel à Vision",
    )

    if HEIF_DISPONIBLE:
        Image.new("RGB", (1200, 800), (10, 120, 60)).save(src / "c.heic")
        t3, _ = generer_versions(src / "c.heic", thumbs, web, None)
        check(t3.name == "c.jpg", "HEIC converti en .jpg")
        contenu = LecteurVision._contenu_image(src / "c.heic")
        check(contenu[:2] == b"\xff\xd8", "HEIC réencodé en JPEG pour Vision")
    else:
        print("(pillow-heif absent : tests HEIC sautés)")


def test_journal_et_index(tmp, ev, parts):
    j = Journal(tmp / "journal.jsonl")
    j.ajouter({"fichier": "a.jpg", "horodatage": "2026-05-17T10:23:45",
               "dossards": [{"numero": "115", "confiance": "moyenne", "lu": "11"}],
               "miniature": "m", "web": "w"})
    with open(tmp / "journal.jsonl", "a") as f:
        f.write('{"tronq')  # arrêt brutal simulé
    entrees = Journal(tmp / "journal.jsonl").entrees()
    check(list(entrees) == ["a.jpg"], "ligne tronquée ignorée")

    entrees["b.jpg"] = {"fichier": "b.jpg", "horodatage": None,
                        "dossards": [{"numero": "245", "confiance": "haute", "lu": "245"}],
                        "miniature": "m", "web": "w", "verifiee": True}
    idx = construire_index(ev, entrees, parts)
    check(idx["photos"][0]["fichier"] == "a.jpg", "tri: sans horodatage en dernier")
    check(idx["photos"][0]["dossards"][0]["lu"] == "11", "champ lu sur confiance moyenne")
    check("lu" not in idx["photos"][1]["dossards"][0], "pas de lu en confiance haute")
    check(idx["photos"][1]["verifiee"] is True, "drapeau verifiee propagé")
    check(idx["dossards_connus"]["245"] == "10km", "dossards_connus présent")
    contenu = json.dumps(idx, ensure_ascii=False)
    check(all(p["nom"] not in contenu for p in parts.values()),
          "aucun nom de participant dans l'index public")
    ecrire_index(idx, tmp / "index.json")
    check(json.loads((tmp / "index.json").read_text())["evenement"]["slug"]
          == ev["slug"], "index écrit et relu")


def test_scripts(tmp, ev):
    """apply_validations et retirer_photo, via un faux journal, sans upload."""
    cwd = tmp / "repo"
    (cwd / "output" / ev["slug"]).mkdir(parents=True)
    journal = cwd / "output" / ev["slug"] / "journal.jsonl"
    lignes = [
        {"fichier": "A.jpg", "horodatage": "2026-05-17T09:00:00",
         "dossards": [{"numero": "115", "confiance": "moyenne", "lu": "11"}],
         "miniature": "m/A.jpg", "web": "w/A.jpg"},
        {"fichier": "B.jpg", "horodatage": "2026-05-17T10:00:00",
         "dossards": [], "miniature": "m/B.jpg", "web": "w/B.jpg"},
        {"fichier": "C.jpg", "horodatage": "2026-05-17T11:00:00",
         "dossards": [], "miniature": "m/C.jpg", "web": "w/C.jpg"},
    ]
    journal.write_text("\n".join(json.dumps(l) for l in lignes) + "\n")

    validations = tmp / "validations.json"
    validations.write_text(json.dumps({"decisions": [
        {"fichier": "A.jpg", "numero": "115", "decision": "valider"},
        {"fichier": "B.jpg", "numero": "245", "decision": "ajouter"},
        {"fichier": "B.jpg", "numero": "9999", "decision": "ajouter"},
        {"fichier": "C.jpg", "decision": "ambiance"},
    ]}))
    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts/apply_validations.py"),
         str(RACINE / "events/exemple/event.yaml"), str(validations), "--sans-upload"],
        cwd=cwd, capture_output=True, text=True)
    check(r.returncode == 0, f"apply_validations: {r.stderr}")
    check("Refusé : B.jpg / dossard 9999" in r.stdout, "ajout hors liste refusé")
    idx = json.loads((cwd / "output" / ev["slug"] / "index.json").read_text())
    b = next(p for p in idx["photos"] if p["fichier"] == "B.jpg")
    check([d["numero"] for d in b["dossards"]] == ["245"] and b["verifiee"],
          "ajout manuel appliqué")
    c = next(p for p in idx["photos"] if p["fichier"] == "C.jpg")
    check(c["verifiee"] and not c["dossards"], "ambiance appliquée")

    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts/retirer_photo.py"),
         str(RACINE / "events/exemple/event.yaml"), "B.jpg", "--sans-upload"],
        cwd=cwd, capture_output=True, text=True)
    check(r.returncode == 0, f"retirer_photo: {r.stderr}")
    idx = json.loads((cwd / "output" / ev["slug"] / "index.json").read_text())
    check([p["fichier"] for p in idx["photos"]] == ["A.jpg", "C.jpg"],
          "photo retirée de l'index")
    restants = [json.loads(l)["fichier"]
                for l in journal.read_text().splitlines() if l.strip()]
    check(restants == ["A.jpg", "C.jpg"], "photo retirée du journal")

    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts/retirer_photo.py"),
         str(RACINE / "events/exemple/event.yaml"), "Z.jpg", "--sans-upload"],
        cwd=cwd, capture_output=True, text=True)
    check(r.returncode != 0 and "n'est pas dans le journal" in r.stderr,
          "retrait d'un fichier inconnu refusé")


def test_evaluer(tmp):
    verite = tmp / "verite.json"
    verite.write_text(json.dumps({"photos": [
        {"fichier": "demo_001.jpg", "dossards": ["101"]},
        {"fichier": "demo_005.jpg", "dossards": ["230", "231"]},
        {"fichier": "demo_012.jpg", "dossards": []},
    ]}))
    r = subprocess.run(
        [sys.executable, str(RACINE / "scripts/evaluer.py"),
         str(RACINE / "galerie/demo/index.json"), str(verite)],
        capture_output=True, text=True)
    check(r.returncode == 0, f"evaluer: {r.stderr}")
    check("2/3" in r.stdout and "manqué : 231" in r.stdout, f"bilan: {r.stdout}")


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        ev, parts = test_config_et_matching()
        test_images(tmp)
        test_journal_et_index(tmp, ev, parts)
        test_scripts(tmp, ev)
        test_evaluer(tmp)
    print(f"{ok} vérifications OK")


if __name__ == "__main__":
    main()
