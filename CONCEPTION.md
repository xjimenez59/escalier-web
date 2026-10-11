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

Le bord arrière d'une marche balancée ne peut pas être une simple ligne droite à profondeur
constante : il doit épouser le profil réel en zigzag des crémaillères (palier puis remontée vers
la marche suivante), sans quoi un triangle de bois manque près de chaque crémaillère. La
définition ci-dessous a été établie avec l'utilisateur en octobre 2026 ; elle remplace une
version précédente (point de départ mal défini, variantes « double contact » décrites au cas par
cas) qui avait montré ses limites. Repère : voir `CLAUDE.md` (plan interne, toujours calculé
comme un tournant à droite ; un escalier à gauche est dessiné en miroir).

### Vocabulaire

- **Arête extérieure** d'une crémaillère : le bord de sa face arrière (côté opposé aux marches —
  `JXx`/`JXy` pour les crémaillères intérieures, le mur pour les crémaillères mur).
- **Arête intérieure** : le bord de sa face côté marches (`INx`/`INy`, `WL`).
- **Chant** : le bout d'une crémaillère, sur son épaisseur (TH), perpendiculaire à ses faces.
- **Arête horizontale** : arête au niveau d'un palier (on la suit). **Arête verticale** (ou
  montante) : arête d'une remontée du profil vers la marche suivante (on s'y arrête).

### Algorithme (le même pour toutes les marches)

On raisonne d'abord **sans aucun débord ni jeu** (`debord_jour`, `jeu_mur`, jeux de montage en
dur : tout à zéro), puis on les applique à la fin.

1. **Points 1 et 2** : les deux bouts de la **ligne de nez de la marche elle-même** (pour la marche
   m, `LINES[m-1]`) — 1 côté mur, 2 côté jour. Ce sont les seuls points connus d'emblée.
