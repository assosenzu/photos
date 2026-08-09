# Notes produit

Carnet des décisions et des pistes discutées en cours de route, pour ne pas
les reperdre. Le README dit comment l'outil marche, ce fichier dit pourquoi
il est comme ça et où on pense aller.

## Décisions prises

**Marque blanche.** L'outil ne contient aucune référence en dur à SENZU :
nom, site, couleurs et watermark viennent du bloc `organisateur` de chaque
`event.yaml`. Objectif : pouvoir le proposer à n'importe quel club ou
organisateur, SENZU n'étant qu'un utilisateur (et la vitrine).

**Pas de login organisateur, tri fait en interne.** On a envisagé un compte
organisateur avec édition en ligne des photos mal classées, puis écarté :
l'organisateur achète un résultat, pas un outil, et le tri ne demande aucune
connaissance qu'il aurait en plus de nous. Le tri manuel fait partie de la
prestation — c'est même un argument (« notre équipe vérifie le reste, vous
n'avez rien à faire ») et il est chiffrable : ~10 secondes par cas, soit
grosso modo une heure pour un événement de 3000 photos à 86 % d'automatique.
Le poste de tri (`galerie/admin.html`) reste donc un outil local interne,
sans authentification ni hébergement. Si un jour le tri devient un goulot
(beaucoup de clients), on ressortira l'idée du compte client — architecture
esquissée à l'époque : auth Supabase par lien magique, corrections dans un
fichier séparé de l'index pour survivre aux retraitements.

**Le taux de réussite se mesure, il ne s'annonce pas.** L'argumentaire
commercial (« 86 % classées automatiquement ») doit sortir de
`annoter.html` + `evaluer.py` sur de vraies courses, pas d'une estimation.
Le chiffre variera selon la qualité des photos : présenter une fourchette
mesurée sur plusieurs événements plutôt qu'un chiffre unique.

## Modèle économique — en réflexion

Idée de départ : trois formules. F1 la techno seule, F2 techno + l'organisateur
fait le tri lui-même (surcoût), F3 techno + tri fait par nous (encore plus
cher).

Objections soulevées, à trancher :

- F2 a un problème de logique de prix : le client paierait plus cher que F1
  pour travailler lui-même. Le surcoût ne peut se justifier que par l'outil
  d'édition en ligne — qui est précisément la brique la plus chère à
  construire et à maintenir (login, sécurité, support), pour la formule du
  milieu.
- Le tri ne coûtant qu'environ une heure par événement, l'écart de prix
  F1→F3 peut rester modeste. Un F2 coincé entre les deux n'a presque pas
  d'espace : pour quelques dizaines d'euros de plus, autant prendre F3.
- Risque de F1 : les photos introuvables (les 14 %) donnent une mauvaise
  image de la techno elle-même, même si c'est le choix de formule du client.
  Le nom de l'outil est sur toutes les galeries.

Piste alternative : deux formules seulement. F1 « brut » (traitement
automatique + galerie, prix plancher, éventuellement comme offre d'essai) et
F3 « fini » (tri inclus, l'offre recommandée). Garder F2 en réserve pour le
jour où le volume de tri deviendra un vrai coût — là, le déléguer à certains
clients (gros événements, plusieurs milliers de photos) redeviendra pertinent
et le développement du login se justifiera.

## Pistes à creuser

**Formats de photos.** Réglé pour l'essentiel : le pipeline accepte JPEG,
PNG et HEIC (iPhone), tout ressort en JPEG. Le RAW (NEF, CR3, ARW…) reste
volontairement hors périmètre : fichiers énormes, rendu à faire, dépendances
lourdes — et la pratique du métier est que le photographe livre des JPEG
exportés. C'est une consigne à donner aux photographes, pas du code à écrire.
À rouvrir seulement si un photographe partenaire ne peut vraiment pas faire
autrement.

**Navigation par épreuve.** Question posée : faut-il des « pages » par
épreuve (l'organisateur arrive sur La Pauléenne, puis sous-dossiers 5 km,
10 km…) ? Réponse actuelle : pas besoin de structure de dossiers — chaque
photo est rattachée à ses courses via les dossards détectés, et la galerie
sait déjà filtrer. Les liens directs `?course=5km` donnent à l'organisateur
une URL par épreuve à mettre sur son site, ce qui produit le même effet
qu'un sous-dossier sans dupliquer quoi que ce soit. Cas des courses
simultanées : non ambigu pour l'outil, une photo avec un coureur du 5 km et
un du 10 km apparaît dans les deux filtres. Limite connue : les photos
d'ambiance (sans dossard) ne sont rattachées à aucune épreuve, elles ne
sortent que dans la vue « toutes les courses ». Si un jour on veut des
sous-épreuves hiérarchiques (relais, catégories d'âge…), ça passera par une
structure de courses dans event.yaml, pas par des dossiers.

**Conservation et RGPD.** Le cadre est posé dans RGPD.md (info des
participants, retrait outillé, purge outillée). Deux paramètres restent des
choix d'organisateur à inscrire dans sa clause d'information : le délai de
retrait (7 jours proposés) et la durée de mise en ligne (12 mois proposés).
Reste aussi à tenir la ligne de registre des traitements, et un modèle de
contrat de sous-traitance le jour où l'outil est vendu à un organisateur
extérieur.

**Premier passage en conditions réelles.** Les appels Vision et Supabase
n'ont encore jamais tourné avec de vraies clés — à valider sur un petit lot
avant le premier événement (voir CLAUDE.md, « Tester sans clés »).

**Stockage multi-événements.** Le plan gratuit Supabase (1 Go) tient environ
un événement. Passage au plan Pro ou purge des anciens buckets à décider
quand le deuxième événement arrivera.

**Identité SENZU.** Logo (pour le watermark) et couleurs officielles jamais
fournis — la démo utilise une palette orange plausible. À récupérer avant la
première vraie galerie publiée.
