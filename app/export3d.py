#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export du modèle 3D réel de l'escalier (app/modele3d.py::solide) vers des formats consommables
en dehors du PDF : JSON pour la visionneuse Three.js (app/templates/visionneuse.html), et
Wavefront OBJ + MTL pour l'import dans SweetHome3D ou SketchUp. Aucune dépendance (ni reportlab,
ni autre) : part des couleurs déjà en chaîne hexa renvoyées par `solide()`."""
from datetime import datetime

from .modele3d import solide


def _hex_rgb(hexcol):
    """'#rrggbb' -> (r, g, b) flottants dans [0, 1]."""
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i+2], 16)/255 for i in (0, 2, 4))


def _fan_triangles(pts):
    """Triangulation en éventail d'un polygone convexe (les faces de `solide()` sont garanties
    convexes et planes, héritage de `prism_faces`)."""
    return [(pts[0], pts[i], pts[i+1]) for i in range(1, len(pts)-1)]


def scene_to_threejs(E):
    """Tampon non indexé {"positions": [...], "colors": [...]} (triplets x,y,z / r,g,b à plat),
    prêt pour une THREE.BufferGeometry. Pas de normales : chaque sommet n'appartenant qu'à un
    seul triangle (tampon non indexé), geometry.computeVertexNormals() calculée côté client
    retrouve exactement une normale par triangle (aucun sommet partagé entre faces) - un ombrage
    plat correct, sans calcul ni payload de normales côté serveur."""
    positions = []
    colors = []
    for points, _normal, hexcol, _edge in solide(E):
        r, g, b = _hex_rgb(hexcol)
        for tri in _fan_triangles(points):
            for p in tri:
                positions.extend(p)
                colors.extend((r, g, b))
    return {"positions": positions, "colors": colors}


def scene_to_obj(E, nom="escalier"):
    """(texte_obj, texte_mtl) : modèle exact de l'escalier (voir modele3d.solide), un matériau
    par couleur distincte, faces en polygones natifs (pas de triangulation : OBJ accepte les
    faces n-gones, plus simple et plus robuste qu'une triangulation maison). Pas de normales
    (`vn`) : le sens de parcours des faces est déjà extérieur (garanti par prism_faces), ce qui
    donne des normales sortantes correctes par défaut à l'import. Coordonnées en centimètres,
    Z vers le haut (repère monde interne du projet, voir CLAUDE.md) - pas de conversion d'axe ;
    à régler à l'import si le logiciel cible l'exige."""
    faces = solide(E)
    materiaux = {}  # hex -> nom de matière
    sommets = []     # liste globale de points (non dédupliquée)
    lignes_f = []     # (nom_matiere, [indices 1-based])
    for points, _normal, hexcol, _edge in faces:
        if hexcol not in materiaux:
            materiaux[hexcol] = f"materiau_{hexcol.lstrip('#')}"
        debut = len(sommets) + 1
        sommets.extend(points)
        lignes_f.append((materiaux[hexcol], list(range(debut, debut + len(points)))))

    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
    obj = [
        f"# Escalier quart tournant - modèle 3D exact ({horodatage})",
        "# Coordonnées en centimètres, Z vers le haut.",
        f"mtllib {nom}.mtl",
    ]
    for x, y, z in sommets:
        obj.append(f"v {x:.3f} {y:.3f} {z:.3f}")
    matiere_courante = None
    for nom_matiere, indices in lignes_f:
        if nom_matiere != matiere_courante:
            obj.append(f"usemtl {nom_matiere}")
            matiere_courante = nom_matiere
        obj.append("f " + " ".join(str(i) for i in indices))
    obj_text = "\n".join(obj) + "\n"

    mtl = [f"# Matériaux de l'escalier ({horodatage})"]
    for hexcol, nom_matiere in materiaux.items():
        r, g, b = _hex_rgb(hexcol)
        mtl += [
            f"newmtl {nom_matiere}",
            f"Kd {r:.3f} {g:.3f} {b:.3f}",
            f"Ka {r:.3f} {g:.3f} {b:.3f}",
            "Ks 0.000 0.000 0.000",
            "d 1.0",
            "illum 1",
            "",
        ]
    mtl_text = "\n".join(mtl)
    return obj_text, mtl_text
