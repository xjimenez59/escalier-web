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


def _cross3(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _norm3(a):
    l = (a[0]**2+a[1]**2+a[2]**2)**0.5 or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)


def _dot3(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def _polygon_2d(points, normal):
    """Projette des points 3D coplanaires sur un repère 2D local tangent à `normal` (base
    orthonormée), pour pouvoir les découper en triangles indépendamment de leur orientation dans
    l'espace."""
    aux = (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    ux = _norm3(_cross3(aux, normal))
    uy = _cross3(normal, ux)
    return [(_dot3(p, ux), _dot3(p, uy)) for p in points]


def _cross2(o, a, b):
    return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])


def _dans_triangle(p, a, b, c):
    d1, d2, d3 = _cross2(a, b, p), _cross2(b, c, p), _cross2(c, a, p)
    neg, pos = (d1 < 0 or d2 < 0 or d3 < 0), (d1 > 0 or d2 > 0 or d3 > 0)
    return not (neg and pos)


def _decoupe_oreilles(pts2d):
    """Indices (i, j, k) d'une triangulation par découpe d'oreilles d'un polygone simple (sans
    auto-intersection), convexe ou non. Nécessaire ici : les faces capuchon des crémaillères
    (zigzag) et des marches (en L) ne sont garanties convexes par `prism_faces` que si elles ont
    été subdivisées (voir `_grid_pieces` dans app/modele3d.py) - ce qui n'est pas le cas du
    modèle exact `solide()` (pas de subdivision, voir CLAUDE.md), donc une simple triangulation
    en éventail y produirait des triangles parasites hors du contour réel."""
    n = len(pts2d)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]
    aire = sum(pts2d[i][0]*pts2d[(i+1) % n][1] - pts2d[(i+1) % n][0]*pts2d[i][1] for i in range(n))
    idx = list(range(n)) if aire >= 0 else list(range(n))[::-1]
    tris = []
    garde = 0
    while len(idx) > 3 and garde < n*n + 10:
        garde += 1
        m = len(idx)
        decoupe = False
        for i in range(m):
            ip, ic, isv = idx[i-1], idx[i], idx[(i+1) % m]
            a, b, c = pts2d[ip], pts2d[ic], pts2d[isv]
            if _cross2(a, b, c) <= 1e-9:
                continue  # sommet réflexe ou dégénéré : pas une oreille
            if any(_dans_triangle(pts2d[idx[j]], a, b, c) for j in range(m) if idx[j] not in (ip, ic, isv)):
                continue
            tris.append((ip, ic, isv))
            idx.pop(i)
            decoupe = True
            break
        if not decoupe:
            break  # polygone dégénéré : on s'arrête proprement plutôt que boucler
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def _triangles(points, normal):
    """Triangles (p0, p1, p2) d'une face plane (polygone simple, convexe ou non)."""
    if len(points) == 3:
        return [tuple(points)]
    return [(points[i], points[j], points[k]) for i, j, k in _decoupe_oreilles(_polygon_2d(points, normal))]


def scene_to_threejs(E):
    """Tampon non indexé {"positions": [...], "colors": [...]} (triplets x,y,z / r,g,b à plat),
    prêt pour une THREE.BufferGeometry. Pas de normales : chaque sommet n'appartenant qu'à un
    seul triangle (tampon non indexé), geometry.computeVertexNormals() calculée côté client
    retrouve exactement une normale par triangle (aucun sommet partagé entre faces) - un ombrage
    plat correct, sans calcul ni payload de normales côté serveur."""
    positions = []
    colors = []
    for points, normal, hexcol, _edge in solide(E):
        r, g, b = _hex_rgb(hexcol)
        for tri in _triangles(points, normal):
            for p in tri:
                positions.extend(p)
                colors.extend((r, g, b))
    return {"positions": positions, "colors": colors}


def scene_to_obj(E, nom="escalier"):
    """(texte_obj, texte_mtl) : modèle exact de l'escalier (voir modele3d.solide), un matériau
    par couleur distincte. Faces triangulées (`_triangles`) plutôt qu'émises en polygones natifs :
    certaines faces capuchon ne sont pas convexes (crémaillères en zigzag, marches en L), et tous
    les logiciels important l'OBJ ne les décomposeraient pas forcément correctement eux-mêmes.
    Pas de normales (`vn`) : le sens de parcours des faces est déjà extérieur (garanti par
    prism_faces), ce qui donne des normales sortantes correctes par défaut à l'import. Coordonnées
    en centimètres, Z vers le haut (repère monde interne du projet, voir CLAUDE.md) - pas de
    conversion d'axe ; à régler à l'import si le logiciel cible l'exige."""
    materiaux = {}   # hex -> nom de matière
    sommets = []     # liste globale de points (non dédupliquée)
    lignes_f = []    # (nom_matiere, (i, j, k) 1-based)
    for points, normal, hexcol, _edge in solide(E):
        if hexcol not in materiaux:
            materiaux[hexcol] = f"materiau_{hexcol.lstrip('#')}"
        for tri in _triangles(points, normal):
            debut = len(sommets) + 1
            sommets.extend(tri)
            lignes_f.append((materiaux[hexcol], (debut, debut+1, debut+2)))

    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
    obj = [
        f"# Escalier quart tournant - modèle 3D exact ({horodatage})",
        "# Coordonnées en centimètres, Z vers le haut.",
        f"mtllib {nom}.mtl",
    ]
    for x, y, z in sommets:
        obj.append(f"v {x:.3f} {y:.3f} {z:.3f}")
    matiere_courante = None
    for nom_matiere, (i, j, k) in lignes_f:
        if nom_matiere != matiere_courante:
            obj.append(f"usemtl {nom_matiere}")
            matiere_courante = nom_matiere
        obj.append(f"f {i} {j} {k}")
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
