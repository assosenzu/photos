# SENZU Photos

Retrouver ses photos de course en tapant son numéro de dossard. Le principe :
un pipeline Python lit les photos d'un événement, détecte les dossards par OCR
(Google Cloud Vision), croise avec la liste des inscrits pour éliminer les faux
positifs, puis publie une galerie web où chaque participant cherche son numéro.
Pas de reconnaissance faciale, uniquement de la lecture de texte — aucune
donnée biométrique.

Le projet est prévu pour être multi-événements : chaque course a son dossier
dans `events/` avec sa configuration et sa liste de participants.

## Où on en est

Pipeline et galerie sont fonctionnels : OCR, validation par la liste des
inscrits, récupération des lectures partielles, miniatures, watermark
(optionnel), upload Supabase, index, galerie de recherche par dossard et page
admin de validation. L'outil est générique : toute l'identité (nom, site,
couleurs, logo) se règle dans l'`event.yaml` de chaque organisateur, le code
ne contient rien de spécifique à SENZU.

## Contenu du dépôt

```
events/exemple/       exemple de configuration d'événement (event.yaml + participants.csv)
pipeline/             les briques du traitement (OCR, validation, images, upload…)
galerie/index.html    la galerie publique (recherche par dossard)
galerie/admin.html    la page de validation des lectures incertaines
galerie/demo/         jeu de démonstration pour tester la galerie sans rien configurer
scripts/test_vision.py     test de l'OCR sur quelques photos
scripts/process_event.py   le pipeline complet d'un événement
scripts/apply_validations.py   applique les décisions de la page admin
input/                déposer ici les photos à traiter (jamais versionnées)
secrets/              déposer ici la clé Google Cloud (jamais versionnée)
assets/               logo pour le watermark (optionnel, voir plus bas)
output/               fichiers générés : miniatures, index, journal (jamais versionnés)
.env.example          modèle de configuration, à copier en .env
requirements.txt      dépendances Python
```

## Créer le compte Google Cloud

Il faut le faire une seule fois, compte environ 20 minutes. Utilise de
préférence l'adresse Gmail de l'association plutôt qu'un compte perso, pour
que l'accès ne dépende pas d'une personne.

Côté coût : la lecture de texte est facturée 1,50 $ les 1000 images, et les
1000 premières images de chaque mois sont gratuites. Un événement de 3000
photos revient donc à environ 3 $. Google demande quand même une carte
bancaire à l'inscription, et offre 300 $ de crédit pendant 90 jours pour les
nouveaux comptes — les premiers événements ne coûteront rien.

### Étape 1 — créer le projet

1. Va sur [console.cloud.google.com](https://console.cloud.google.com) et
   connecte-toi avec le compte Google choisi.
2. À la première connexion, Google demande d'accepter les conditions
   d'utilisation : coche et valide.
3. En haut de la page, clique sur le sélecteur de projet (à côté du logo
   "Google Cloud"), puis sur **Nouveau projet**.
4. Nom du projet : `senzu-photos`. Laisse le reste par défaut et clique sur
   *Créer*.
5. Attends quelques secondes, puis vérifie dans le sélecteur en haut que le
   projet `senzu-photos` est bien sélectionné. Toutes les étapes suivantes se
   font dans ce projet.

### Étape 2 — activer la facturation

1. Menu ☰ (en haut à gauche) → *Facturation*.
2. Clique sur *Associer un compte de facturation* puis *Créer un compte de
   facturation*.
3. Renseigne le pays (France), le type de compte (choisis "Particulier" si
   l'association n'a pas de numéro de TVA), et une carte bancaire.
4. Valide. Google active en général le crédit d'essai de 300 $ à ce moment-là.

Rien n'est débité tant qu'on reste sous les 1000 images gratuites du mois ou
dans le crédit d'essai. On peut aussi définir une alerte de budget (menu
*Facturation* → *Budgets et alertes*) à 5 € pour dormir tranquille.

### Étape 3 — activer l'API Vision

