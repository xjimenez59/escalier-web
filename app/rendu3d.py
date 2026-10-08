#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rendu de la vue 3D en perspective dans le PDF : projection et algorithme du peintre
à partir des faces produites par app/modele3d.py."""
import math

from reportlab.lib import colors
from reportlab.platypus import Flowable

from .modele3d import v_add, v_sub, v_mul, v_dot, v_cross, v_norm, scene

def render_3d(c, box, E, cam, target, eye_note=True):
    """Dessine la scène dans box=(x, y, w, h) (points PDF)."""
    sgx = -1 if E.left else 1
    C = (sgx*cam[0], -cam[1], cam[2]); L = (sgx*target[0], -target[1], target[2])
    f = v_norm(v_sub(L, C)); r = v_norm(v_cross(f, (0, 0, 1))); u = v_cross(r, f)
    def proj(p):
        d = v_sub(p, C); zc = v_dot(d, f)
        return (v_dot(d, r)/zc, v_dot(d, u)/zc, zc)
    faces = scene(E)
    # sol et murs (fond)
    Y0, XE = E.Y0, E.XE
    W = lambda x, y, z: (sgx*x, -y, z)
    floor = [W(-20, -20, 0), W(XE+120, -20, 0), W(XE+120, Y0+220, 0), W(-20, Y0+220, 0)]
    wall1 = [W(0, 0, 0), W(0, Y0+220, 0), W(0, Y0+220, E.P.hauteur), W(0, 0, E.P.hauteur)]
    wall2 = [W(0, 0, 0), W(XE+120, 0, 0), W(XE+120, 0, E.P.hauteur), W(0, 0, E.P.hauteur)]
    bg = [(floor, colors.HexColor("#e6e2da")), (wall1, colors.HexColor("#f1efea")), (wall2, colors.HexColor("#ebe8e1"))]
    light = v_norm((0.35, -0.55, 0.9))
    items = []
    for fc in faces:
        pts, nrm, col, edge = fc[:4]; slab = len(fc) > 4
        cen = v_mul(pts[0], 0); 
        for p in pts: cen = v_add(cen, p)
        cen = v_mul(cen, 1/len(pts))
        if v_dot(nrm, v_sub(C, cen)) <= 0: continue
        pp = [proj(p) for p in pts]
        if any(q[2] <= 1 for q in pp): continue
        sh = 0.62 + 0.38*max(0.0, v_dot(nrm, light))
        items.append((math.dist(cen, C), pp, col, sh, edge, slab))
    items.sort(key=lambda t: -t[0])
    allp = [q for it in items if not it[5] for q in it[1]]
    xs = [q[0] for q in allp]; ys = [q[1] for q in allp]
    x0, y0, w, h = box
    sc = min(w/(max(xs)-min(xs)), h/(max(ys)-min(ys)))*0.92
    cx = (max(xs)+min(xs))/2; cy = (max(ys)+min(ys))/2
    S = lambda q: (x0 + w/2 + (q[0]-cx)*sc, y0 + h/2 + (q[1]-cy)*sc)
    c.saveState()
    pth = c.beginPath(); pth.rect(x0, y0, w, h); c.clipPath(pth, stroke=0, fill=0)
    for poly, col in bg:
        pp = [proj(p) for p in poly]
        if any(q[2] <= 1 for q in pp): continue
        p = c.beginPath(); X, Y = S(pp[0]); p.moveTo(X, Y)
        for q in pp[1:]: X, Y = S(q); p.lineTo(X, Y)
        p.close(); c.setFillColor(col); c.setStrokeColor(colors.HexColor("#c9c4b8")); c.setLineWidth(0.4)
        c.drawPath(p, fill=1, stroke=1)
    for _, pp, col, sh, edge, slab in items:
        p = c.beginPath(); X, Y = S(pp[0]); p.moveTo(X, Y)
        for q in pp[1:]: X, Y = S(q); p.lineTo(X, Y)
        p.close()
        cc = colors.Color(col.red*sh, col.green*sh, col.blue*sh)
        c.setFillColor(cc)
        if slab: c.setFillAlpha(0.35)
        else: c.setFillAlpha(1)
        if isinstance(edge, (tuple, list)):
            # face issue d'une subdivision (prism_faces) : un booléen par bord (un par sommet,
            # dans l'ordre). Un morceau de subdivision rempli seul, bord à bord avec son voisin,
            # peut laisser un très léger liseré (anticrénelage indépendant de chaque polygone) ;
            # on scelle donc d'abord TOUS les bords avec un trait de la couleur du remplissage
            # (sans toucher aux coordonnées, pour ne pas déformer une arête réelle oblique), puis
            # on trace par-dessus, en foncé, seulement les bords qui sont de vraies arêtes.
            c.setStrokeColor(cc); c.setLineWidth(0.15); c.setStrokeAlpha(0.35 if slab else 1)
            c.drawPath(p, fill=1, stroke=1)
            c.setStrokeColor(colors.HexColor("#3a2f25")); c.setLineWidth(0.35); c.setStrokeAlpha(1)
            n_ = len(pp)
            for i, flag in enumerate(edge):
                if not flag: continue
                X0, Y0_ = S(pp[i]); X1, Y1_ = S(pp[(i+1) % n_])
                c.line(X0, Y0_, X1, Y1_)
        else:
            c.setStrokeColor(colors.HexColor("#3a2f25")); c.setLineWidth(0.35)
            c.drawPath(p, fill=1, stroke=1 if edge else 0)
    c.restoreState()

class View3D(Flowable):
    def __init__(self, E, cam, target, width, height):
        super().__init__(); self.E = E; self.cam = cam; self.target = target; self.width = width; self.height = height
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        render_3d(self.canv, (0, 0, self.width, self.height), self.E, self.cam, self.target)
