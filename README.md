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

Phase 1 (ce dépôt aujourd'hui) : la structure, la configuration Google Cloud
et un script de test qui analyse 5 photos pour vérifier que tout marche.
Les phases suivantes ajouteront le pipeline complet (miniatures, watermark,
upload Supabase), la galerie et la documentation d'exploitation.

## Contenu du dépôt

```
events/exemple/       exemple de configuration d'événement (event.yaml + participants.csv)
scripts/test_vision.py   script de test de l'OCR sur quelques photos
input/                déposer ici les photos à analyser (jamais versionnées)
secrets/              déposer ici la clé Google Cloud (jamais versionnée)
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

## Préparer un événement

Copie le dossier `events/exemple/` sous un nouveau nom, par exemple
`events/pauleenne-2026/`, et adapte `event.yaml` : slug, nom, date, liste des
courses et chemin du CSV. C'est ce fichier qui pilotera tout le pipeline en
phase 2.