2. **Points 6 et 3** : depuis le point 1 (resp. 2), suivre les **arêtes horizontales extérieures**
   jusqu'à rencontrer la première **arête verticale extérieure** ; c'est le point 6 (resp. 3).
   Priorité à la prolongation directe : on continue tout droit tant que la crémaillère se
   poursuit, même un peu au-delà du coin du L, et on ne bifurque (sur un chant, ou sur l'arête
   d'une autre crémaillère) qu'à sa fin réelle. La crémaillère abordée après avoir tourné ne
   porte la marche que si elle a un palier à sa hauteur ; sinon le parcours s'arrête dès son
   début. Pas besoin de savoir à l'avance
   quelle crémaillère est « basse » ou « haute » ; quatre enchaînements sont possibles :
   1. départ > arête > arrivée — cas simple, le plus courant ;
   2. départ > arête > arête > arrivée — la crémaillère basse est collée à la face extérieure de
      la haute (cas de l'angle mur : la crémaillère d'arrivée bute contre celle de départ) ;
   3. départ > arête > chant > arrivée — la haute est collée à la face extérieure de la basse, et
      démarre par une montée ;
   4. départ > arête > chant > arête > arrivée — même chose, mais la haute démarre par un palier.
3. **Points 5 et 4** : depuis le point 6 (resp. 3), **traverser l'épaisseur** de la crémaillère
   (perpendiculairement à ses faces) jusqu'à son arête intérieure.
4. **Fermeture** : droite directe du point 4 au point 5, à la même hauteur.
5. **Débords** : on applique ensuite le débord côté jour (`debord_jour`, la marche dépasse de
   l'arête extérieure des crémaillères intérieures) et le jeu côté mur (`jeu_mur`, la marche
   s'arrête avant le mur).
   Côté jour, le nez lui-même ne dépasse pas la face avant de la crémaillère qui porte la marche
   (le début de son palier) de plus que le recouvrement, mesuré le long de cette crémaillère : sur
   un nez très oblique (marches balancées d'un escalier raide), la pointe est recoupée d'équerre,
   parallèlement à cette face (jusqu'à 12 cm de pointe en moins avec `--long-arrivee 115`, 1,6 cm
   sur la marche 5 de la configuration ci-dessous). Pas de coupe en dessous de 1 cm (`POINTE_MINI`), qui ne
   ferait qu'ajouter un trait de scie. Seulement quand il y a une vraie pointe, c'est-à-
   dire quand la ligne de coupe recoupe le nez ; un nez qui rejoint le bord jour en angle obtus
   n'est pas touché.
6. **Languette** (si contremarche) : remplace la droite 4→5, voir ci-dessous.

**Bout de crémaillère écrêté.** Quand le dernier palier d'une crémaillère de départ est
entièrement dans le carré du coin (la bande où la crémaillère d'arrivée est collée contre elle) et
que la crémaillère d'arrivée porte déjà la marche de ce palier et la précédente, ce palier est
supprimé : la crémaillère finit au niveau de la marche précédente. Il n'apportait presque rien
(2,4 cm côté jour avec `--largeur-depart 95`, 1,35 cm côté mur avec `--long-depart 125`) et
obligeait la marche précédente à le contourner. Règle appliquée au profil des crémaillères
(`ecreter_bouts`), donc aussi à leurs développés et tracés dans le PDF, et des deux côtés pour
rester une règle unique.

**Double contact.** Quand cet écrêtage ne s'applique pas et que la crémaillère de départ remonte dans la bande où celle d'arrivée est
collée contre elle (le « carré du coin »), la marche porte sur les deux : le contour suit les deux
remontées. Côté jour (la crémaillère d'arrivée est collée à la face extérieure de celle de
départ) : on tourne au coin, on suit la crémaillère d'arrivée jusqu'à sa remontée, puis on revient
le long de la jonction des deux jusqu'à la remontée de la crémaillère de départ (encoche autour
de son bout). Côté mur (la crémaillère d'arrivée bute contre la face intérieure de celle de
départ) : remontée de la crémaillère de départ, puis le long de la jonction jusqu'au mur
d'arrivée, puis la crémaillère d'arrivée jusqu'à sa remontée.

**Limite.** Si une ligne de nez longe une crémaillère de trop près (moins que le recouvrement),
cette crémaillère saute un palier : elle passe directement de la marche précédente à la suivante
et aucune règle de tracé ne peut fermer le vide entre les deux (cas `--long-depart 125`, marche 3).
Une alerte le signale ; il faut revoir le balancement ou les longueurs.

Exception : la **dernière marche** n'a pas d'arête montante au-dessus d'elle (pas de marche
suivante) ; son arrière est fixé par le chevêtre.

Exemple vérifié (marche 5 de la configuration « gauche, 249 / 200 / 255, trémie 300, largeurs
80 et 100 ») : côté jour, depuis le bout du nez sur l'arête extérieure d'`int_bas`, on longe
celle-ci jusqu'au coin, puis l'arête extérieure d'`int_haut` jusqu'à sa remontée (enchaînement
2 — c'est l'angle rentrant G de la fiche). Côté mur de la marche 6, même chose le long du mur de
départ puis du mur d'arrivée.

### Languette de contremarche

Entre les points 4 et 5, pour que le panneau reculé au-delà du pli garde un appui plein :

- 4a : dans le prolongement de 3→4, à 1 mm au-delà de 4 (`JEU_LIMON`) ; 4d : de même dans le
  prolongement de 6→5.
- 4a→4b parallèle à la face de la crémaillère jour, 4d→4c parallèle à celle de la crémaillère
  mur, chacun sur `ep_contremarche + RECUL_CREMAILLERE` ; les deux profondeurs sont
  **indépendantes**, et chacune n'est réduite que si le bois plein manque réellement à cet endroit
  (vérifié avec `backed`, à la hauteur de la marche) — en pratique jamais, le profil de la
  crémaillère continuant de monter au-delà du pli.
- 4b→4c : droite directe (pas forcément parallèle à 4→5).
- La languette s'appuie toujours sur la crémaillère qui porte réellement la marche suivante (la
  première rencontrée depuis le nez, côté jour comme côté mur) : la seconde crémaillère d'un
  enchaînement s'arrête au coin et ne monte jamais assez haut pour tenir le panneau.
- Le panneau de contremarche reprend exactement 4b (jour) et 4c (mur) ; les pré-perçages sont
  centrés sur son épaisseur (à `ep_contremarche / 2` de la face de la languette).

### Implémentation

`Escalier.parcours` (un côté) et `Escalier.contour_marche` (le contour complet, avec la
languette) appliquent cet algorithme ; le parcours se fait sur les arêtes réelles et les points
trouvés sont reportés sur les arêtes décalées du débord (`JRd`/`JRa`) ou du jeu (`WR`), ce qui
revient à appliquer les débords à la fin. `python -m app.escalier --trace-marche N …` affiche le
détail du parcours d'une marche (arêtes suivies, coins, points 1 à 6). Un test vérifie qu'aucune
marche ne passe dans le bois d'une crémaillère plus haute qu'elle, sur plusieurs configurations
limites (l'ancien tracé le faisait dans 5 des 13 configurations essayées).

### Écarté

- **Tracé par demi-plans sur la géométrie globale de la marche** (première tentative) : les
  demi-plans (`x ≥ WL`, etc.) ne distinguent pas « juste à côté de la crémaillère » de « loin de
  l'autre côté » quand ils partagent l'axe du nez d'une marche voisine — marches tronquées ou
  flottantes constatées sur le PDF.
- **Ancienne définition point par point** (points 1 et 2 pris sur `LINES[m]`, la ligne de nez de
  la marche suivante, le reste venant de la découpe d'un rectangle en L ; variantes « double
  contact » 3bis/6bis décrites séparément, et repli sur une diagonale à profondeur constante dans
  les cas non prévus) : remplacée par l'algorithme unique ci-dessus.
- **Tourner au coin du L plutôt qu'à la fin réelle de la crémaillère** : une crémaillère qui
  remonte quelques dixièmes de millimètre après le coin était alors ignorée, et la marche passait
  dans son bois.
- **Chaîner deux crémaillères dès que les deux ont un palier à la hauteur de la marche** :
  déclenchait des points parasites (marches 4 de la config par défaut, 5 et 6 de la config
  ci-dessus) ; seule la rencontre d'une fin réelle de crémaillère sur le parcours justifie de
  bifurquer. Le même test filtré par `backed` pile au bord du palier n'est pas fiable non plus (le
  test point-dans-polygone est ambigu sur le bord).
- **Plafonner la profondeur de languette par l'écart entre deux paliers consécutifs** de `PAL` :
  cet écart (~0,05 cm) n'est que le pas d'échantillonnage de `steps()`, pas une limite réelle ;
  le plafond tombait à zéro sur presque toutes les marches.
- **Supprimer la languette dès qu'un enchaînement de crémaillères est détecté**, ou retomber alors
  sur l'ancienne méthode par recherche (`contremarche_offset`) : ce recul uniforme le long de la
  normale du nez laisse un triangle non couvert (panneau en retrait côté mur, juste côté jour).

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
  qu'il touche, de son épaisseur plus 0,5 cm, indépendamment de chaque côté (voir « Languette de
  contremarche » plus haut et *Écarté : panneau calé exactement sur le pli* ci-dessous). Un jeu de 0,1 cm de chaque côté par
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
