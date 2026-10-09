# Choix de conception de l'escalier

Ce document réunit les choix de construction validés pour l'escalier (dimensions, assemblage,
fixations) et les options envisagées puis écartées, avec la raison. Il complète la section
« Choix de construction validés » de `CLAUDE.md` (qui reste la référence courte utilisée en
session) en gardant la trace des alternatives écartées et du pourquoi.

## Géométrie générale

- Hauteur de sol à sol 290 cm, 15 hauteurs de marche (~19,3 cm), giron côté foulée réglé pour
  2h + g ≈ 63 (relation de Blondel).
- Balancement par la méthode sinus sur les marches 3 à 11 (réglable).
- Marches de 80 cm utiles (du jeu au mur jusqu'au bord côté jour), ligne de foulée au milieu.
- Recouvrement (nez) de 3 cm d'une marche sur la marche du dessous.
- Épaisseur des marches 4 cm, des crémaillères 4,5 cm.

## Marches

- Posées sur les crémaillères, vissées dans les zones d'appui (deux vis par appui, noyées et
  bouchonnées).
- Entaillées au droit du poteau d'angle seulement si leur dessous est plus bas que le haut du
  poteau à cet endroit (sinon elles reposent simplement dessus).
- Débord de quelques cm au-delà de la face arrière des crémaillères intérieures, côté vide
  (paramètre `debord_jour`, 2 cm par défaut).

## Bord arrière des marches (tracé exact)

Le bord arrière d'une marche balancée (celui qui n'est pas le nez) ne peut pas être une simple
ligne droite à profondeur constante : il doit épouser le profil réel en zigzag de chaque
crémaillère (palier + face de contremarche), sans quoi un triangle de bois manque près de chaque
crémaillère (la diagonale simple mord dans l'épaisseur côté mur et déborde dans le vide côté
jour). Le tracé ci-dessous, point par point, a été établi avec l'utilisateur en reprenant
précisément sa géométrie ; **non encore implémenté** (voir *Écarté* plus bas pour la tentative
d'une version précédente, erronée). Repère : voir `CLAUDE.md` (plan interne, toujours calculé
comme un tournant à droite).

Schéma de principe (non à l'échelle, angles non représentatifs — la crémaillère « mur » et la
crémaillère « vide » peuvent être à n'importe quel angle l'une de l'autre et par rapport à la
ligne de nez) :

```
                     1 ─────────────── ligne de nez ─────────────── 2
                     │        (balancement, cf. CLAUDE.md)          │
                     │                                              │
          crémaillère│                                              │crémaillère
            "mur"    │                                              │  "vide"
                     │                                              3
                     │                                              │  (a) parallèle à la
                     │                                              │      crémaillère vide
                     │                                              4  (b) ↳ arête intérieure
                     │                                             ╱       (perpendiculaire)
                     │                                            ╱
                     │                       (c) droite directe  ╱
                     │                        (même hauteur z)  ╱
                     │                                         5   arête intérieure,
                     6 ───────────────────────────────────────┘    crémaillère mur
                     │   (d) ↑ perpendiculaire, arrêtée 5 mm
                     │       avant l'arête extérieure crémaillère mur
                     │
                     └──(e) retour direct au point 1, ferme le contour
```

1. **Point de départ** : bout « mur » de la ligne de nez de la marche (`LINES[m][1]`, à 5 mm du
   mur, `x = WR` ou `y = WR`).
