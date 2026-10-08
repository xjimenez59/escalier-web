# Escalier quart tournant : générateur de plans

Application web (Flask) qui calcule un escalier quart tournant balancé, marches posées sur crémaillères,
et produit un PDF de fabrication : page de résultats, plan, vue en perspective, fiche coordonnée de chaque
marche, développé et tracé dans le brut de chaque crémaillère, assemblages, liste de débit.

Projet personnel d'un particulier qui construit l'escalier de son atelier. **On échange en français**
(code, commentaires, messages de commit, interface et PDF en français). Toutes les cotes sont en centimètres.

## Organisation du code

- `app/geometrie.py` : le calcul, sans dépendance (bibliothèque standard seule).
  - `Escalier(P)` calcule tout à partir d'un `argparse.Namespace` (`parse_args([])` donne les valeurs par défaut).
  - Les erreurs de paramètres lèvent `EscalierErreur` (message destiné à l'utilisateur) ; les incohérences
    non bloquantes vont dans `E.alertes`.
- `app/pdf.py` : mise en page du PDF (reportlab), `build_pdf(E, chemin_ou_flux)`.
- `app/modele3d.py` : modèle 3D de l'escalier, sans dépendance à reportlab.
  - `pieces3d(E, seg, eps_z)` : faces réelles (marches, crémaillères, contremarches, poteau, bastaing),
    couleurs en chaîne hexa. `seg` (subdivision) et `eps_z` (écart aux contremarches) ne servent qu'au rendu
    PDF peintre (sans z-buffer) — défauts = modèle exact, sans ces compromis.
  - `scene(E)` : `pieces3d(seg=12.0, eps_z=1.0)` + plancher/chevêtre, couleurs reportlab — pour le PDF
    uniquement (`app/rendu3d.py`).
  - `solide(E)` : `pieces3d()` par défaut (exact, sans plancher/chevêtre) — pour la visionneuse 3D et
    l'export (`app/export3d.py`). Ne jamais ajouter de compromis propre au rendu PDF à `solide`/`pieces3d`.
- `app/rendu3d.py` : rendu de la vue 3D dans le PDF (projection + algorithme du peintre), à partir de `scene(E)`.
- `app/export3d.py` : sérialise `modele3d.solide(E)` en JSON (visionneuse Three.js, route `/3d`) et en
  Wavefront OBJ+MTL (export `.zip` pour SweetHome3D/SketchUp, route `/export3d.zip`). Aucune dépendance.
- `app/escalier.py` : point d'entrée en ligne de commande (`python -m app.escalier --help`) ; réexporte
  `Escalier`, `parse_args`, `EscalierErreur`, `build_pdf` pour `app/web.py` et les tests.
- `app/web.py` : formulaire (liste `GROUPES` : nom, libellé, type, bornes, pas, aide) ; route `POST /` qui
  renvoie le PDF, `GET /3d` (visionneuse) et `GET /export3d.zip` (export) qui acceptent les mêmes paramètres
  en query string (`lire_formulaire` fonctionne avec `request.form` ou `request.args` indifféremment).
  Tout nouveau paramètre du moteur doit être ajouté à `parse_args` **et** à `GROUPES`.
- `app/templates/visionneuse.html` : page de la visionneuse 3D interactive (Three.js vendorisé dans
  `app/static/vendor/three/`, aucune dépendance CDN — cohérent avec un déploiement sans accès internet garanti).
- `tests/` : pytest. Les tests doivent passer avant tout commit (`python -m pytest -q`).

## Repères géométriques (à respecter, source d'erreurs passées)

- Repère plan interne, toujours calculé pour un escalier tournant **à droite** : angle extérieur des murs en (0,0),
  mur de départ = droite x=0, volée de départ montant vers les y décroissants depuis y = long_depart ;
  mur d'arrivée = droite y=0, volée d'arrivée montant vers les x croissants jusqu'au chevêtre en x = long_arrivee.
  Ce repère a l'axe y vers le bas sur le papier (vue de dessus correcte quand on dessine y vers le bas).
  Pour un escalier **à gauche**, tout est calculé pareil puis dessiné en miroir.
- Monde 3D : (x, -y, z), avec en plus x -> -x pour un escalier à gauche.
- Développés des crémaillères : vus **côté marches** (face qui reçoit les marches). Pour un escalier à droite,
  les crémaillères mur ne sont pas inversées (départ à gauche) et les crémaillères intérieures le sont
  (`Escalier.view_mirror`). L'utilisateur a relevé une inversion par le passé : vérifier le sens à chaque changement.
- Fiches de marches : vue de dessus, nez en bas, origine à l'extrémité gauche du nez, X le long du nez, Y vers l'arrière.
- Tracé des crémaillères : origine à l'extrémité gauche de la face inférieure du brut, X le long de cette face.

## Choix de construction validés avec l'utilisateur

Résumé rapide ci-dessous ; le détail complet (raisonnement, dimensions, **options envisagées puis
écartées et pourquoi**) est dans `CONCEPTION.md` — à tenir à jour en même temps que ce qui suit.

- Marches de 80 cm utiles (du jeu au mur au bord côté jour), ligne de foulée au milieu ; 15 hauteurs pour 290 cm ;
  balancement marches 3 à 11 (méthode sinus) ; recouvrement 3 cm ; marches 4 cm.
- Quatre **crémaillères** (pas de limons à logements : montage impossible, abandonné). Coupes **toutes d'équerre**
  (les coupes obliques du tournant dépassaient 45° de lame) : chaque coupe suit la plus basse des deux faces.
- Rive basse **droite** par défaut (face inférieure du brut, pieds coupés au sol) ; gorge 12 cm côté jour, 8 cm côté mur.
- Crémaillères mur vissées dans les montants de l'ossature bois (OSB 10 mm : ne rien fixer dans l'OSB seul).
  Angle mur : la crémaillère de départ va jusqu'au mur d'arrivée, celle d'arrivée bute contre sa face
  (une feuillure a été écartée : elle empêchait le montage). Bastaing de soutien dans l'angle.
