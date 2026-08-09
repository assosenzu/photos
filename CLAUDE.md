# CLAUDE.md

Outil de galerie photos de courses avec recherche par numéro de dossard.
OCR des dossards via Google Cloud Vision (pas de reconnaissance faciale),
validation contre la liste des inscrits, hébergement des images sur Supabase
Storage, galerie statique en JS vanilla. L'utilisateur principal ne code pas :
tout doit rester pilotable par des commandes simples documentées dans
README.md et GUIDE.md, avec des messages d'erreur en français qui renvoient à
la bonne section de doc.

## Conventions

- Code, identifiants, messages et documentation en français.
- Outil "marque blanche" : aucune référence en dur à un organisateur dans le
  code. Toute l'identité (nom, site, couleurs, watermark) vient du bloc
  `organisateur` de l'`event.yaml` et transite par `index.json`.
- Galerie et page admin : un seul fichier HTML chacun, zéro dépendance,
  zéro build.
- Les noms des participants ne sortent jamais dans `index.json` (publié sur
  un bucket public) — uniquement numéros, confiance et course.

## Flux de données

```
input/*.jpg
   └─ scripts/process_event.py <event.yaml>
        ├─ pipeline/vision_ocr.py     OCR (débit limité, coût affiché avant)
        ├─ pipeline/matching.py       candidats → dossards (haute/moyenne)
        ├─ pipeline/images.py         miniature 800 q80, web 1600 q85 + watermark
        ├─ pipeline/stockage.py       bucket public Supabase photos-{slug}
        └─ pipeline/journal.py        output/{slug}/journal.jsonl (reprise)
             └─ pipeline/index_builder.py → output/{slug}/index.json
                                            + upload en racine du bucket
galerie/index.html   lit index.json (constante INDEX_PAR_DEFAUT ou ?index=)
galerie/admin.html   poste de tri : confiance "moyenne" à valider/rejeter,
                     photos sans dossard (saisie manuelle contrôlée par
                     dossards_connus, ou marquage "ambiance")
   └─ scripts/apply_validations.py    réécrit le journal, régénère l'index
galerie/annoter.html annotation d'une vérité terrain → verite.json
   └─ scripts/evaluer.py              taux de bon classement vs index.json
```

## Points de design à connaître

- **Reprise** : `journal.jsonl` est la source de vérité, une ligne JSON par
  photo traitée, écrite après upload. Relancer la même commande saute ce qui
  y figure ; l'index est reconstruit intégralement depuis le journal à chaque
  exécution. Une ligne tronquée (arrêt brutal) est ignorée et la photo
  retraitée.
- **Confiance "moyenne"** : un nombre lu qui n'est pas un dossard mais qui
  est préfixe ou suffixe d'exactement un dossard du CSV lui est attribué avec
  `confiance: "moyenne"` et le fragment lu dans `lu`. Deux dossards
  compatibles → rejet. Longueur minimale du fragment : 2 chiffres.
- **index.json expose aussi** : `dossards_connus` ({numéro: course}, sans
  les noms — équivalent d'une liste de départ, publiable) pour le contrôle
  des saisies manuelles, et un drapeau `verifiee` sur les photos passées au
  poste de tri, pour qu'elles ne reviennent pas dans la file "sans dossard".
- **validations.json** (export admin) porte quatre décisions : `valider`,
  `rejeter` (cas moyenne), `ajouter` (saisie manuelle, refusée hors liste des
  participants) et `ambiance` (photo vérifiée sans dossard).
- **URLs dans index.json** : absolues (Supabase) en mode normal, relatives à
  la racine du dépôt avec `--sans-upload`. Les pages HTML résolvent les
  chemins non-http en les préfixant de `/` — d'où le `python -m http.server`
  lancé depuis la racine.
- **Supabase** : la signature de `storage.create_bucket` varie selon les
  versions du client Python ; `pipeline/stockage.py` a un repli. En cas de
  problème d'upload, c'est le premier endroit à regarder.
- **Watermark** : appliqué seulement aux versions web au moment du
  traitement. L'ajouter après coup implique de retraiter (donc re-payer
  l'OCR) — c'est documenté et assumé.
- **Vision** : quota par défaut largement suffisant ; le limiteur de débit
  (5 req/s, `--debit`) est un garde-fou. Arrêt automatique si les premières
  photos échouent toutes (mauvaise clé, API désactivée) pour ne pas insister
  inutilement.

## Tester sans clés

Aucun test automatisé versionné pour l'instant ; ce qui a été utilisé en
développement :

- tout le pipeline hors API se teste hors-ligne (config, matching, images
  avec EXIF, journal, index) — voir l'historique de la session, scripts dans
  le scratchpad ;
- la galerie et l'admin se testent avec Playwright sur le jeu de démo
  (`galerie/demo/`, régénérable par `scripts/generer_demo.py`) servi par
  `python -m http.server` depuis la racine ;
- `--sans-upload --limite N` permet un vrai run Vision sans toucher Supabase.

Ce qui n'a jamais tourné contre les vrais services : les appels Vision et
Supabase réels. Au premier run réel, surveiller `stockage.py` (versions du
client) et le format des URLs publiques.

## Contexte produit

Les décisions non techniques (marque blanche, tri interne plutôt que login
organisateur, modèle économique en réflexion, formats photos à venir) sont
consignées dans NOTES.md — le lire avant de proposer une évolution qui
toucherait au positionnement de l'outil.