1. Menu ☰ → *API et services* → *Bibliothèque*.
2. Dans la barre de recherche, tape `Cloud Vision API` et clique sur le
   résultat.
3. Clique sur **Activer**. C'est tout.

### Étape 4 — créer la clé de service

C'est le fichier qui permet au script de s'authentifier auprès de Google.

1. Menu ☰ → *IAM et administration* → *Comptes de service*.
2. Clique sur *Créer un compte de service*.
3. Nom : `senzu-photos-pipeline`. Clique sur *Créer et continuer*.
4. L'écran propose d'attribuer un rôle : ce n'est pas nécessaire pour Vision,
   clique simplement sur *Continuer* puis *OK*.
5. Dans la liste, clique sur le compte de service qui vient d'être créé, puis
   onglet *Clés* → *Ajouter une clé* → *Créer une clé* → format **JSON** →
   *Créer*. Un fichier `.json` se télécharge sur ton ordinateur.
6. Dans le Codespace, glisse-dépose ce fichier dans le dossier `secrets/` du
   projet (dans l'explorateur de fichiers à gauche) et renomme-le
   `gcp-vision-key.json`.

Ce fichier est une clé d'accès : il ne doit jamais être envoyé sur GitHub ni
partagé. Le `.gitignore` du dépôt l'exclut déjà, ne le déplace pas ailleurs.

### Étape 5 — configurer et installer

Dans le terminal du Codespace :

```bash
cp .env.example .env
pip install -r requirements.txt
```

Le `.env` par défaut pointe déjà vers `secrets/gcp-vision-key.json`, il n'y a
rien à modifier pour l'instant (les lignes Supabase serviront en phase 2).

## Tester sur 5 photos

Dépose 4 ou 5 photos de course (JPEG) dans le dossier `input/`, puis :

```bash
python scripts/test_vision.py
```

Le script affiche le coût estimé, demande confirmation, envoie chaque photo à
l'API et liste le texte lu et les nombres détectés. Pour voir la validation
par la liste des participants (le mécanisme qui éliminera les panneaux,
horaires et sponsors) :

```bash
python scripts/test_vision.py --csv events/exemple/participants.csv
```

Avec le CSV d'exemple, seuls les numéros 101, 102, 103, 115, 230, 231, 245,
258, 501 et 502 seront reconnus comme dossards — remplace-le par ton vrai
export d'inscriptions pour un test réaliste. Le format attendu est trois
colonnes `dossard,nom,course` (voir `events/exemple/participants.csv`).

Si le script affiche une erreur, le message indique l'étape du README à
reprendre (clé manquante, facturation, API non activée…).

## Créer le projet Supabase

C'est là que sont hébergées les photos traitées (miniatures et versions web)
ainsi que l'index que la galerie interroge. Un projet dédié, séparé des autres
projets Supabase de l'asso.

1. Sur [supabase.com](https://supabase.com), *New project* : nom
   `senzu-photos`, région `West EU` (Paris ou Francfort, peu importe), et un
   mot de passe de base de données quelconque — on ne se sert pas de la base,
   uniquement du stockage de fichiers. Garde-le quand même dans ton
   gestionnaire de mots de passe.
2. Une fois le projet créé : *Settings* → *API*. Copie deux valeurs dans le
   `.env` :
   - *Project URL* → `SUPABASE_URL`
   - la clé **service_role** (section "Project API keys", il faut cliquer
     pour la révéler) → `SUPABASE_SERVICE_KEY`

Attention à bien prendre la clé `service_role` et pas la clé `anon`. Cette
clé donne tous les droits sur le projet : elle reste dans le `.env`, jamais
dans git, jamais dans la galerie.

Il n'y a rien d'autre à préparer : le script crée lui-même un bucket public
`photos-{slug}` par événement.

Sur le plan gratuit, le stockage est limité à 1 Go — ça tient environ un
événement de 3000 photos en versions réduites. Pour en garder plusieurs en
ligne, il faudra soit passer au plan Pro (25 $/mois), soit supprimer les
buckets des anciens événements.

## Traiter un événement

D'abord préparer le dossier de l'événement : copie `events/exemple/` sous un
nouveau nom (par exemple `events/pauleenne-2026/`), adapte `event.yaml` (slug,
nom, date, courses, chemin du CSV) et remplace le CSV par le vrai export des
inscriptions. Puis dépose les photos JPEG dans `input/` et lance :

```bash
python scripts/process_event.py events/pauleenne-2026/event.yaml
```

Le script annonce le nombre de photos et le coût Vision estimé, attend ta
confirmation, puis traite tout : OCR, validation des dossards contre le CSV,
miniatures et versions web, upload, et enfin l'`index.json` publié dans le
bucket.

Deux points à connaître :

- Si ça s'interrompt (plantage, Ctrl+C, Codespace qui s'endort), relance
  exactement la même commande : les photos déjà traitées sont sautées, le
  travail reprend où il s'était arrêté.
- Un numéro lu partiellement (dossard plié, à moitié caché) est quand même
  attribué s'il ne peut correspondre qu'à un seul inscrit, avec une confiance
  "moyenne". Ces cas seront listés dans la page admin pour vérification.

Pour essayer sans rien envoyer sur Supabase, ou sur un petit échantillon :

```bash
python scripts/process_event.py events/pauleenne-2026 --sans-upload --limite 20
```

Autres options : `--dossier` pour lire les photos ailleurs que dans `input/`,
`--debit` pour ralentir les appels à Vision (5 par seconde par défaut),
`--workers` pour le nombre de photos traitées en parallèle, `--oui` pour
passer la confirmation.

## La galerie

Une seule page, sans framework ni dépendance : `galerie/index.html`. Elle
charge un `index.json` et offre la recherche par numéro de dossard, les
filtres par course et par tranche horaire, une lightbox et le téléchargement.
L'habillage (nom de l'organisateur, lien de contact, couleurs) vient du bloc
`organisateur` de l'`event.yaml` — sans ce bloc elle reste neutre.