- Poteau d'angle **côté vide**, hauteur automatique = dessus des crémaillères intérieures (pas de garde-corps
  prévu pour l'instant) ; marches entaillées seulement si leur dessous est plus bas que le haut du poteau.
- Haut de la crémaillère intérieure : elle **monte jusqu'au plancher** sur 10 cm et se fixe sur la face du chevêtre
  par 2 tiges M10 (la marche du haut est entaillée). L'ancien « talon » sous le chevêtre était suspendu : à éviter.
- Bois prévu : bastaings de pin collés chant sur chant pour les crémaillères.
- **Contremarches** (optionnelles, `--ep-contremarche`) : engagées dans une rainure sous la marche du dessus,
  vissées par en dessous sur une languette ajoutée à l'arrière de la marche du dessous. Le panneau est en retrait
  du pli de chaque crémaillère (épaisseur + marge), jamais calé dessus — une pose en butée bord à bord y serait à
  tolérance nulle (`CONCEPTION.md` explique pourquoi, avec les autres options écartées : feuillure dans la
  crémaillère, biseau des chants, tasseau rapporté en principe général, vissage en façade).

## Méthode de travail attendue

1. Discuter le besoin avec l'utilisateur, proposer, puis coder.
2. Vérifier : `python -m pytest -q`, et générer un PDF de contrôle (`python -m app.escalier -o /tmp/test.pdf`)
   pour les changements de géométrie ou de rendu ; les regarder si possible.
3. Commit en français, petit et ciblé, sur `main`, puis `git push`. La CI publie alors l'image `edge` (non déployée).
4. **Mise en production** uniquement avec l'accord explicite de l'utilisateur : incrémenter la version
   (`vMAJEUR.MINEUR.CORRECTIF`), `git tag vX.Y.Z && git push origin vX.Y.Z`. La CI publie l'image `latest`,
   que le NAS récupère tout seul en moins de 10 minutes (script `deploy/mise-a-jour.sh` en tâche planifiée).
5. Vérifier ensuite le déploiement (la page affiche la version en pied de page ; `/sante` renvoie la version).

Ne jamais mettre de secrets dans le dépôt. Pas d'accès direct au NAS depuis cette session.
