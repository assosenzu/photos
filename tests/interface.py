#!/usr/bin/env python3
"""Tests navigateur de la galerie, du poste de tri et de l'annotation.

Nécessite le paquet playwright et un Chromium (celui de Playwright, ou un
chemin passé dans CHROMIUM). Se lance depuis n'importe où :
    pip install playwright && playwright install chromium   # une fois
    python tests/interface.py
"""

import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PORT = 8143

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Paquet playwright absent (pip install playwright) — tests sautés.")
    sys.exit(0)


def trouver_chromium():
    if os.environ.get("CHROMIUM"):
        return os.environ["CHROMIUM"]
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if base:
        candidats = glob.glob(f"{base}/chromium-*/chrome-linux/chrome")
        if candidats:
            return sorted(candidats)[-1]
    return None  # laisser Playwright utiliser son installation par défaut


ok = 0
serveur = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(PORT)],
    cwd=RACINE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(1)


def check(cond, msg):
    global ok
    if not cond:
        print(f"FAIL: {msg}")
        serveur.terminate()
        sys.exit(1)
    ok += 1


try:
    with sync_playwright() as p:
        executable = trouver_chromium()
        navigateur = p.chromium.launch(
            **({"executable_path": executable} if executable else {}))
        page = navigateur.new_page(viewport={"width": 1200, "height": 900})
        erreurs_js = []
        page.on("pageerror", lambda e: erreurs_js.append(str(e)))

        # --- galerie
        page.goto(f"http://localhost:{PORT}/galerie/")
        page.wait_for_selector(".carte-photo img")
        check("Pauléenne" in page.title(), f"titre: {page.title()}")
        check("SENZU" in page.inner_text("#nom-organisateur"), "nom organisateur")
        check("12" in page.inner_text("#compteur"), "compteur initial")
        accent = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        check(accent == "#e27410", f"couleur organisateur appliquée: {accent}")

        page.fill("#champ-dossard", "245")
        compteur = page.inner_text("#compteur")
        check("2" in compteur and "245" in compteur, f"recherche: {compteur}")
        page.fill("#champ-dossard", "9999")
        check("Aucune photo" in page.inner_text("#compteur"), "dossard inconnu")
        page.click("#bouton-effacer")

        page.click(".puce:text-is('10km')")
        check("4" in page.inner_text("#compteur"), "filtre course")
        page.click(".puce:text-is('10h (4)')")
        check("4" in page.inner_text("#compteur"), "filtre tranche horaire")

        page.locator(".carte-photo").first.click()
        page.wait_for_selector(".lightbox.ouverte")
        page.keyboard.press("ArrowRight")
        check("2/4" in page.inner_text("#lb-infos"), "navigation lightbox")
        with page.expect_download() as dl:
            page.click("#lb-telecharger")
        check(dl.value.suggested_filename.endswith(".jpg"), "téléchargement en .jpg")
        page.keyboard.press("Escape")

        # liens directs par épreuve / dossard
        page.goto(f"http://localhost:{PORT}/galerie/?course=10km")
        page.wait_for_selector(".carte-photo img")
        check("4" in page.inner_text("#compteur"), "lien direct ?course=10km")
        check("active" in page.locator(".puce:text-is('10km')").get_attribute("class"),
              "puce course active via lien direct")
        page.goto(f"http://localhost:{PORT}/galerie/?dossard=245")
        page.wait_for_selector(".carte-photo img")
        check("245" in page.inner_text("#compteur"), "lien direct ?dossard=245")
        check(page.input_value("#champ-dossard") == "245", "champ prérempli")

        # sans bloc organisateur : neutre
        idx = json.loads((RACINE / "galerie/demo/index.json").read_text())
        del idx["organisateur"]
        neutre = RACINE / "galerie/demo/index-neutre.json"
        neutre.write_text(json.dumps(idx))
        page.goto(f"http://localhost:{PORT}/galerie/?index=galerie/demo/index-neutre.json")
        page.wait_for_selector(".carte-photo img")
        check(page.locator("#nom-organisateur").is_hidden(), "en-tête neutre")
        accent = page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()")
        check(accent == "#2563eb", "palette neutre par défaut")

        # --- poste de tri
        page.goto(f"http://localhost:{PORT}/galerie/admin.html")
        page.wait_for_selector(".cas")
        check(page.locator("#liste-incertaines .cas").count() == 3, "3 lectures incertaines")
        check(page.locator("#liste-sans .cas").count() == 2, "2 photos sans dossard")
        page.locator("#liste-incertaines .valider").first.click()
        premier_sans = page.locator("#liste-sans .cas").first
        premier_sans.locator("input").fill("9999")
        premier_sans.locator(".ajouter").click()
        check("pas dans la liste" in premier_sans.locator(".probleme").inner_text(),
              "saisie hors liste refusée")
        premier_sans.locator("input").fill("501")
        premier_sans.locator("input").press("Enter")
        check(page.locator("#liste-sans .chip").count() == 1, "dossard ajouté")
        page.locator("#liste-sans .ambiance").nth(1).click()
        with page.expect_download() as dl:
            page.click("#exporter")
        contenu = json.loads(Path(dl.value.path()).read_text())
        decisions = {d["decision"] for d in contenu["decisions"]}
        check(decisions == {"valider", "ajouter", "ambiance"},
              f"décisions exportées: {decisions}")

        # --- annotation
        page.goto(f"http://localhost:{PORT}/galerie/annoter.html")
        page.wait_for_selector("#poste:not([hidden])")
        page.fill("#champ", "101")
        page.press("#champ", "Enter")
        check("photo 2/12" in page.inner_text("#fichier"), "photo suivante")
        page.click("#aucun")
        with page.expect_download() as dl:
            page.click("#exporter")
        verite = json.loads(Path(dl.value.path()).read_text())
        check(len(verite["photos"]) == 2 and verite["photos"][1]["dossards"] == [],
              "vérité terrain exportée")

        check(not erreurs_js, f"erreurs JS: {erreurs_js}")
        navigateur.close()
finally:
    serveur.terminate()
    (RACINE / "galerie/demo/index-neutre.json").unlink(missing_ok=True)

print(f"{ok} vérifications navigateur OK")
