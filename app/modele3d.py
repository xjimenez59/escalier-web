#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modèle 3D de l'escalier : liste de faces (points, normale, couleur) à partir d'un
Escalier déjà calculé. Pas de dépendance à reportlab : ce module pourra aussi alimenter,
plus tard, un export pour une visionneuse 3D interactive (Three.js) côté navigateur."""
import math

from reportlab.lib import colors

from .geometrie import area, clean, hp_clip

# ----------------------------------------------------------------------------
# Vue 3D (perspective, peintre)
# ----------------------------------------------------------------------------
def v_add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def v_sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def v_mul(a, k): return (a[0]*k, a[1]*k, a[2]*k)
def v_dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def v_cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def v_norm(a):
    L = math.sqrt(v_dot(a, a)) or 1.0
    return (a[0]/L, a[1]/L, a[2]/L)

def _edge_flags(pts, a0, a1, b0, b1, li, ri, bi, ti, eps=1e-4):
    """Un booléen par bord de `pts` : vrai si ce bord est à tracer, c'est-à-dire s'il ne
    coïncide pas avec une des coupes internes (a0/a1/b0/b1, selon li/ri/bi/ti) d'une cellule
    de la grille de subdivision — donc si c'est une vraie arête du polygone d'origine."""
    m_ = len(pts); flags = []
    for k in range(m_):
        p, q = pts[k], pts[(k+1) % m_]
        internal = (li and abs(p[0]-a0) < eps and abs(q[0]-a0) < eps) or \
                   (ri and abs(p[0]-a1) < eps and abs(q[0]-a1) < eps) or \
                   (bi and abs(p[1]-b0) < eps and abs(q[1]-b0) < eps) or \
                   (ti and abs(p[1]-b1) < eps and abs(q[1]-b1) < eps)
        flags.append(not internal)
    return flags

def _grid_pieces(poly2d, seg):
    """Subdivise poly2d (peut être non convexe : marche en L, crémaillère en zigzag) en
    morceaux d'au plus seg x seg, par découpes successives (hp_clip gère les contours non
    convexes, un contour simple reste valide après une coupe par demi-plan). Renvoie une
    liste de (points, bords_à_tracer, bords_à_tracer_si_parcours_inversé) : un bord est à
    tracer s'il correspond à une vraie arête du polygone d'origine, pas à une coupure de
    subdivision (les deux orientations sont fournies, pour la face capuchon du dessous, dont
    les points sont pris en sens inverse pour que sa normale pointe vers l'extérieur)."""
    as_ = [p[0] for p in poly2d]; bs_ = [p[1] for p in poly2d]
    amin, amax, bmin, bmax = min(as_), max(as_), min(bs_), max(bs_)
    if amax <= amin or bmax <= bmin: return [(poly2d, [True]*len(poly2d), [True]*len(poly2d))]
    na = max(1, math.ceil((amax-amin)/seg)); nb = max(1, math.ceil((bmax-bmin)/seg))
    out = []
    for i in range(na):
        a0, a1 = amin+i*seg, amin+(i+1)*seg
        li, ri = i > 0, i < na-1
        for j in range(nb):
            b0, b1 = bmin+j*seg, bmin+(j+1)*seg
            bi, ti = j > 0, j < nb-1
            cp = hp_clip(poly2d, (a0, 0), (1, 0)); cp = hp_clip(cp, (a1, 0), (-1, 0))
            cp = hp_clip(cp, (0, b0), (0, 1)); cp = hp_clip(cp, (0, b1), (0, -1))
            cp = clean(cp)
            if len(cp) < 3 or abs(area(cp)) < 1e-4: continue
            fwd = _edge_flags(cp, a0, a1, b0, b1, li, ri, bi, ti)
            rev = _edge_flags(cp[::-1], a0, a1, b0, b1, li, ri, bi, ti)
            out.append((cp, fwd, rev))
    return out

def prism_faces(poly2d, O, A, B, Tv, color, edge=True, seg=12.0):
    """Prisme : polygone (a,b) dans le plan O + a*A + b*B, extrudé de Tv. Renvoie des faces
    (pts, normale extérieure, couleur, traits à tracer).

    Toutes les faces (capuchons compris, subdivisés par `_grid_pieces`, et faces latérales,
    subdivisées le long de chaque arête) sont découpées en morceaux d'au plus `seg` cm :
    l'algorithme du peintre (render_3d) trie des faces entières par la distance de leur
    centre à la caméra, et une face trop grande ou allongée (ex. une longue crémaillère, vue
    de face, ou un panneau de contremarche oblique dans le tournant) a un centre qui ne
    représente pas bien sa profondeur sur toute son étendue, d'où des chevauchements mal
    ordonnés avec d'autres faces. Pour ne pas faire apparaître de lignes de subdivision
    parasites, seuls les bords correspondant à une vraie arête du polygone d'origine (et non
    à une coupure de subdivision) sont marqués à tracer ; `edge` par face est alors un
    n-uplet de booléens (un par bord) plutôt qu'un simple booléen."""
    if area(poly2d) < 0: poly2d = poly2d[::-1]
    tn = v_norm(Tv); faces = []
    for pts2d, fwd, rev in _grid_pieces(poly2d, seg):
        if not edge: fwd = rev = [False]*len(fwd)
        P0p = [v_add(O, v_add(v_mul(A, a), v_mul(B, b))) for a, b in pts2d]
        P1p = [v_add(p, Tv) for p in P0p]
        faces.append((P0p[::-1], v_mul(tn, -1), color, tuple(rev)))
        faces.append((P1p, tn, color, tuple(fwd)))
    P0 = [v_add(O, v_add(v_mul(A, a), v_mul(B, b))) for a, b in poly2d]
    P1 = [v_add(p, Tv) for p in P0]
    n_ = len(poly2d)
    for i in range(n_):
        (a0, b0), (a1, b1) = poly2d[i], poly2d[(i+1) % n_]
        dx, dy = a1-a0, b1-b0
        nrm = v_norm(v_sub(v_mul(A, dy), v_mul(B, dx)))
        p0i, p0j, p1i, p1j = P0[i], P0[(i+1) % n_], P1[i], P1[(i+1) % n_]
        length = math.dist(p0i, p0j)
        nseg = max(1, math.ceil(length/seg))
        lerp = lambda p, q, t: (p[0]+(q[0]-p[0])*t, p[1]+(q[1]-p[1])*t, p[2]+(q[2]-p[2])*t)
        for s in range(nseg):
            t0, t1 = s/nseg, (s+1)/nseg
            q0a, q0b = lerp(p0i, p0j, t0), lerp(p0i, p0j, t1)
            q1a, q1b = lerp(p1i, p1j, t0), lerp(p1i, p1j, t1)
            edges = (True, s == nseg-1, True, s == 0) if edge else (False, False, False, False)
            faces.append(([q0a, q0b, q1b, q1a], nrm, color, edges))
    return faces

def pieces3d(E, seg=1e6, eps_z=0.0):
    """Faces 3D réelles de l'escalier (marches, crémaillères, contremarches, poteau, bastaing de
    soutien) : liste de (points, normale, couleur_hex, bords_à_tracer). Couleur en chaîne hexa
    (`"#rrggbb"`) : pas de dépendance à reportlab ici, c'est `scene()` qui la convertit pour le
    rendu PDF. Ne contient pas le plancher d'arrivée/chevêtre (ajouté séparément par `scene()`,
    voir plus bas) : ce n'est qu'un repère visuel de mise en situation pour le rendu PDF, avec des
    marges arbitraires, pas une pièce réelle de l'escalier.

    `seg` : subdivision max (cm) des faces — n'a d'intérêt que pour fiabiliser le tri par
    profondeur de l'algorithme du peintre du rendu PDF (app/rendu3d.py), sans z-buffer ; sans
    objet pour un modèle exact (visionneuse 3D interactive, export) — laisser très grand, par
    défaut (aucune subdivision).
    `eps_z` : écart (cm) retranché en haut et en bas de chaque panneau de contremarche —
    sert uniquement à éviter un scintillement dans ce même rendu peintre (faces coïncidentes
    avec les marches voisines, voir `scene()`) ; laisser à 0, par défaut, pour un modèle exact où
    le panneau touche vraiment la marche du dessus et celle du dessous."""
    sgx = -1 if E.left else 1
    W = lambda x, y, z: (sgx*x, -y, z)          # plan -> monde (x est, y nord, z haut)
    Wv = lambda x, y, z: (sgx*x, -y, z)         # vecteurs
    faces = []
    TREAD = "#d9b98a"; CR = "#b98a55"; POT = "#8a5a2b"; RISER = "#4a4d52"
    # marches
    for m, poly in E.TREADS.items():
        z0 = m*E.h - E.EP
        pts = [W(x, y, 0)[:2] for x, y in poly]
        faces += prism_faces(pts, (0, 0, z0), (1, 0, 0), (0, 1, 0), (0, 0, E.EP), TREAD, seg=seg)
    # crémaillères (plans verticaux)
    Y0, WL, TH = E.Y0, E.WL, E.TH
    defs = {
        'mur_dep': (W(0, Y0, 0), Wv(0, -1, 0), Wv(1, 0, 0)),
        'mur_arr': (W(WL-(Y0-WL), 0, 0), Wv(1, 0, 0), Wv(0, 1, 0)),
        'int_bas': (W(E.INx, Y0, 0), Wv(0, -1, 0), Wv(1, 0, 0)),
        'int_haut': (W(E.INx-(Y0-E.INy), E.INy, 0), Wv(1, 0, 0), Wv(0, 1, 0)),
    }
    for k, (O, A, tdir) in defs.items():
        faces += prism_faces(E.OUT[k], O, A, (0, 0, 1), v_mul(tdir, TH), CR, seg=seg)
    # contremarches (panneaux verticaux pleins, partie visible seulement)
    for r in E.RISERS.values():
        a, b = r['a'], r['b']; Lr = math.dist(a, b)
        if Lr <= 0: continue
        z_bas, z_haut = r['z_bas']+eps_z, r['z_haut']-eps_z
        if z_haut <= z_bas: continue
        uxr = ((b[0]-a[0])/Lr, (b[1]-a[1])/Lr); nrmr = (-uxr[1], uxr[0])
        rect = [(0, 0), (Lr, 0), (Lr, z_haut-z_bas), (0, z_haut-z_bas)]
        faces += prism_faces(rect, W(a[0], a[1], z_bas), Wv(uxr[0], uxr[1], 0), (0, 0, 1),
                              v_mul(Wv(nrmr[0], nrmr[1], 0), E.P.ep_contremarche), RISER, seg=seg)
    # poteau et bastaing de soutien. Le poteau est un prisme simple (carré, pas de contour non
    # convexe) et une de ses faces touche exactement celle de la crémaillère intérieure
    # (boulonnées ensemble) : jamais de subdivision (seg très large, quel que soit `seg` demandé)
    # pour éviter tout conflit de profondeur avec elle dans le rendu peintre du PDF, qui ferait
    # disparaître par endroits les faces du poteau.
    if E.P.poteau > 0:
        sq = [W(E.PO0x, E.PO0y, 0)[:2], W(E.PO1x, E.PO0y, 0)[:2], W(E.PO1x, E.PO1y, 0)[:2], W(E.PO0x, E.PO1y, 0)[:2]]
        faces += prism_faces(sq, (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, E.POT_H), POT, seg=max(seg, 1000.0))
    faces += prism_faces(E.SUP_POLY, W(0, 0, 0), Wv(1, 0, 0), (0, 0, 1), v_mul(Wv(0, 1, 0), WL), CR, seg=seg)
    return faces

def solide(E):
    """Modèle exact de l'escalier : les mêmes pièces que `scene()` (voir `pieces3d`), mais sans
    aucun des compromis propres au rendu peintre du PDF (pas de subdivision, panneaux de
    contremarche à leur vraie hauteur, pas de plancher/chevêtre - juste l'escalier lui-même).
    Alimente la visionneuse 3D interactive et l'export de fichiers 3D (voir app/export3d.py)."""
    return pieces3d(E)

def scene(E):
    faces = [(pts, nrm, colors.HexColor(col), edge) for pts, nrm, col, edge in pieces3d(E, seg=12.0, eps_z=1.0)]
    # plancher d'arrivée autour de la trémie (translucide) et chevêtre : simple repère visuel en
    # perspective pour le PDF (marges arbitraires), pas une pièce réelle de l'escalier - absent
    # du modèle exact `solide()`.
    sgx = -1 if E.left else 1
    W = lambda x, y, z: (sgx*x, -y, z)
    SL = colors.HexColor("#9aa4ae"); zc = E.CHEV; XE = E.XE
    tl = E.P.tremie_largeur
    for (x0, x1, y0, y1) in [(XE, XE+90, 0, tl+70), (0, XE, tl, tl+70)]:
        sq = [W(x0, y0, 0)[:2], W(x1, y0, 0)[:2], W(x1, y1, 0)[:2], W(x0, y1, 0)[:2]]
        for f in prism_faces(sq, (0, 0, zc), (1, 0, 0), (0, 1, 0), (0, 0, E.P.plancher), SL, edge=True):
            faces.append(f + ("slab",))
    return faces
