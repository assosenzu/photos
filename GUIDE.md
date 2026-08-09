# Traiter les photos d'un nouvel événement

Ce guide suppose que l'installation est déjà faite (compte Google Cloud,
projet Supabase, `.env` rempli — sinon, commence par le README). Compte une
demi-heure de manipulation, plus le temps de traitement lui-même : environ
une heure pour 2000 photos, et ça tourne tout seul.

## 1. Créer le dossier de l'événement

Dans `events/`, copie le dossier `exemple` et renomme-le, par exemple
`events/run-bike-2026/`. Ouvre son `event.yaml` et adapte : le slug (minuscules
et tirets, il nomme le bucket en ligne), le nom, la date, la liste des courses,
et le bloc `organisateur` si l'habillage change.

## 2. Mettre la liste des inscrits

Exporte les inscriptions en CSV avec trois colonnes : `dossard,nom,course`.
Les noms de courses doivent être écrits exactement comme dans l'`event.yaml`
(un "5 km" avec espace d'un côté et "5km" de l'autre, et le filtre de la
galerie ne marchera pas — le script te préviendra). Remplace le
`participants.csv` du dossier par ce fichier.

Cette liste sert de filtre anti-faux-positifs : seuls les numéros qui y
figurent peuvent devenir des dossards. Plus elle est juste, meilleur est le
résultat.

## 3. Déposer les photos

Toutes les photos JPEG dans le dossier `input/`. Peu importe les sous-noms ou
l'ordre, mais vide-le des photos d'un ancien événement avant.

Si tu veux te rassurer d'abord, teste l'OCR sur cinq photos :
`python scripts/test_vision.py --csv events/run-bike-2026/participants.csv`

## 4. Lancer le traitement

```bash
python scripts/process_event.py events/run-bike-2026/event.yaml
```

Le script annonce le nombre de photos et le coût estimé (ordre de grandeur :
3 $ pour 3000 photos), et attend que tu confirmes. Ensuite il enchaîne tout
seul : lecture des dossards, miniatures, envoi en ligne.

Si ça s'interrompt — Codespace qui s'endort, coupure, Ctrl+C — relance
exactement la même commande : il reprend où il en était sans rien payer deux
fois. À la fin, il affiche l'adresse publique de l'index ; garde-la, c'est
elle qu'il faut donner à la galerie.

## 5. Trier ce que la machine n'a pas su lire

Le bilan de fin de traitement donne le nombre de cas à vérifier. Lance un
petit serveur local :

```bash
python -m http.server 8000
```

puis ouvre `http://localhost:8000/galerie/admin.html?index=output/run-bike-2026/index.json`.
Le poste de tri présente deux files : les lectures incertaines (valider ou
rejeter d'un clic) et les photos sans dossard détecté — regarde-les, saisis le
numéro quand il est lisible à l'œil, ou marque « aucun dossard lisible » pour
les photos d'ambiance. Ensuite, exporte les décisions et applique-les :

```bash
python scripts/apply_validations.py events/run-bike-2026/event.yaml validations.json
```

Compte une dizaine de secondes par cas. Tu peux aussi faire ce tri en
plusieurs fois : les cas déjà tranchés ne reviennent pas, et la galerie
fonctionne déjà pendant ce temps.

## 6. Mettre la galerie en ligne

Ouvre `galerie/index.html`, remplace la valeur de `INDEX_PAR_DEFAUT` (tout en
haut du bloc `<script>`) par l'adresse de l'index notée à l'étape 4, et dépose
ce fichier sur l'hébergement choisi. C'est tout : la page va chercher les
photos sur Supabase directement.

Avant d'annoncer le lien aux participants, fais le test de vérité : cherche
ton propre dossard, ouvre deux ou trois photos, télécharges-en une.

---

Pour connaître ton taux de réussite sur l'événement (utile en interne et pour
la communication), annote une centaine de photos avec
`galerie/annoter.html` puis lance `python scripts/evaluer.py` — la procédure
détaillée est dans le README, section « Mesurer le taux de réussite ».

Question fréquente : « un participant signale qu'une photo n'est pas de lui ».
Ouvre `output/{slug}/journal.jsonl`, cherche la ligne du fichier photo
concerné (Ctrl+F sur son nom), et supprime dans cette ligne le bloc
`{"numero": "…", …}` du dossard fautif. Relance ensuite
`python scripts/process_event.py events/…/event.yaml --oui` : rien n'est
retraité ni refacturé, l'index est simplement reconstruit et republié sans
cette attribution.