2. Bout « jour » de la même ligne de nez (`LINES[m][0]`, sur la droite fixe `x = JRd` ou
   `y = JRa` — c'est-à-dire `debord_jour` au-delà de l'arête arrière de la crémaillère intérieure,
   mesuré perpendiculairement à celle-ci, quel que soit l'angle de la ligne de nez).
3. **(a)** De là, la ligne suit une **parallèle à la crémaillère « vide »** (le long de son
   développé, à `x` ou `y` constant = celui du point 2) jusqu'à l'abscisse développée où le
   profil réel de cette crémaillère (son vrai tracé en zigzag, `OUT[key]`/`d_along`) remonte pour
   la contremarche suivante — pas une simple droite à profondeur fixe.
4. **(b)** Bifurque à 90° (perpendiculaire à la crémaillère, donc le long de cette face de
   contremarche prolongée) jusqu'à l'**arête intérieure** de la crémaillère vide (`INx`/`INy` —
   celle qui reçoit vraiment la marche, pas `JXx`/`JXy`, sa face arrière).
5. **(c)** Droite directe jusqu'à l'**arête intérieure de la crémaillère mur** (`WL`), au point
   situé à la **même hauteur `z`** sur le profil de cette crémaillère.
6. **(d)** Bifurque à 90°, perpendiculaire à la crémaillère mur, vers son arête extérieure (côté
   mur réel) — mais s'arrête à 5 mm avant de l'atteindre (même jeu qu'au point 1).
7. **(e)** Rejoint directement le point 1, fermant le contour.

### Variante : marche au contact des deux crémaillères « mur »

Près de l'angle, la crémaillère de départ va jusqu'au mur d'arrivée et la crémaillère d'arrivée
bute contre sa face (voir plus bas) ; une marche à cheval dessus doit contourner le coin plutôt
que fermer directement du point 6 au point 1 :

```
      5                                          5
      │                                          │
      6 ── retour direct au point 1               6 ── 6bis ── retour au point 1
 (-5mm arête extérieure                      (parallèle à la 1ère         (perpendiculaire,
  crémaillère mur)                            crémaillère -arrivée-,       vers le point 1)
                                               jusqu'à -5mm de l'arête
                                               extérieure de la 2nde
                                               -départ-)
```

### Variante : marche au contact des deux crémaillères « vide »

Symétriquement, pour le segment 2→3 (parallèle à la crémaillère vide) :

```
 2                                            2
 │                                            │
 │ parallèle à la crémaillère vide            │ parallèle à la 1ère crémaillère vide
 │ jusqu'à l'abscisse de la                   │ jusqu'au coin où les deux crémaillères vide
 │ prochaine contremarche                     │ se rejoignent (= 3bis, même coin que celui
 │                                            │ utilisé pour la hauteur du poteau)
 3                                            3bis
                                               │ parallèle à la 2nde crémaillère vide,
                                               │ jusqu'à l'abscisse de la prochaine
                                               │ contremarche
                                               3
```

### Variante : avec contremarche (languette)

Entre les points 5 et 6, insertion de la languette d'appui pour la contremarche (déjà
implémentée côté `tab_ends`/`add_tab`/`contremarche_offset` ; ce tracé documente comment elle se
raccorde au reste du contour) :

```
Sans contremarche :              Avec contremarche (zoom sur le segment 5→6) :

      4                                   4
       ╲                                   ╲
        ╲                                   ╲
         5                                   5 ── 5a  (prolonge de 1 mm, dans l'axe 4→5
         │                                        │    - le jeu `JEU_LIMON`)
         │                                        │
         │                                        │ (a) bifurque 90°, parallèle à la face
         │                                        │     intérieure de la crémaillère vide,
         6                                        │     sur ép. contremarche + 5 mm
                                                   5b
                                                   │
                                                   │ (b) bifurque 90° en sens inverse, vers
                                                   │     la crémaillère mur, arrêtée à 1 mm
                                                   │     de contact (jeu)
                                                   5c
                                                   │
                                                   │ (c) bifurque 90°, parallèle à la
                                                   │     crémaillère mur, jusqu'à l'abscisse
                                                   │     du point 6
                                                   5d ── 6   (5d, 6 et 1/6bis alignés)
```

### Écarté : tracé par demi-plans sur la géométrie globale de la marche

Première tentative : reconstruire ce contour par intersection de demi-plans (côté centroïde de
la marche, borné par la projection sur la perpendiculaire au nez) puis union des morceaux.
Fonctionnait sur des cas isolés mais s'est révélé non robuste sur le modèle réel : les demi-plans
utilisés (`x ≥ WL`, etc.) ne distinguent pas « juste à côté de la crémaillère » de « loin de
l'autre côté, sans rapport » quand ils partagent le même axe que le bord du nez d'une marche
voisine — un retrait censé ne concerner que le coin « vide » coupait alors aussi, par erreur, le
bord de nez côté opposé (`LINES[m-1]`), produisant des marches tronquées ou flottantes
(régression constatée visuellement sur le rendu PDF). Écarté au profit du tracé explicite
ci-dessus, qui suit le vrai profil de chaque crémaillère plutôt que des demi-plans plats.

## Crémaillères

- **Quatre crémaillères** (deux côté mur, deux côté vide). *Écarté : limons à logements* —
  montage par le dessus impossible une fois les marches en place ; abandonné au profit de
  crémaillères classiques.
- **Coupes toutes d'équerre.** *Écarté : coupes obliques dans le tournant* — la profondeur de
  coupe oblique nécessaire dépassait 45° de lame sur une scie portative. Chaque coupe suit donc
  la plus basse des deux faces du pli.
- Rive basse par défaut **droite** (face inférieure du brut conservée, pieds coupés au sol) ;
  variante disponible, rive **découpée** suivant la pente à gorge constante.
- Gorge minimale 12 cm côté jour, 8 cm côté mur (bois plein restant sous les entailles).
- Crémaillères mur vissées dans les montants de l'ossature bois. **Jamais de fixation dans l'OSB
  seul** (10 mm, pas assez porteur).
- Angle mur : la crémaillère de départ file jusqu'au mur d'arrivée ; celle d'arrivée bute contre
  sa face. *Écarté : feuillure à cet angle* — empêchait le montage (les deux pièces doivent
  pouvoir glisser l'une contre l'autre à la pose). Un bastaing de soutien est posé dans l'angle.
- Haut de la crémaillère intérieure : monte jusqu'au plancher sur 10 cm, fixée sur la face du
  chevêtre par 2 tiges filetées M10 (la marche du haut est entaillée en conséquence). *Écarté :
  talon suspendu sous le chevêtre comme fixation par défaut* — tenue jugée insuffisante (il
  reste possible via `--fixation-haut talon` pour un montage différent, mais ce n'est plus le
  choix par défaut).
- Bois prévu : bastaings de pin collés chant sur chant.

## Poteau d'angle

- Côté vide (pas côté marches), hauteur automatique = dessus des crémaillères intérieures à cet
  endroit. Pas de garde-corps prévu pour l'instant, donc pas de hauteur imposée par ailleurs.
- Les marches ne sont entaillées à son droit que si leur dessous passe plus bas que son sommet ;
  sinon elles reposent simplement dessus.

## Contremarches

Principe retenu, entièrement démontable/posable après la construction de l'escalier :

- **Haut** : engagé de 0,8 cm (réglable) dans une rainure creusée sous la marche du dessus,
  positionnée dans la zone cachée sous son recouvrement.
- **Bas** : posé sur une languette ajoutée à l'arrière de la marche du dessous (voir plus bas),
  et vissé par en dessous (accès par l'espace ouvert sous les crémaillères) à trois
  pré-perçages — deux proches des bords, un au centre.
- **Profondeur de pose** : le panneau est en retrait du pli de chacune des deux crémaillères
  qu'il touche, d'au moins son épaisseur plus 0,5 cm, davantage si besoin près d'un coin (voir
  *Écarté : panneau calé exactement sur le pli* ci-dessous). Un jeu de 0,1 cm de chaque côté par
  rapport aux faces des crémaillères évite tout contact chant-contre-bois.
- **Languette de marche** : pour que le panneau ainsi reculé garde un appui plein, la marche du
  dessous reçoit un débord supplémentaire vers l'arrière, uniquement dans la largeur comprise
  entre les deux crémaillères (pas sur toute la largeur — à l'aplomb des crémaillères elles-
  mêmes, la marche s'arrête comme avant, à leur affleurement). C'est la même logique que les
  débords déjà prévus côté vide et côté nez, appliquée à un troisième côté.
- **Contremarche du bas (sol → marche 1)** : pas de rainure ni de pré-perçages calculés — fixée
  avec deux tasseaux collés (un au sol, un sous la marche 1), contre lesquels elle se visse.
- **Contremarche du haut (dernière marche → chevêtre)** : pas de perçage calculé côté haut (la
  structure du plancher n'est pas connue du calcul) — à fixer contre la face du chevêtre selon
  cette structure.
- Le poteau d'angle, plus loin derrière les crémaillères intérieures que le recul des panneaux,
  n'est jamais atteint par une contremarche.

### Écarté : panneau calé exactement sur le pli de la crémaillère

Premier principe envisagé : poser le panneau avec sa face arrière exactement sur le pli vertical
de chaque crémaillère (comme une marche, poussée en butée). Écarté après vérification précise du
tracé réel des crémaillères (fonction `top_at`/`outline`) : au pli exact, le bois plein de la
crémaillère ne commence, côté marche du dessus, qu'à partir de ce pli — rien devant, sur toute
l'épaisseur du panneau, s'il y est posé directement. Une pose en butée bord à bord y serait donc
à tolérance nulle (un panneau légèrement trop en avant flotterait dans le vide, légèrement trop
en arrière mordrait dans le bois massif), inadaptée à une pose après-coup par un particulier.
Remplacé par le recul au-delà du pli, avec languette de marche en vis-à-vis (ci-dessus).

### Écarté : biseauter les chants du panneau dans le tournant

Piste intermédiaire, mise en œuvre puis abandonnée : plutôt que de reculer tout le panneau,
tailler un léger biseau à chaque bout pour qu'il affleure quand même le pli de chaque crémaillère
malgré leur angle différent dans le tournant. Fonctionnait géométriquement, mais ajoutait une
coupe non perpendiculaire à tracer et scier pour chaque panneau du tournant, pour un gain que le
recul uniforme (plus simple, plus robuste à un changement de géométrie) obtient déjà.

### Écarté : feuillure dans l'épaisseur de la crémaillère

Évoqué à deux reprises pour loger les bouts du panneau (une fois dès la réflexion initiale, une
fois en alternative au recul). Écarté les deux fois : mordrait sur la gorge déjà validée (12 cm
jour / 8 cm mur), et redemanderait un ajustement précis à l'installation.

### Écarté : tasseau ou quart-de-rond rapporté (comme principe général)

Pièce supplémentaire à fixer en position de toute façon — n'évite pas le problème, le déplace.
Conservé uniquement pour le cas particulier de la toute première contremarche (sol → marche 1),
où il n'y a pas de pli de crémaillère auquel se référer.

### Écarté : vissage direct en façade des crémaillères (sans tasseau)

Écarté pour raison esthétique : laisse un chant de panneau visible contre le bois massif du
limon.

## Pré-perçages

- Marge de 5 cm par rapport aux bords (place pour manœuvrer une visseuse sans buter contre la
  crémaillère voisine).
- Trois pré-perçages par contremarche (hors la première et la dernière, voir plus haut) : deux
  proches des bords, un au centre — la pointe des chaussures tape souvent le milieu de la
  contremarche, qui bénéficie donc de sa propre fixation plutôt que de ne compter que sur les
  deux extrémités.
