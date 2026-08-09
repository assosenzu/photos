# RGPD et droit à l'image

Ce document fait le tour de ce que l'outil traite comme données personnelles,
de ce qui a été prévu pour rester dans les clous, et de ce qu'il reste à
faire côté organisation. Ce n'est pas un avis juridique — pour un doute
sérieux, consulter la CNIL (cnil.fr) ou un professionnel.

## Ce que l'outil traite, et ce qu'il ne traite pas

Des photos de personnes identifiables sont des données personnelles : leur
publication est donc un traitement au sens du RGPD, avec ou sans outil
automatique. Ce que fait notre pipeline en plus, c'est lire les numéros de
dossard par OCR — de la lecture de texte, exactement comme lire un panneau.

Le point qui compte : **aucune donnée biométrique**. Pas de reconnaissance
faciale, pas de gabarit de visage, rien qui identifie quelqu'un par ses
caractéristiques physiques. C'est la différence majeure avec certains
concurrents, et c'est ce qui nous évite le régime des données sensibles
(article 9), le plus contraignant du RGPD. À dire tel quel aux organisateurs.

Dans le détail, ce qui existe et où :

- les photos publiées (bucket Supabase public) : versions réduites,
  cherchables par numéro de dossard uniquement ;
- l'`index.json` public : numéros de dossard, course, horodatage — jamais
  les noms. Quelqu'un qui connaît un numéro peut voir les photos associées,
  comme sur n'importe quel affichage de résultats de course ;
- le CSV des participants (noms + dossards) : reste sur la machine de
  l'opérateur, n'est jamais téléversé nulle part ;
- Google Cloud Vision reçoit chaque photo le temps de l'analyse. Google
  s'engage contractuellement à ne pas conserver ni réutiliser les images des
  clients de l'API (Data Processing Addendum de Google Cloud) ;
- Supabase héberge les photos publiées — choisir une région UE à la création
  du projet (c'est ce que dit le README).

## Qui est responsable de quoi

L'organisateur de la course est le responsable de traitement : c'est lui qui
décide de publier les photos et c'est vers lui que les participants se
tournent. Nous (l'opérateur de l'outil) agissons comme sous-traitant, avec
Google et Supabase comme sous-traitants ultérieurs. Quand l'outil sera
proposé à des organisateurs extérieurs, il faudra un petit contrat de
sous-traitance (article 28) — un modèle d'une page suffit à notre échelle,
à faire relire une fois. Pour les courses SENZU, organisateur et opérateur
sont la même entité, question réglée.

## L'information des participants

La base la plus solide : informer au moment de l'inscription. Une clause dans
le règlement de course que chaque participant accepte, par exemple :

> Des photographies sont prises pendant l'épreuve et publiées dans une
> galerie en ligne où elles sont retrouvables par numéro de dossard, afin que
> chaque participant puisse récupérer ses photos. Aucun dispositif de
> reconnaissance faciale n'est utilisé et aucun nom n'est publié. Vous pouvez
> demander le retrait de toute photo vous concernant à [adresse email de
> l'organisateur] ; il sera effectué sous 7 jours. Les galeries sont
> retirées du web au plus tard [12 mois] après l'épreuve.

Les deux valeurs entre crochets sont à fixer par l'organisateur. Le pied de
page de la galerie rappelle déjà le contact pour demander un retrait.

## Les demandes de retrait

C'est la demande qu'on recevra vraiment. La procédure outillée :

```bash
python scripts/retirer_photo.py events/mon-evenement/event.yaml IMG_1234.jpg
```

La photo disparaît du bucket, du journal et de l'index en une commande.
Retrouver *quelle* photo est en cause est simple si le demandeur donne son
dossard (la galerie fait la recherche) ; sinon lui demander le lien de la
photo (bouton de téléchargement → le nom du fichier est dans l'URL).
Répondre sous une semaine est largement dans les temps réglementaires (un
mois) et raisonnable vis-à-vis des gens.

Cas voisin : « ce n'est pas moi sur cette photo » (dossard mal attribué) —
ce n'est pas un retrait mais une correction, voir la question fréquente du
GUIDE.md.

## La fin de vie des galeries

Le RGPD demande une durée de conservation définie et annoncée — pas de
galerie qui traîne en ligne pour toujours. Quand la durée convenue est
atteinte :

```bash
python scripts/purger_evenement.py events/mon-evenement/event.yaml
```

Le bucket entier disparaît. 12 mois après l'épreuve est une durée
raisonnable et utile (les participants reviennent chercher leurs photos
longtemps après) ; c'est un paramètre commercial autant que réglementaire,
à écrire dans la clause d'information ci-dessus.

## Reste à faire

Tenir une ligne de registre des traitements (obligation même pour une petite
asso, c'est un tableau d'une ligne : finalité, données, durée, sous-traitants
— la CNIL fournit un modèle). Et le jour où l'outil est vendu à un
organisateur extérieur, rédiger le contrat de sous-traitance évoqué plus
haut.