Pour l'essayer tout de suite avec le jeu de démonstration, depuis la racine
du projet :

```bash
python -m http.server 8000
```

puis ouvre `http://localhost:8000/galerie/` dans le navigateur (dans un
Codespace, VS Code propose automatiquement d'ouvrir le port). Pour visualiser
un vrai événement traité en local :
`http://localhost:8000/galerie/?index=output/mon-evenement/index.json`.

En production, on dépose `galerie/index.html` sur n'importe quel hébergement
(le site de l'organisateur, GitHub Pages…) et on remplace la constante
`INDEX_PAR_DEFAUT` en tête de son script par l'URL publique de l'index
Supabase, affichée à la fin du traitement.

## Valider les lectures incertaines

Après un traitement, certains dossards sont attribués en "confiance moyenne" :
l'OCR n'a lu qu'un morceau de numéro qui ne peut correspondre qu'à un seul
inscrit. La page `galerie/admin.html` (à ouvrir en local, même serveur que
ci-dessus) les liste photo par photo :

```
http://localhost:8000/galerie/admin.html?index=output/mon-evenement/index.json
```

On valide ou rejette chaque cas, on clique sur *Exporter les décisions* (ça
télécharge un `validations.json`), puis :

```bash
python scripts/apply_validations.py events/mon-evenement/event.yaml validations.json
```

Les dossards validés passent en confiance haute, les rejetés disparaissent,
et l'index est régénéré puis republié sur Supabase. Cette page est un outil
interne : elle n'est pas destinée à être mise en ligne.

## Le watermark

Optionnel. Dépose le logo SENZU au format PNG (fond transparent de
préférence) dans `assets/watermark.png` : il sera incrusté discrètement en bas
à droite des versions web (pas des miniatures). Sans ce fichier, le script le
signale et continue sans watermark. Mieux vaut donc le mettre en place avant
de traiter un gros événement : l'ajouter après coup oblige à supprimer
`output/{slug}/` et à relancer le traitement complet, OCR compris.
