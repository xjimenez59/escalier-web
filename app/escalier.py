#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Escalier quart tournant balancé, marches posées sur crémaillères.
Génère un PDF unique : plans de fabrication + tracé des crémaillères.

Dépendance : reportlab  (pip install reportlab)

Exemple :
    python3 -m app.escalier --sens droite --hauteur 290 --plancher 22 \
        --long-depart 160 --long-arrivee 260 --tremie-largeur 100 \
        --balancement 3 11 --ep-cremaillere 4.5 --ep-marche 4 -o escalier.pdf

Toutes les cotes sont en centimètres.

Repère interne (vue de dessus, escalier tournant à droite) :
  - angle extérieur des murs en (0, 0) ;
  - mur de départ = droite x = 0, la volée de départ monte vers les y décroissants
    depuis y = long_depart ;
  - mur d'arrivée = droite y = 0, la volée d'arrivée monte vers les x croissants
    jusqu'au chevêtre en x = long_arrivee.
Pour un escalier tournant à gauche, tout est calculé de la même façon puis
dessiné en miroir.
"""
import argparse, math, sys


class EscalierErreur(ValueError):
    """Paramètres incohérents : le message est destiné à l'utilisateur."""

# ----------------------------------------------------------------------------
# Paramètres
# ----------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Escalier quart tournant sur crémaillères : plans PDF")
    a = p.add_argument
    a("--sens", choices=["droite", "gauche"], default="droite", help="sens du quart tournant")
    a("--hauteur", type=float, default=290.0, help="hauteur de sol fini à sol fini")
    a("--plancher", type=float, default=22.0, help="épaisseur du plancher d'arrivée")
    a("--long-depart", type=float, default=160.0, help="longueur au sol le long du mur de départ, de l'angle au nez de la 1re marche")
    a("--long-arrivee", type=float, default=260.0, help="longueur le long du mur d'arrivée, de l'angle au chevêtre (bord de trémie)")
    a("--tremie-largeur", type=float, default=100.0, help="largeur de la trémie, mesurée depuis le mur d'arrivée")
    a("--nb-hauteurs", type=int, default=0, help="nombre de hauteurs de marche (0 = choix automatique selon Blondel)")
    a("--balancement", type=int, nargs=2, default=[3, 11], metavar=("PREMIERE", "DERNIERE"), help="première et dernière marche balancées")
    a("--largeur-depart", type=float, default=80.0, help="longueur utile des marches de la volée de départ, du jeu au mur jusqu'au bord côté jour")
    a("--largeur-arrivee", type=float, default=0.0,
      help="longueur utile des marches de la volée d'arrivée (0 = comme la volée de départ). L'escalier est calculé sur la plus "
           "grande des deux largeurs, puis le bord côté jour (et le poteau) de la volée la plus étroite est rapproché du mur")
    a("--jeu-mur", type=float, default=0.5, help="jeu entre les marches et les murs")
    a("--debord-jour", type=float, default=2.0, help="débord des marches au-delà de la face arrière des crémaillères intérieures")
    a("--recouvrement", type=float, default=3.0, help="recouvrement d'une marche sur la marche du dessous")
    a("--ep-marche", type=float, default=4.0, help="épaisseur des marches")
    a("--ep-cremaillere", type=float, default=4.5, help="épaisseur des crémaillères")
    a("--gorge-jour", type=float, default=12.0, help="gorge mini des crémaillères intérieures (perpendiculaire à la pente)")
    a("--gorge-mur", type=float, default=8.0, help="gorge mini des crémaillères mur (vissées dans les montants)")
    a("--poteau", type=float, default=9.0, help="section du poteau d'angle (carré)")
    a("--poteau-hauteur", type=float, default=0.0,
      help="hauteur du poteau d'angle depuis le sol ; 0 = juste ce qu'il faut pour porter les crémaillères (sans garde-corps)")
    a("--soutien-largeur", type=float, default=17.5, help="largeur du bastaing de soutien dans l'angle des murs")
    a("--fixation-haut", choices=["chevetre", "talon"], default="chevetre",
      help="haut de la crémaillère intérieure : 'chevetre' = elle monte jusqu'au plancher et se boulonne sur la face du chevêtre "
           "(marche du haut entaillée) ; 'talon' = talon vissé sous le chevêtre")
    a("--ancrage", type=float, default=10.0, help="longueur de la partie de crémaillère qui monte jusqu'au plancher (fixation 'chevetre')")
    a("--talon", type=float, default=8.0, help="longueur du talon sous le chevêtre (fixation 'talon')")
    a("--echappee-mini", type=float, default=190.0, help="échappée minimale acceptée (alerte en dessous)")
    a("--rive-basse", choices=["droite", "decoupee"], default="droite",
      help="rive basse des crémaillères : 'droite' = face inférieure du brut conservée (pieds coupés au sol), "
           "'decoupee' = rive suivant la pente, gorge constante")
    a("-o", "--sortie", default="escalier_quart_tournant.pdf", help="fichier PDF produit")
    return p.parse_args(argv)

def fr(v, d=1):
    s = f"{v:.{d}f}".replace('.', ',')
    return "0" if s in ("-0,0", "0,0", "-0") else s

# ----------------------------------------------------------------------------
# Outils géométriques
# ----------------------------------------------------------------------------
def frange(a, b, step):
    out = []; x = a
    while x <= b + 1e-9:
        out.append(x); x += step
    return out

def hp_clip(poly, p0, nrm, off=0.0):
    """Garde la partie du polygone où (p-p0).nrm >= off."""
    out = []
    f = lambda p: (p[0]-p0[0])*nrm[0] + (p[1]-p0[1])*nrm[1] - off
    for i in range(len(poly)):
        a = poly[i]; b = poly[(i+1) % len(poly)]
        fa, fb = f(a), f(b)
        if fa >= 0: out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa/(fa-fb); out.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    return out

def clean(poly):
    p = []
    for q in poly:
        q = (float(q[0]), float(q[1]))
        if not p or math.dist(q, p[-1]) > 1e-4: p.append(q)
    if len(p) > 1 and math.dist(p[0], p[-1]) < 1e-4: p.pop()
    changed = True
    while changed and len(p) > 3:
        changed = False
        for i in range(len(p)):
            a, b, c = p[i-1], p[i], p[(i+1) % len(p)]
            cr = (b[0]-a[0])*(c[1]-b[1]) - (b[1]-a[1])*(c[0]-b[0])
            la, lc = math.dist(a, b), math.dist(b, c)
            if la < 1e-3 or lc < 1e-3 or abs(cr)/(la*lc) < 2e-3:
                p.pop(i); changed = True; break
    return p

def area(p):
    return sum(p[i][0]*p[(i+1) % len(p)][1] - p[(i+1) % len(p)][0]*p[i][1] for i in range(len(p)))/2

def interp(pts, x):
    if x <= pts[0][0]: (x0, y0), (x1, y1) = pts[0], pts[1]
    elif x >= pts[-1][0]: (x0, y0), (x1, y1) = pts[-2], pts[-1]
    else:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1: break
    if x1 == x0: return y0
    return y0 + (y1-y0)*(x-x0)/(x1-x0)

def minus_square(poly, lo, hi):
    return minus_rect(poly, lo, hi, lo, hi)

def minus_rect(poly, x0, x1, y0, y1):
    """Retire du polygone le rectangle [x0,x1]x[y0,y1] et refusionne le contour."""
    A = hp_clip(poly, (x0, 0), (-1, 0)); B = hp_clip(poly, (x1, 0), (1, 0))
    C = hp_clip(hp_clip(poly, (x0, 0), (1, 0)), (x1, 0), (-1, 0))
    C1 = hp_clip(C, (0, y0), (0, -1)); C2 = hp_clip(C, (0, y1), (0, 1))
    parts = [clean(p) for p in (A, B, C1, C2) if len(p) >= 3 and abs(area(p)) > 1e-3]
    parts = [p for p in parts if len(p) >= 3]
    if not parts: return []
    if len(parts) == 1: return parts[0]
    key = lambda v: (round(v[0], 4), round(v[1], 4))
    segs = []
    for p in parts:
        if area(p) < 0: p = p[::-1]
        for i in range(len(p)): segs.append((key(p[i]), key(p[(i+1) % len(p)])))
    verts = set(v for s_ in segs for v in s_); split = []
    for a, b in segs:
        pts = [a, b]
        for v in verts:
            if v in (a, b): continue
            ab = (b[0]-a[0], b[1]-a[1]); av = (v[0]-a[0], v[1]-a[1]); L2 = ab[0]**2+ab[1]**2
            cr = ab[0]*av[1]-ab[1]*av[0]; t = (ab[0]*av[0]+ab[1]*av[1])/L2
            if abs(cr)/math.sqrt(L2) < 1e-3 and 1e-6 < t < 1-1e-6: pts.append(v)
        pts.sort(key=lambda v: (v[0]-a[0])*(b[0]-a[0]) + (v[1]-a[1])*(b[1]-a[1]))
        for i in range(len(pts)-1): split.append((pts[i], pts[i+1]))
    S_ = set(split); bnd = [e for e in split if (e[1], e[0]) not in S_]
    nxt = {a: b for a, b in bnd}; st = bnd[0][0]; out = [st]; cur = nxt[st]
    guard = 0
    while cur != st and guard < 1000:
        out.append(cur); cur = nxt[cur]; guard += 1
    return clean(out)

def pip(pt, poly):
    x, y = pt; c = False
    for i in range(len(poly)):
        a, b = poly[i], poly[i-1]
        if (a[1] > y) != (b[1] > y):
            xi = a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if x < xi: c = not c
    return c

def min_strip(poly, angles_deg):
    best = None
    for ang in angles_deg:
        th = math.radians(ang); nv = (-math.sin(th), math.cos(th))
        pr = [p[0]*nv[0]+p[1]*nv[1] for p in poly]; w = max(pr)-min(pr)
        if best is None or w < best[0]: best = (w, th)
    w, th = best
    u = (math.cos(th), math.sin(th)); L = [p[0]*u[0]+p[1]*u[1] for p in poly]
    return w, th, max(L)-min(L)

# ----------------------------------------------------------------------------
# Calcul de l'escalier
# ----------------------------------------------------------------------------
class Escalier:
    def __init__(self, P):
        self.P = P
        self.alertes = []
        self.left = (P.sens == "gauche")
        self.EP = P.ep_marche; self.TH = P.ep_cremaillere; self.REC = P.recouvrement
        self.WR = P.jeu_mur
        self.Wd = P.largeur_depart
        self.Wa = P.largeur_arrivee if P.largeur_arrivee > 0 else P.largeur_depart
        self.JR = self.WR + max(self.Wd, self.Wa)            # bord côté jour du calcul (plus grande largeur)
        self.JRd = self.WR + self.Wd; self.JRa = self.WR + self.Wa   # bords côté jour réels de chaque volée
        self.Y0 = P.long_depart; self.XE = P.long_arrivee
        self.WL = self.TH                                  # face côté marches des crémaillères mur
        # crémaillères intérieures : x pour la volée de départ, y pour la volée d'arrivée
        self.INx = self.JRd - P.debord_jour - self.TH; self.JXx = self.INx + self.TH
        self.INy = self.JRa - P.debord_jour - self.TH; self.JXy = self.INy + self.TH
        self.PO0x, self.PO1x = self.JXx, self.JXx + P.poteau   # poteau côté vide
        self.PO0y, self.PO1y = self.JXy, self.JXy + P.poteau
        self.CHEV = P.hauteur - P.plancher                  # dessous du plancher / chevêtre
        self.R = (self.JR - self.WR)/2
        self.A1 = self.Y0 - self.JR; self.arc = math.pi/2*self.R; self.A2 = self.XE - self.JR
        if self.A1 <= 0 or self.A2 <= 0:
            raise EscalierErreur("Encombrement trop petit pour la largeur de marche demandée.")
        self.S = self.A1 + self.arc + self.A2
        self.choisir_hauteurs()
        self.balancer()
        # giron côté jour mesuré sur les bords réels (après rapprochement du bord de la volée la plus étroite)
        self.collet = self.girons_jour(); self.collet_mini = min(self.collet)
        if self.collet_mini < 10:
            self.alertes.append(f"Giron mini côté jour de {self.collet_mini:.1f} cm (moins de 10 cm) : élargir la zone balancée.")
        self.marches()
        self.cremailleres()
        self.supports()
        self.poteau_et_entailles()
        self.TIGES = []
        if self.ancrage_chevetre('int_haut'):
            m = self.n-1; La = self.P.ancrage
            self.TREADS[m] = minus_rect(self.TREADS[m], self.XE-La, self.XE+1, self.INy, self.JRa+1)
            self.notes[m].append(f"Entaille de {fr(La)} × {fr(self.JRa-self.INy)} cm à l'arrière côté jour, pour le passage de la crémaillère.")
            H = self.P.hauteur; c = self.CHEV
            self.TIGES = [c + (H-c)*0.3, c + (H-c)*0.75]
        self.echappee = self.calc_echappee()
        if self.echappee < P.echappee_mini:
            self.alertes.append(f"Échappée de {self.echappee:.1f} cm sous la trémie, inférieure à {P.echappee_mini:.0f} cm : "
                                f"élargir la trémie.")

    # --- hauteur / giron
    def choisir_hauteurs(self):
        P = self.P
        if P.nb_hauteurs and P.nb_hauteurs > 2:
            n = P.nb_hauteurs
        else:
            best = None
            for n in range(5, 40):
                h = P.hauteur/n; g = self.S/(n-1)
                if not (15.0 <= h <= 21.0): continue
                sc = abs(2*h+g-63)
                if best is None or sc < best[0]: best = (sc, n)
            if best is None: raise EscalierErreur("Impossible de trouver un nombre de marches raisonnable.")
            n = best[1]
        self.n = n; self.h = P.hauteur/n; self.g = self.S/(n-1)
        self.s = [k*self.g for k in range(n)]
        self.blondel = 2*self.h + self.g
        if not (60 <= self.blondel <= 64.5):
            self.alertes.append(f"Pas de Blondel 2h+g = {self.blondel:.1f} cm, hors de la plage confortable 60 à 64 cm.")

    def walk(self, t):
        if t <= self.A1: return (self.WR+self.R, self.Y0-t)
        if t <= self.A1+self.arc:
            ang = math.pi + (t-self.A1)/self.R
            return (self.JR+self.R*math.cos(ang), self.JR+self.R*math.sin(ang))
        return (self.JR+(t-self.A1-self.arc), self.WR+self.R)

    def inner(self, u):
        """Point du bord côté jour réel à la distance développée u (depuis le nez de la première marche)."""
        a1 = self.Y0 - self.JRa
        return (self.JRd, self.Y0-u) if u <= a1 else (self.JRd+(u-a1), self.JRa)

    def outer_from(self, uin, k):
        p = self.inner(uin); q = self.walk(self.s[k]); dx, dy = q[0]-p[0], q[1]-p[1]; c = []
        if dx < -1e-9:
            t = (self.WR-p[0])/dx; y = p[1]+t*dy
            if y >= self.WR-1e-9: c.append((t, (self.WR, y)))
        if dy < -1e-9:
            t = (self.WR-p[1])/dy; x = p[0]+t*dx
            if x >= self.WR-1e-9: c.append((t, (x, self.WR)))
        return min(c)[1] if c else None

    def odist(self, p):
        return (self.Y0-p[1]) if abs(p[0]-self.WR) < 1e-6 else (self.Y0-self.WR)+(p[0]-self.WR)

    def balancer(self):
        P = self.P; n = self.n
        m1, m2 = P.balancement
        a = m1-1; N = m2-m1+1
        if N < 2 or a < 0 or a+N > n-1:
            raise EscalierErreur(f"Balancement {m1}-{m2} impossible : les marches vont de 1 à {n-1}.")
        if self.s[a] > self.A1 + 1e-9:
            raise EscalierErreur(f"Balancement : la marche {m1} commence déjà dans le tournant ; il faut commencer le balancement plus bas.")
        if self.s[a+N] < self.A1 + self.arc - 1e-9:
            raise EscalierErreur(f"Balancement : la marche {m2} se termine avant la fin du tournant ; il faut finir le balancement plus haut.")
        w = [math.sin(math.pi*(j+0.5)/N) for j in range(N)]
        # déficit de longueur du bord côté jour réel par rapport à la ligne de foulée, absorbé par le balancement
        self.deficit = self.arc - (self.JR-self.JRa) - (self.JR-self.JRd)
        if self.deficit <= 0:
            raise EscalierErreur("Écart de largeur utile entre les deux volées trop grand pour ce tournant : rapprocher les deux largeurs "
                                 "ou élargir le tournant (rayon de giron plus grand).")
        D = self.deficit/sum(w)
        G = [self.g]*(n-1)
        for j in range(N): G[a+j] -= D*w[j]
        uu = [0.0]
        for x in G: uu.append(uu[-1]+x)
        self.G = G; self.uu = uu
        self.LINES = []
        oo = []
        for k in range(n):
            o = self.outer_from(uu[k], k)
            if o is None: raise EscalierErreur("Balancement impossible avec ces paramètres (ligne de nez hors de l'escalier).")
            self.LINES.append((self.inner(uu[k]), o)); oo.append(self.odist(o))
        go = [oo[i+1]-oo[i] for i in range(n-1)]
        if min(go) <= 0: raise EscalierErreur("Balancement impossible : des lignes de nez se croisent côté mur. Élargis la zone balancée.")
        self.giron_mur = go
        self.collet_calcul = min(G); self.mur_maxi = max(go)

    def line_normal(self, k):
        a, b = self.LINES[k]; dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy)
        nx, ny = -dy/L, dx/L
        ref = self.walk(self.s[k]+1)
        if (ref[0]-a[0])*nx + (ref[1]-a[1])*ny < 0: nx, ny = -nx, -ny
        return a, (nx, ny)

    def sdist(self, pt, k):
        a, nr = self.line_normal(k); return (pt[0]-a[0])*nr[0] + (pt[1]-a[1])*nr[1]

    # --- marches
    def marches(self):
        n = self.n; self.TREADS = {}; self.notes = {}
        for m in range(1, n):
            poly = [(self.WR, self.WR), (self.XE, self.WR), (self.XE, self.JRa), (self.JRd, self.JRa), (self.JRd, self.Y0), (self.WR, self.Y0)]
            p0, nr = self.line_normal(m-1); poly = hp_clip(poly, p0, nr, 0)
            p1, nr1 = self.line_normal(m); back = self.REC if m <= n-2 else 0
            poly = clean(hp_clip(poly, p1, (-nr1[0], -nr1[1]), -back))
            note = []
            # marche dont le nez est sur la volée de départ et qui file le long de la crémaillère haute :
            # on l'arrête contre le poteau
            if self.jour_hit(m-1)[0] == 'depart' and max(q[0] for q in poly) > self.PO1x+1e-6:
                poly = clean(hp_clip(poly, (self.PO1x, 0), (-1, 0)))
                note.append("Bout côté jour coupé d'équerre à l'aplomb de la face du poteau.")
            self.TREADS[m] = poly; self.notes[m] = note
        # marche sur les deux crémaillères mur
        for m, poly in self.TREADS.items():
            if any(abs(q[0]-self.WR) < 1e-6 and q[1] < self.WR+self.TH+1 for q in poly) and \
               any(abs(q[1]-self.WR) < 1e-6 for q in poly):
                self.notes[m].append("Repose sur les deux crémaillères mur.")

    def jour_hit(self, k):
        """Point où la ligne de nez k coupe le bord côté jour réel ; renvoie (volée, point, développé le long du bord)."""
        a, b = self.LINES[k]
        dx, dy = a[0]-b[0], a[1]-b[1]
        cands = []
        if abs(dx) > 1e-9:                      # bord de la volée de départ x = JRd, y >= JRa
            t = (self.JRd-b[0])/dx; y = b[1]+t*dy
            if t > 0 and y >= self.JRa-1e-6: cands.append((t, 'depart', (self.JRd, y)))
        if abs(dy) > 1e-9:                      # bord de la volée d'arrivée y = JRa, x >= JRd
            t = (self.JRa-b[1])/dy; x = b[0]+t*dx
            if t > 0 and x >= self.JRd-1e-6: cands.append((t, 'arrivee', (x, self.JRa)))
        t, cote, pt = min(cands)
        dev = (self.Y0-pt[1]) if cote == 'depart' else (self.Y0-self.JRa)+(pt[0]-self.JRd)
        return cote, pt, dev

    def girons_jour(self):
        devs = [self.jour_hit(k)[2] for k in range(self.n)]
        return [devs[i+1]-devs[i] for i in range(self.n-1)]

    # --- crémaillères
    def palier(self, pt):
        x, y = pt
        if x > self.XE+1e-9: return None
        m = 0
        for k in range(1, self.n):
            if self.sdist(pt, k-1) >= self.REC-1e-9: m = k
        return m if m >= 1 else None

    def top_at(self, pt):
        m = self.palier(pt); return None if m is None else m*self.h - self.EP

    def cremailleres(self):
        Y0, WL, XE, TH = self.Y0, self.WL, self.XE, self.TH
        INx, JXx, INy, JXy = self.INx, self.JXx, self.INy, self.JXy
        self.CR = {
            'mur_dep': dict(face=lambda d: (WL, Y0-d), back=lambda d: (self.WR+1e-3, Y0-d), rng=(0, Y0)),
            'mur_arr': dict(face=lambda d: (WL+(d-(Y0-WL)), WL), back=lambda d: (WL+(d-(Y0-WL)), self.WR+1e-3), rng=(Y0-WL, Y0-WL+XE-WL)),
            'int_bas': dict(face=lambda d: (INx, Y0-d), back=lambda d: (JXx-1e-3, Y0-d), rng=(0, Y0-INy)),
            'int_haut': dict(face=lambda d: (INx+(d-(Y0-INy)), INy), back=lambda d: (INx+(d-(Y0-INy)), JXy-1e-3),
                             rng=(Y0-INy+TH, Y0-INy+XE-INx)),
        }
        self.THR = {'mur_dep': self.P.gorge_mur, 'mur_arr': self.P.gorge_mur, 'int_bas': self.P.gorge_jour, 'int_haut': self.P.gorge_jour}
        self.PAL = {}
        for k, c in self.CR.items():
            a, b = c['rng']; prof = []
            for d in frange(a, b, 0.05):
                zs = [z for z in (self.top_at(c['face'](d)), self.top_at(c['back'](d))) if z is not None]
                prof.append((d, min(zs) if zs else None))
            self.PAL[k] = self.steps(prof)
        bd = self.bottom_line('mur_dep'); ba = self.bottom_line('mur_arr')
        self.CORNER_Z = min(interp(bd, Y0-WL), ba[0][1])
        self.OUT = {k: self.outline(k) for k in self.CR}
        self.STRIP = {}
        if self.P.rive_basse == "droite":
            self.rives_droites()
        last_top = (self.n-1)*self.h - self.EP
        self.talon_ok = last_top <= self.CHEV + 1e-6
        if not self.talon_ok:
            self.alertes.append("Le dernier palier est plus haut que le dessous du chevêtre : le talon d'appui est impossible, "
                                "prévoir une platine métallique.")

    @staticmethod
    def steps(prof):
        out = []; cur = None
        for d, z in prof:
            if z is None:
                if cur: out.append(cur); cur = None
                continue
            if cur and abs(cur[0]-z) < 1e-6: cur = (z, cur[1], d)
            else:
                if cur: out.append(cur)
                cur = (z, d, d)
        if cur: out.append(cur)
        return [p for p in out if p[2]-p[1] > 0.2]

    def bottom_line(self, k):
        pal = self.PAL[k]
        c = sorted((d1, z) for z, d0, d1 in pal[:-1])
        out = []
        for i, (d, z) in enumerate(c):
            j0 = max(0, i-2); j1 = min(len(c)-1, i+2)
            sl = (c[j1][1]-c[j0][1])/(c[j1][0]-c[j0][0]) if c[j1][0] > c[j0][0] else 0
            out.append([d, z - self.THR[k]*math.sqrt(1+sl*sl)])
        for i in range(len(out)-2, -1, -1): out[i][1] = min(out[i][1], out[i+1][1])
        changed = True
        while changed and len(out) > 2:
            changed = False
            for i in range(1, len(out)-1):
                (x0, y0), (x1, y1), (x2, y2) = out[i-1], out[i], out[i+1]
                if x2 > x0 and y1 > y0 + (y2-y0)*(x1-x0)/(x2-x0) + 0.05:
                    out.pop(i); changed = True; break
        res = []
        for d, z in out:
            if res and abs(d-res[-1][0]) < 0.3: res[-1] = (res[-1][0], min(res[-1][1], z))
            else: res.append((d, z))
        if len(res) == 1: res.append((res[0][0]+10, res[0][1]+10))
        return res

    def outline(self, k):
        pal = self.PAL[k]; a, b = self.CR[k]['rng']
        top = []
        for z, d0, d1 in pal: top += [(d0, z), (d1, z)]
        top = self.lever_bout(k, top)
        bot = self.bottom_line(k)
        start, end, bottom = [], [], bot
        if k in ('mur_dep', 'int_bas'):
            d0 = pal[0][1]
            (x0, y0), (x1, y1) = bot[0], bot[1]
            xf = x0 + (0-y0)*(x1-x0)/(y1-y0) if y1 != y0 else x0
            start = [(d0, 0)]
            bottom = [(max(xf, d0+0.5), 0)] + [p for p in bot if p[1] > 0]
        if k == 'mur_dep':
            zc = self.CORNER_Z
            end = [(b, top[-1][1]), (b, zc)]
            bottom = [p for p in bottom if p[0] < b-self.WL and p[1] <= zc+1e-6] + [(b-self.WL, zc)]
        elif k == 'int_bas':
            end = [(b, top[-1][1]), (b, interp(bot, b))]
            bottom = [p for p in bottom if p[0] < b]
        if k == 'mur_arr':
            start = [(a, self.CORNER_Z)]
            bottom = [p for p in bottom if p[0] > a+1e-6 and p[1] > self.CORNER_Z-1e-6]
        if k == 'int_haut':
            start = [(a, bot[0][1])]
            bottom = [p for p in bottom if p[0] > a]
        if k in ('mur_arr', 'int_haut'):
            if self.talon_ok_pre():
                zb = interp(bot, b+self.P.talon)
                end = [(b, top[-1][1]), (b, self.CHEV), (b+self.P.talon, self.CHEV), (b+self.P.talon, zb)]
                bottom = [p for p in bottom if p[0] < b+self.P.talon]
            else:
                end = [(b, top[-1][1]), (b, interp(bot, b))]
                bottom = [p for p in bottom if p[0] < b]
        poly = start + top + end + bottom[::-1]
        return clean(poly)

    def rives_droites(self):
        """Remplace la rive basse découpée par la face inférieure du brut (droite), pieds coupés au sol."""
        Y0, WL = self.Y0, self.WL
        ZB = {}
        for k in self.CR:
            mir = self.view_mirror(k); sg = -1 if mir else 1
            P_ = [(sg*p[0], p[1]) for p in self.OUT[k]]
            w, th, _ = min_strip(P_, [i*0.05 for i in range(-1790, 1791)])
            nv = (-math.sin(th), math.cos(th)); on = min(p[0]*nv[0]+p[1]*nv[1] for p in P_)
            self.STRIP[k] = th
            ZB[k] = (lambda d, sg=sg, th=th, on=on: (on + math.sin(th)*sg*d)/math.cos(th))
        self.ZB = ZB
        for k in self.CR:
            pal = self.PAL[k]; a, b = self.CR[k]['rng']; zb = ZB[k]
            top = []
            for z, d0, d1 in pal: top += [(d0, z), (d1, z)]
            top = self.lever_bout(k, top)
            if k in ('mur_dep', 'int_bas'):
                d0 = pal[0][1]
                if zb(d0) >= 0:
                    start = [(d0, zb(d0))]; foot = []
                else:
                    # point où la rive droite coupe le sol
                    lo, hi = d0, b
                    for _ in range(60):
                        mid = (lo+hi)/2
                        if zb(mid) < 0: lo = mid
                        else: hi = mid
                    start = [(d0, 0)]; foot = [(hi, 0)]
            else:
                start = [(a, zb(a))]; foot = []
            if k == 'mur_dep':
                zc = zb(b)
                end = [(b, top[-1][1]), (b, zc), (b-WL, zc), (b-WL, zb(b-WL))]
            elif k == 'int_bas':
                end = [(b, top[-1][1]), (b, zb(b))]
            else:
                if self.talon_ok_pre():
                    t = self.P.talon
                    end = [(b, top[-1][1]), (b, self.CHEV), (b+t, self.CHEV), (b+t, zb(b+t))]
                else:
                    end = [(b, top[-1][1]), (b, zb(b))]
            self.OUT[k] = clean(start + top + end + foot[::-1])
        self.CORNER_Z = ZB['mur_dep'](Y0)

    def talon_ok_pre(self):
        return self.P.fixation_haut == "talon" and (self.n-1)*self.h - self.EP <= self.CHEV + 1e-6 and self.P.talon > 0

    def ancrage_chevetre(self, k):
        return k == 'int_haut' and self.P.fixation_haut == "chevetre" and self.P.ancrage > 0

    def lever_bout(self, k, top):
        """Fixation 'chevetre' : le bout haut de la crémaillère intérieure monte jusqu'au plancher fini."""
        if not self.ancrage_chevetre(k): return top
        b = self.CR[k]['rng'][1]; La = self.P.ancrage
        z = top[-1][1]
        top = [p for p in top if p[0] < b-La-1e-6]
        return top + [(b-La, z), (b-La, self.P.hauteur), (b, self.P.hauteur)]

    def body_at(self, k, d):
        poly = self.OUT[k]; ys = []
        for i in range(len(poly)):
            (x0, y0), (x1, y1) = poly[i], poly[(i+1) % len(poly)]
            if (x0-d)*(x1-d) <= 0 and x0 != x1: ys.append(y0+(y1-y0)*(d-x0)/(x1-x0))
        return (min(ys), max(ys)) if ys else (0, 0)

    # --- hauteur du poteau, entailles des marches
    def poteau_et_entailles(self):
        P = self.P; self.POT_H = 0.0
        if P.poteau <= 0: return
        def overlap(poly):
            cp = poly
            for p0, nrm in (((self.PO0x, 0), (1, 0)), ((self.PO1x, 0), (-1, 0)), ((0, self.PO0y), (0, 1)), ((0, self.PO1y), (0, -1))):
                cp = hp_clip(cp, p0, nrm)
                if len(cp) < 3: return False
            return abs(area(cp)) > 0.05
        # hauteur nécessaire : dessus des crémaillères intérieures au contact du poteau
        need = 0.0
        ranges = {'int_bas': (self.Y0-self.PO1y, self.Y0-self.PO0y),
                  'int_haut': ((self.Y0-self.INy)+(self.PO0x-self.INx), (self.Y0-self.INy)+(self.PO1x-self.INx))}
        for k, (d0, d1) in ranges.items():
            for d in frange(d0+0.01, d1-0.01, 0.25):
                lo, hi = self.body_at(k, d)
                need = max(need, hi)
        self.POT_AUTO = (P.poteau_hauteur <= 0)
        self.POT_H = need if self.POT_AUTO else P.poteau_hauteur
        if not self.POT_AUTO and P.poteau_hauteur < need - 0.1:
            self.alertes.append(f"Poteau de {P.poteau_hauteur:.0f} cm : il faut au moins {need:.1f} cm pour porter les crémaillères.")
        # entailles : seulement les marches dont le dessous est plus bas que le haut du poteau
        for m, poly in self.TREADS.items():
            if not overlap(poly): continue
            under = m*self.h - self.EP
            if under < self.POT_H - 0.05:
                self.TREADS[m] = minus_rect(poly, self.PO0x, self.PO1x, self.PO0y, self.PO1y)
                self.notes[m].append("Entaille au droit du poteau.")
            elif under < self.POT_H + 0.5:
                self.notes[m].append("Repose en partie sur le dessus du poteau.")

    # --- supports, boulons
    def supports(self):
        Y0, WL = self.Y0, self.WL
        chain = [(Y0-WL, self.CORNER_Z)] + [p for p in self.bottom_line('mur_arr') if p[0] > Y0-WL+0.5 and p[1] > self.CORNER_Z]
        if len(chain) < 2: chain.append((chain[0][0]+10, chain[0][1]))
        sw = self.P.soutien_largeur
        if self.P.rive_basse == "droite":
            zA = self.ZB['mur_arr']
            self.SUP_POLY = [(0, 0), (sw, 0), (sw, zA((Y0-WL)+sw-WL)), (WL, zA(Y0-WL)), (WL, self.CORNER_Z), (0, self.CORNER_Z)]
        else:
            self.SUP_POLY = [(0, 0), (sw, 0), (sw, interp(chain, (Y0-WL)+sw-WL)), (WL, self.CORNER_Z), (0, self.CORNER_Z)]
        # boulons des crémaillères intérieures sur le poteau
        cx = (self.PO0x+self.PO1x)/2; cy = (self.PO0y+self.PO1y)/2
        d_ib = Y0 - cy; d_ih = (Y0-self.INy) + (cx-self.INx)
        b1 = self.body_at('int_bas', d_ib); b2 = self.body_at('int_haut', d_ih)
        cand1 = [z for z in frange(math.ceil(b1[0]+4.5), math.floor(b1[1]-4.5), 1.0)]
        cand2 = [z for z in frange(math.ceil(b2[0]+4.5), math.floor(b2[1]-4.5), 1.0)]
        best = None
        for i in range(len(cand1)):
            for j in range(i+1, len(cand1)):
                for k in range(len(cand2)):
                    for l in range(k+1, len(cand2)):
                        zs = sorted([cand1[i], cand1[j], cand2[k], cand2[l]])
                        gap = min(zs[q+1]-zs[q] for q in range(3))
                        spread = (cand1[j]-cand1[i]) + (cand2[l]-cand2[k])
                        sc = (min(gap, 6), spread)
                        if best is None or sc > best[0]: best = (sc, (cand1[i], cand1[j]), (cand2[k], cand2[l]))
        if best is None:
            self.BOLTS = {'int_bas': (d_ib, ()), 'int_haut': (d_ih, ())}
            self.alertes.append("Pas assez de bois sur les crémaillères intérieures au droit du poteau pour y placer deux boulons : "
                                "augmenter la gorge côté jour.")
        else:
            if best[0][0] < 4:
                self.alertes.append("Boulons du poteau à moins de 4 cm d'écart en hauteur : vérifier qu'ils ne se croisent pas.")
            self.BOLTS = {'int_bas': (d_ib, best[1]), 'int_haut': (d_ih, best[2])}

    def calc_echappee(self):
        Y = self.P.tremie_largeur; ceil = self.CHEV
        L = self.LINES
        def side(Pt, Ln):
            (x1, y1), (x2, y2) = Ln; return (x2-x1)*(Pt[1]-y1)-(y2-y1)*(Pt[0]-x1)
        best = 999.0
        if Y > self.Y0: return best
        return self._echappee_edge(Y, side)

    def _echappee_edge(self, Y, side):
        best = 999.0; L = self.LINES
        for x in frange(self.WR+0.5, self.JRd-0.5, (self.JRd-self.WR-1)/60):
            sd = [side((x, Y), l) for l in L]
            for k in range(self.n-1):
                if sd[k]*sd[k+1] <= 0:
                    f = abs(sd[k])/(abs(sd[k])+abs(sd[k+1])) if (abs(sd[k])+abs(sd[k+1])) > 0 else 0
                    best = min(best, self.CHEV - ((k+1)*self.h + f*self.h)); break
        return best

    # --- repères locaux
    def on_line(self, p, k, tol=1e-2):
        a, b = self.LINES[k]; dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy)
        return abs((p[0]-a[0])*dy - (p[1]-a[1])*dx)/L < tol

    def tread_local(self, m):
        """Coordonnées de la marche m : origine à l'extrémité gauche du nez (vue de dessus, nez en bas),
        X le long du nez vers la droite, Y vers l'arrière. Renvoie (points, types d'arêtes, zones d'appui)."""
        poly = self.TREADS[m]
        if area(poly) > 0: poly = poly[::-1]
        fr_ = [i for i, p in enumerate(poly) if self.on_line(p, m-1)]
        wallpt = self.LINES[m-1][1]
        w = min(fr_, key=lambda i: math.dist(poly[i], wallpt)); c = max(fr_, key=lambda i: math.dist(poly[i], wallpt))
        O = poly[w]; ux = (poly[c][0]-O[0], poly[c][1]-O[1]); L = math.hypot(*ux); ux = (ux[0]/L, ux[1]/L)
        _, nr = self.line_normal(m-1)
        tf = lambda p: ((p[0]-O[0])*ux[0]+(p[1]-O[1])*ux[1], (p[0]-O[0])*nr[0]+(p[1]-O[1])*nr[1])
        n_ = len(poly); step = 1 if (w+1) % n_ in fr_ else -1
        idx = [(w+step*i) % n_ for i in range(n_)]
        P_ = [poly[i] for i in idx]
        kinds = [('nez' if self.on_line(P_[i], m-1) and self.on_line(P_[(i+1) % n_], m-1) else 'autre') for i in range(n_)]
        bands = []
        rects = [(0, self.WL, 0, self.Y0), (self.WL, self.XE, 0, self.WL), (self.INx, self.JXx, self.INy, self.Y0), (self.JXx, self.XE, self.INy, self.JXy)]
        for r in rects:
            cp = self.TREADS[m]
            for p0, nrm in (((r[0], 0), (1, 0)), ((r[1], 0), (-1, 0)), ((0, r[2]), (0, 1)), ((0, r[3]), (0, -1))):
                cp = hp_clip(cp, p0, nrm)
                if len(cp) < 3: break
            if len(cp) >= 3:
                cp = clean(cp)
                if len(cp) >= 3 and abs(area(cp)) > 0.5: bands.append([tf(p) for p in cp])
        pts = [tf(p) for p in P_]
        if self.left:
            # miroir : l'extrémité gauche du nez est alors côté jour
            xs_nose = [pts[i][0] for i in range(n_) if self.on_line(P_[i], m-1)]
            xm = max(xs_nose)
            mir = lambda p: (xm-p[0], p[1])
            pts = [mir(p) for p in pts]; bands = [[mir(p) for p in b] for b in bands]
            # renuméroter : départ au nouveau point d'origine (0,0), sens trigonométrique
            pts = pts[::-1]; kinds = kinds[::-1]
            kinds = kinds[1:] + kinds[:1]
            i0 = min(range(n_), key=lambda i: math.hypot(*pts[i]))
            pts = pts[i0:] + pts[:i0]; kinds = kinds[i0:] + kinds[:i0]
        return pts, kinds, bands

    def angles(self, Lc):
        n_ = len(Lc); ar = area(Lc); out = []
        for i in range(n_):
            a, b, c = Lc[i-1], Lc[i], Lc[(i+1) % n_]
            v1 = (a[0]-b[0], a[1]-b[1]); v2 = (c[0]-b[0], c[1]-b[1])
            ang = math.degrees(math.atan2(v1[0]*v2[1]-v1[1]*v2[0], v1[0]*v2[0]+v1[1]*v2[1]))
            if ar > 0: ang = -ang
            out.append(ang % 360)
        return out

    def view_mirror(self, k):
        """Vue côté marches d'une crémaillère : faut-il inverser le développé ?"""
        return k.startswith('int') != self.left

    def board(self, k):
        """Contour de la crémaillère dans le repère du brut (face inférieure du brut = axe X)."""
        mir = self.view_mirror(k)
        T = (lambda p: (-p[0], p[1])) if mir else (lambda p: (p[0], p[1]))
        poly = [T(p) for p in self.OUT[k]]
        if k in self.STRIP:
            th = self.STRIP[k]
        else:
            w, th, L = min_strip(poly, [i*0.05 for i in range(-1790, 1791)])
        u = (math.cos(th), math.sin(th)); nv = (-math.sin(th), math.cos(th))
        ou = min(p[0]*u[0]+p[1]*u[1] for p in poly); on = min(p[0]*nv[0]+p[1]*nv[1] for p in poly)
        F = lambda p: ((T(p)[0]*u[0]+T(p)[1]*u[1])-ou, (T(p)[0]*nv[0]+T(p)[1]*nv[1])-on)
        pts = [F(p) for p in self.OUT[k]]
        if area(pts) < 0: pts = pts[::-1]
        i0 = min(range(len(pts)), key=lambda i: math.hypot(*pts[i]))
        pts = pts[i0:] + pts[:i0]
        bolts = [F((self.BOLTS[k][0], z)) for z in self.BOLTS[k][1]] if k in self.BOLTS else []
        b = self.CR[k]['rng'][1]
        self.RODS = getattr(self, 'RODS', {})
        self.RODS[k] = [(F((b, z)), F((b-self.P.ancrage+2.5, z))) for z in self.TIGES] if self.ancrage_chevetre(k) else []
        Lb = max(p[0] for p in pts); Wb = max(p[1] for p in pts)
        return pts, bolts, Lb, Wb, abs(math.degrees(th))

# ----------------------------------------------------------------------------
# Rendu PDF
# ----------------------------------------------------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Flowable, CondPageBreak)
from reportlab.lib.pagesizes import landscape

INK = colors.HexColor("#1f2a36"); MUTED = colors.HexColor("#5d6874"); RULE = colors.HexColor("#c9ced3")
WOOD = colors.HexColor("#efe4cf"); NEZ = colors.HexColor("#c2410c"); DIM = colors.HexColor("#1d4ed8")
CREM = colors.HexColor("#c9a97e"); TRE = colors.HexColor("#0f766e"); BAND = colors.HexColor("#cfe5df")


class Fig(Flowable):
    """Dessin vectoriel : `world` = (xmin, ymin, xmax, ymax) en cm, `draw(c, T, s)` dessine avec T(x,y)->points."""
    def __init__(self, world, draw, width, max_height):
        super().__init__()
        x0, y0, x1, y1 = world
        self.world = world; self.drawfn = draw
        sx = width/(x1-x0); sy = max_height/(y1-y0)
        self.s = min(sx, sy)
        self.width = width; self.height = (y1-y0)*self.s
        self.dx = (width - (x1-x0)*self.s)/2
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        c = self.canv; x0, y0, x1, y1 = self.world; s = self.s; dx = self.dx
        T = lambda x, y: (dx + (x-x0)*s, (y-y0)*s)
        self.drawfn(c, T, s)

def poly_path(c, T, pts, fill=None, stroke=INK, width=0.6, dash=None, close=True):
    p = c.beginPath(); X, Y = T(*pts[0]); p.moveTo(X, Y)
    for q in pts[1:]:
        X, Y = T(*q); p.lineTo(X, Y)
    if close: p.close()
    c.saveState()
    if fill is not None: c.setFillColor(fill)
    if stroke is not None: c.setStrokeColor(stroke); c.setLineWidth(width)
    if dash: c.setDash(*dash)
    c.drawPath(p, fill=1 if fill is not None else 0, stroke=1 if stroke is not None else 0)
    c.restoreState()

def line(c, T, a, b, color=INK, width=0.6, dash=None):
    c.saveState(); c.setStrokeColor(color); c.setLineWidth(width)
    if dash: c.setDash(*dash)
    X0, Y0 = T(*a); X1, Y1 = T(*b); c.line(X0, Y0, X1, Y1); c.restoreState()

def text(c, T, x, y, s, size=6, color=INK, anchor="middle", bold=False, dy=0):
    X, Y = T(x, y); c.saveState(); c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    Y += dy - size*0.35
    if anchor == "middle": c.drawCentredString(X, Y, s)
    elif anchor == "end": c.drawRightString(X, Y, s)
    else: c.drawString(X, Y, s)
    c.restoreState()

def styles():
    ss = getSampleStyleSheet()
    st = {
        'h1': ParagraphStyle('h1', parent=ss['Title'], fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=0, textColor=INK, spaceAfter=6),
        'h2': ParagraphStyle('h2', parent=ss['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=INK, spaceBefore=8, spaceAfter=4),
        'h3': ParagraphStyle('h3', parent=ss['Heading3'], fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=INK, spaceBefore=2, spaceAfter=2),
        'p': ParagraphStyle('p', parent=ss['BodyText'], fontName='Helvetica', fontSize=9, leading=12, textColor=INK, spaceAfter=4),
        'small': ParagraphStyle('small', parent=ss['BodyText'], fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=MUTED, spaceAfter=3),
        'alert': ParagraphStyle('alert', parent=ss['BodyText'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=NEZ, spaceAfter=3),
    }
    return st

def tbl(rows, header=True, widths=None, size=7):
    t = Table(rows, colWidths=widths, hAlign='LEFT')
    sty = [('FONT', (0, 0), (-1, -1), 'Helvetica', size), ('TEXTCOLOR', (0, 0), (-1, -1), INK),
           ('ALIGN', (1, 0), (-1, -1), 'RIGHT'), ('LINEBELOW', (0, 0), (-1, -1), 0.25, RULE),
           ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
           ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3)]
    if header: sty += [('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', size), ('TEXTCOLOR', (0, 0), (-1, 0), MUTED)]
    t.setStyle(TableStyle(sty)); return t

def split_cols(rows, ncols, header):
    """Répartit une longue liste de lignes en plusieurs tableaux côte à côte."""
    per = math.ceil(len(rows)/ncols)
    parts = [rows[i*per:(i+1)*per] for i in range(ncols) if rows[i*per:(i+1)*per]]
    tables = [tbl([header]+p) for p in parts]
    t = Table([tables], hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 10)]))
    return t

NAMES = {'mur_dep': "Crémaillère mur, volée de départ", 'mur_arr': "Crémaillère mur, volée d'arrivée",
         'int_bas': "Crémaillère intérieure basse (volée de départ)", 'int_haut': "Crémaillère intérieure haute (volée d'arrivée)"}
LOW = {'mur_dep': "départ", 'mur_arr': "angle", 'int_bas': "départ", 'int_haut': "poteau"}
HIGH = {'mur_dep': "angle", 'mur_arr': "chevêtre", 'int_bas': "poteau", 'int_haut': "chevêtre"}


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

def prism_faces(poly2d, O, A, B, Tv, color, edge=True):
    """Prisme : polygone (a,b) dans le plan O + a*A + b*B, extrudé de Tv. Renvoie des faces (pts, normale extérieure, couleur)."""
    if area(poly2d) < 0: poly2d = poly2d[::-1]
    P0 = [v_add(O, v_add(v_mul(A, a), v_mul(B, b))) for a, b in poly2d]
    P1 = [v_add(p, Tv) for p in P0]
    tn = v_norm(Tv); faces = []
    faces.append((P0[::-1], v_mul(tn, -1), color, edge))
    faces.append((P1, tn, color, edge))
    n_ = len(poly2d)
    for i in range(n_):
        (a0, b0), (a1, b1) = poly2d[i], poly2d[(i+1) % n_]
        dx, dy = a1-a0, b1-b0
        nrm = v_norm(v_sub(v_mul(A, dy), v_mul(B, dx)))
        faces.append(([P0[i], P0[(i+1) % n_], P1[(i+1) % n_], P1[i]], nrm, color, edge))
    return faces

def scene(E):
    sgx = -1 if E.left else 1
    W = lambda x, y, z: (sgx*x, -y, z)          # plan -> monde (x est, y nord, z haut)
    Wv = lambda x, y, z: (sgx*x, -y, z)         # vecteurs
    faces = []
    TREAD = colors.HexColor("#d9b98a"); CR = colors.HexColor("#b98a55"); POT = colors.HexColor("#8a5a2b")
    # marches
    for m, poly in E.TREADS.items():
        z0 = m*E.h - E.EP
        pts = [W(x, y, 0)[:2] for x, y in poly]
        faces += prism_faces(pts, (0, 0, z0), (1, 0, 0), (0, 1, 0), (0, 0, E.EP), TREAD)
    # crémaillères (plans verticaux)
    Y0, WL, XE, TH = E.Y0, E.WL, E.XE, E.TH
    defs = {
        'mur_dep': (W(0, Y0, 0), Wv(0, -1, 0), Wv(1, 0, 0)),
        'mur_arr': (W(WL-(Y0-WL), 0, 0), Wv(1, 0, 0), Wv(0, 1, 0)),
        'int_bas': (W(E.INx, Y0, 0), Wv(0, -1, 0), Wv(1, 0, 0)),
        'int_haut': (W(E.INx-(Y0-E.INy), E.INy, 0), Wv(1, 0, 0), Wv(0, 1, 0)),
    }
    for k, (O, A, tdir) in defs.items():
        faces += prism_faces(E.OUT[k], O, A, (0, 0, 1), v_mul(tdir, TH), CR)
    # poteau et bastaing de soutien
    if E.P.poteau > 0:
        sq = [W(E.PO0x, E.PO0y, 0)[:2], W(E.PO1x, E.PO0y, 0)[:2], W(E.PO1x, E.PO1y, 0)[:2], W(E.PO0x, E.PO1y, 0)[:2]]
        faces += prism_faces(sq, (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, E.POT_H), POT)
    faces += prism_faces(E.SUP_POLY, W(0, 0, 0), Wv(1, 0, 0), (0, 0, 1), v_mul(Wv(0, 1, 0), WL), CR)
    # plancher d'arrivée autour de la trémie (translucide) et chevêtre
    SL = colors.HexColor("#9aa4ae"); zc = E.CHEV
    tl = E.P.tremie_largeur
    for (x0, x1, y0, y1) in [(XE, XE+90, 0, tl+70), (0, XE, tl, tl+70)]:
        sq = [W(x0, y0, 0)[:2], W(x1, y0, 0)[:2], W(x1, y1, 0)[:2], W(x0, y1, 0)[:2]]
        for f in prism_faces(sq, (0, 0, zc), (1, 0, 0), (0, 1, 0), (0, 0, E.P.plancher), SL, edge=True):
            faces.append(f + ("slab",))
    return faces

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
        c.setStrokeColor(colors.HexColor("#3a2f25")); c.setLineWidth(0.35)
        c.drawPath(p, fill=1, stroke=1 if edge else 0)
    c.restoreState()

class View3D(Flowable):
    def __init__(self, E, cam, target, width, height):
        super().__init__(); self.E = E; self.cam = cam; self.target = target; self.width = width; self.height = height
    def wrap(self, aw, ah): return self.width, self.height
    def draw(self):
        render_3d(self.canv, (0, 0, self.width, self.height), self.E, self.cam, self.target)

def build_pdf(E, path):
    P = E.P; st = styles(); story = []
    W = A4[0] - 24*mm
    sens = "droite" if not E.left else "gauche"
    MX = (lambda x: -x) if E.left else (lambda x: x)

    # --- page de garde
    story.append(Paragraph(f"Escalier quart tournant à {sens} : plans de fabrication", st['h1']))
    story.append(Paragraph("Marches posées sur crémaillères, poteau d'angle côté vide. Toutes les cotes sont en centimètres.", st['p']))
    rows = [["Résultat", "Valeur"],
            ["Nombre de hauteurs / de marches", f"{E.n} / {E.n-1}"],
            ["Hauteur de marche h", f"{fr(E.h, 2)}"],
            ["Giron sur la ligne de foulée g", f"{fr(E.g, 2)}"],
            ["Pas de Blondel 2h + g", f"{fr(E.blondel, 1)}"],
            ["Ligne de foulée (longueur, distance au mur)", f"{fr(E.S, 1)} ; {fr(E.WR+E.R, 1)}"],
            ["Marches balancées", f"{P.balancement[0]} à {P.balancement[1]}"],
            ["Giron mini côté jour", f"{fr(E.collet_mini)}" + (f" (calc. {fr(E.collet_calcul)})" if abs(E.collet_mini-E.collet_calcul) > 0.05 else "")],
            ["Giron maxi côté mur (développé)", f"{fr(E.mur_maxi)}"],
            ["Échappée sous le bord de la trémie", f"{fr(E.echappee)}"],
            ["Inclinaison moyenne", f"{fr(math.degrees(math.atan(E.h/E.g)), 0)}°"]]
    prow = [["Paramètre", "Valeur"],
            ["Sens", sens], ["Hauteur sol à sol", fr(P.hauteur)], ["Épaisseur du plancher", fr(P.plancher)],
            ["Longueur le long du mur de départ", fr(P.long_depart)], ["Longueur le long du mur d'arrivée", fr(P.long_arrivee)],
            ["Trémie (longueur × largeur)", f"{fr(P.long_arrivee)} × {fr(P.tremie_largeur)}"],
            ["Longueur utile, départ / arrivée", f"{fr(E.Wd)} / {fr(E.Wa)}"], ["Jeu au mur / débord côté jour", f"{fr(P.jeu_mur)} / {fr(P.debord_jour)}"],
            ["Recouvrement", fr(P.recouvrement)], ["Épaisseur marches / crémaillères", f"{fr(P.ep_marche)} / {fr(P.ep_cremaillere)}"],
            ["Gorge crémaillères jour / mur", f"{fr(P.gorge_jour)} / {fr(P.gorge_mur)}"], ["Poteau d'angle", f"{fr(P.poteau)} × {fr(P.poteau)}"],
            ["Hauteur du poteau", (f"{fr(E.POT_H)} (automatique)" if getattr(E, 'POT_AUTO', False) else fr(E.POT_H))],
            ["Bastaing de soutien (largeur)", fr(P.soutien_largeur)],
            ["Fixation en haut", (f"sur la face du chevêtre, ancrage {fr(P.ancrage)}" if P.fixation_haut == "chevetre" else f"talon de {fr(P.talon)} sous le chevêtre")]]
    t = Table([[tbl(rows, size=8), tbl(prow, size=8)]], hAlign='LEFT')
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 12)]))
    story.append(t); story.append(Spacer(1, 6))
    for a in E.alertes: story.append(Paragraph("Attention : " + a, st['alert']))
    story.append(Paragraph("Principe de construction", st['h2']))
    story.append(Paragraph(
        f"Les marches (planches de {fr(P.ep_marche)} cm) reposent sur quatre crémaillères de {fr(P.ep_cremaillere)} cm d'épaisseur : deux côté mur, "
        f"plaquées contre les murs et vissées dans les montants, et deux côté jour, boulonnées sur un poteau d'angle placé côté vide. "
        + (f"Les marches font {fr(E.Wd)} cm de long, de {fr(P.jeu_mur)} cm du mur jusqu'à leur bord côté jour ; la ligne de foulée passe au milieu. "
         if abs(E.Wd-E.Wa) < 1e-6 else
         f"Les marches font {fr(E.Wd)} cm de long sur la volée de départ et {fr(E.Wa)} cm sur la volée d'arrivée, depuis {fr(P.jeu_mur)} cm du mur. "
         f"La ligne de foulée et le giron sont calculés sur la plus grande largeur ({fr(max(E.Wd, E.Wa))} cm, ligne de foulée à "
         f"{fr(E.WR+E.R)} cm du mur). Le bord côté jour de la volée la plus étroite, ses crémaillères intérieures et le poteau sont rapprochés "
         f"du mur, et le balancement est réparti le long de ce bord réel : le bord côté jour étant plus court, les marches tournantes y "
         f"gagnent du giron. ") +
        f"Elles dépassent de {fr(P.debord_jour)} cm la face arrière des crémaillères intérieures, sauf au droit du poteau, et recouvrent de "
        f"{fr(P.recouvrement)} cm la marche du dessous. La première marche déborde de {fr(P.recouvrement)} cm devant les crémaillères.", st['p']))
    story.append(Paragraph(
        f"Toutes les coupes des crémaillères sont d'équerre. Gorge (bois continu sous les entailles, perpendiculairement à la pente) : "
        f"{fr(P.gorge_jour)} cm côté jour, {fr(P.gorge_mur)} cm côté mur. Le chevêtre est supposé au bout de la longueur d'arrivée.", st['p']))

    # --- plan d'ensemble
    story.append(PageBreak()); story.append(Paragraph("Plan d'ensemble", st['h2']))
    xmax = E.XE + 8; world = (MX(xmax) if E.left else -30, -E.Y0-22, 30 if E.left else xmax, 26)
    world = (min(world[0], world[2]), world[1], max(world[0], world[2]), world[3])
    def draw_plan(c, T0, s):
        T = lambda x, y: T0(MX(x), -y)
        line(c, T, (0, E.Y0+8), (0, 0), INK, 1.6); line(c, T, (0, 0), (E.XE+8, 0), INK, 1.6)
        for r in [(0, 0, E.WL, E.Y0), (E.WL, 0, E.XE, E.WL), (E.INx, E.INy, E.JXx, E.Y0), (E.JXx, E.INy, E.XE, E.JXy)]:
            poly_path(c, T, [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])], fill=CREM, stroke=None)
        for m in range(1, E.n):
            poly_path(c, T, E.TREADS[m], fill=WOOD, stroke=INK, width=0.4)
        if P.poteau > 0:
            poly_path(c, T, [(E.PO0x, E.PO0y), (E.PO1x, E.PO0y), (E.PO1x, E.PO1y), (E.PO0x, E.PO1y)], fill=colors.HexColor("#8a5a2b"), stroke=None)
        sw = P.soutien_largeur
        poly_path(c, T, [(0, 0), (sw, 0), (sw, E.WL), (0, E.WL)], stroke=INK, width=0.4, dash=(2, 2))
        poly_path(c, T, [(0, 0), (E.XE, 0), (E.XE, P.tremie_largeur), (0, P.tremie_largeur)], stroke=TRE, width=0.8, dash=(4, 3))
        for m in range(1, E.n):
            t_ = (m-0.5)*E.g; x, y = E.walk(t_)
            if t_ <= E.A1: x -= 12
            elif t_ >= E.A1+E.arc: y -= 12
            else:
                vx, vy = x-E.JR, y-E.JR; d = math.hypot(vx, vy); x = E.JR+vx*(d+12)/d; y = E.JR+vy*(d+12)/d
            text(c, T, x, y, str(m), 7, INK, bold=True)
        text(c, T, E.WR+E.R, E.Y0+12, "départ", 7, MUTED)
        text(c, T, E.XE-20, -8, "arrivée, chevêtre", 7, MUTED)
        text(c, T, E.XE/2, -14, f"{fr(E.XE, 0)} (mur d'arrivée)", 7, DIM)
        text(c, T, -6, E.Y0/2, fr(E.Y0, 0), 7, DIM, anchor="end" if not E.left else "start")
        text(c, T, E.XE*0.6, P.tremie_largeur+6, f"trémie {fr(E.XE, 0)} × {fr(P.tremie_largeur, 0)}", 7, TRE)
        if P.poteau > 0: text(c, T, E.PO1x+3, E.PO1y+5, f"poteau {fr(P.poteau, 0)} × {fr(P.poteau, 0)}", 6.5, MUTED, anchor="start" if not E.left else "end")
    story.append(Fig(world, draw_plan, W, 150*mm))
    story.append(Paragraph("Vue de dessus. En brun clair, les crémaillères (sous les marches) ; en brun foncé, le poteau d'angle ; "
                           "en pointillé noir, le bastaing de soutien ; en pointillé vert, la trémie.", st['small']))

    # --- vue 3D à hauteur d'homme (page paysage)
    story.append(NextPageTemplate('paysage')); story.append(PageBreak())
    story.append(Paragraph("Vue en perspective, à hauteur d'homme", st['h2']))
    WL3 = landscape(A4)[0] - 24*mm
    cam = (E.JR + 210, E.Y0 + 190, 165); tgt = (E.JR*0.55, E.JR*0.35, 125)
    story.append(View3D(E, cam, tgt, WL3, 150*mm))
    story.append(Paragraph("Œil à 1,65 m du sol, dans la pièce, face au départ de l'escalier. Le plancher d'arrivée est figuré en transparence "
                           "autour de la trémie ; les murs et le sol en gris clair.", st['small']))
    story.append(NextPageTemplate('portrait'))
    # --- marches
    story.append(PageBreak()); story.append(Paragraph("Les marches", st['h2']))
    cote = "mur à gauche, jour à droite" if not E.left else "jour à gauche, mur à droite"
    story.append(Paragraph(f"Chaque marche est dessinée vue de dessus, nez en bas ({cote}). Origine : extrémité gauche du nez (point A). "
                           f"X le long du nez vers la droite, Y vers l'arrière. En vert pâle, les zones qui portent sur les crémaillères : "
                           f"c'est là qu'on visse (deux vis par appui, noyées et bouchonnées). Le nez est en rouge.", st['p']))
    cells = []; deb = []
    for m in range(1, E.n):
        Lc, kinds, bands = E.tread_local(m); an = E.angles(Lc)
        xs = [p[0] for p in Lc]; ys = [p[1] for p in Lc]
        deb.append((m, max(xs)-min(xs), max(ys)-min(ys)))
        world = (min(xs)-8, min(ys)-8, max(xs)+8, max(ys)+8)
        def draw_tread(c, T, s, Lc=Lc, kinds=kinds, bands=bands):
            poly_path(c, T, Lc, fill=WOOD, stroke=None)
            for b in bands: poly_path(c, T, b, fill=BAND, stroke=None)
            n_ = len(Lc); ar = area(Lc)
            for i in range(n_):
                a, b = Lc[i], Lc[(i+1) % n_]
                line(c, T, a, b, NEZ if kinds[i] == 'nez' else INK, 1.6 if kinds[i] == 'nez' else 0.6)
            cx = sum(p[0] for p in Lc)/n_; cy = sum(p[1] for p in Lc)/n_
            for i in range(n_):
                a, b = Lc[i], Lc[(i+1) % n_]; L = math.dist(a, b)
                if L >= 6:
                    mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2; dx_, dy_ = (b[0]-a[0])/L, (b[1]-a[1])/L
                    nx, ny = dy_, -dx_
                    if ar < 0: nx, ny = -nx, -ny
                    text(c, T, mx+nx*4, my+ny*4, fr(L), 5.5, DIM)
            for i, p in enumerate(Lc):
                vx, vy = p[0]-cx, p[1]-cy; d = math.hypot(vx, vy) or 1
                a_, b_ = Lc[i-1], Lc[(i+1) % n_]
                if min(math.dist(p, a_), math.dist(p, b_)) >= 2.5:
                    text(c, T, p[0]+vx/d*3.5, p[1]+vy/d*3.5, chr(65+i), 6, INK, bold=True)
        fig = Fig(world, draw_tread, W/2-8*mm, 45*mm)
        rows = [["Point", "X", "Y", "Angle"]] + [[chr(65+i), fr(p[0]), fr(p[1]), fr(an[i])+"°"] for i, p in enumerate(Lc)]
        note = " ".join(E.notes[m])
        cell = [Paragraph(f"Marche {m}  <font size=7 color='#5d6874'>(dessus à {fr(m*E.h)} cm)</font>", st['h3']), fig, Spacer(1, 2),
                tbl(rows, size=6.5), Paragraph(f"Planche mini {math.ceil(max(xs)-min(xs))} × {math.ceil(max(ys)-min(ys))}. {note}", st['small'])]
        cells.append(cell)
    grid = [cells[i:i+2] for i in range(0, len(cells), 2)]
    if len(grid[-1]) == 1: grid[-1].append("")
    for row in grid:
        t = Table([row], colWidths=[W/2, W/2], hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOX', (0, 0), (0, 0), 0.3, RULE),
                               ('BOX', (1, 0), (1, 0), 0.3 if row[1] != "" else 0, RULE),
                               ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                               ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        story.append(t); story.append(Spacer(1, 5))

    # --- crémaillères
    for k in E.CR:
        story.append(PageBreak())
        mir = E.view_mirror(k)
        gauche, droite = (HIGH[k], LOW[k]) if mir else (LOW[k], HIGH[k])
        poly = E.OUT[k]; X = (lambda d: -d) if mir else (lambda d: d)
        story.append(Paragraph(NAMES[k] + " : développé", st['h2']))
        story.append(Paragraph(f"Vue de la face côté marches : {gauche} à gauche, {droite} à droite. Cotes horizontales en développé depuis le nez "
                               f"de la première marche, hauteurs depuis le sol. Gorge mini {fr(E.THR[k], 0)} cm.", st['p']))
        xs = [X(p[0]) for p in poly]; zs = [p[1] for p in poly]
        extra = [X((E.Y0-E.WL)+q[0]-E.WL) for q in E.SUP_POLY] if k == 'mur_arr' else []
        world = (min(xs+extra)-8, min(zs+([0] if k == 'mur_arr' else []))-6, max(xs+extra)+8, max(zs)+10)
        def draw_dev(c, T, s, k=k, poly=poly, X=X, world=world):
            if world[1] < 3: line(c, T, (world[0], 0), (world[2], 0), INK, 1.2)
            if world[3] > E.CHEV-5:
                line(c, T, (world[0], E.CHEV), (world[2], E.CHEV), MUTED, 0.5, (3, 2))
                text(c, T, world[0]+1, E.CHEV+2.5, f"dessous du plancher {fr(E.CHEV, 0)}", 6, MUTED, anchor="start")
            if k == 'mur_arr':
                poly_path(c, T, [(X((E.Y0-E.WL)+q[0]-E.WL), q[1]) for q in E.SUP_POLY], fill=colors.HexColor("#e4d6bd"), stroke=INK, width=0.4, dash=(2, 2))
            poly_path(c, T, [(X(p[0]), p[1]) for p in poly], fill=WOOD, stroke=INK, width=0.7)
            for z, d0, d1 in E.PAL[k]:
                m = round((z+E.EP)/E.h); text(c, T, X((d0+d1)/2), z+2.5, str(m), 6.5, INK, bold=True)
            if k in E.BOLTS:
                d, zz = E.BOLTS[k]
                for z in zz:
                    X0, Y0_ = T(X(d), z); c.setFillColor(NEZ); c.circle(X0, Y0_, 1.6, stroke=0, fill=1)
            if E.ancrage_chevetre(k):
                b = E.CR[k]['rng'][1]
                for z in E.TIGES:
                    line(c, T, (X(b), z), (X(b-E.P.ancrage+2.5), z), NEZ, 1.0, (2, 1.5))
                    X0, Y0_ = T(X(b-E.P.ancrage+2.5), z); c.setFillColor(NEZ); c.rect(X0-1.5, Y0_-2, 3, 4, stroke=0, fill=1)
                line(c, T, (X(b), E.CHEV-4), (X(b), E.P.hauteur+3), MUTED, 0.5, (1, 1))
        story.append(Fig(world, draw_dev, W, 120*mm))
        prow = [["Palier (marche)", "Hauteur du palier", "Début", "Fin"]] + \
               [[str(round((z+E.EP)/E.h)), fr(z), fr(d0), fr(d1)] for z, d0, d1 in E.PAL[k]]
        story.append(Spacer(1, 4)); story.append(tbl(prow, size=7))
        if k in E.BOLTS and E.BOLTS[k][1]:
            story.append(Paragraph(f"Boulons sur le poteau (points rouges) : à {fr(E.BOLTS[k][0])} en développé, à "
                                   f"{' et '.join(fr(z, 0) for z in E.BOLTS[k][1])} cm de hauteur.", st['small']))
        if E.ancrage_chevetre(k):
            story.append(Paragraph(f"En haut, la crémaillère monte jusqu'au plancher fini ({fr(P.hauteur, 0)} cm) sur les {fr(P.ancrage)} derniers "
                                   f"centimètres et vient contre la face du chevêtre. Deux tiges filetées M10 (pointillés rouges) entrent dans son "
                                   f"bout à {' et '.join(fr(z) for z in E.TIGES)} cm de hauteur ; leurs écrous se logent dans deux mortaises "
                                   f"(rectangles rouges) creusées dans la face arrière, à {fr(P.ancrage-2.5)} cm du bout.", st['small']))
        # tracé dans le brut (page paysage)
        story.append(NextPageTemplate('paysage')); story.append(PageBreak())
        WL_ = landscape(A4)[0] - 24*mm
        pts, bolts, Lb, Wb, th = E.board(k)
        story.append(Paragraph(NAMES[k] + " : tracé dans le brut", st['h2']))
        story.append(Paragraph(f"Brut posé à plat, face côté marches visible ({gauche} à gauche, {droite} à droite). Origine : extrémité gauche de la face "
                               f"inférieure du brut ; X le long de cette face, Y perpendiculairement vers le haut. Brut mini {math.ceil(Lb)} × {math.ceil(Wb)} "
                               f"(longueur × largeur). Contrôle : les paliers font {fr(th, 1)}° avec la face inférieure du brut. "
                               f"Les coupes sont d'équerre : le tracé est le même sur les deux faces.", st['p']))
        world = (-6, -6, Lb+6, Wb+6)
        def draw_board(c, T, s, pts=pts, bolts=bolts, Lb=Lb, Wb=Wb, rods=list(E.RODS.get(k, []))):
            poly_path(c, T, [(0, 0), (Lb, 0), (Lb, Wb), (0, Wb)], stroke=MUTED, width=0.5, dash=(3, 2))
            poly_path(c, T, pts, fill=WOOD, stroke=INK, width=0.7)
            for x, y in bolts:
                X0, Y0_ = T(x, y); c.setFillColor(NEZ); c.circle(X0, Y0_, 1.6, stroke=0, fill=1)
            for a_, b_ in rods:
                line(c, T, a_, b_, NEZ, 1.0, (2, 1.5))
            cx = sum(p[0] for p in pts)/len(pts); cy = sum(p[1] for p in pts)/len(pts)
            for i, (x, y) in enumerate(pts):
                vx, vy = x-cx, y-cy; d = math.hypot(vx, vy) or 1
                X0, Y0_ = T(x, y); c.setFillColor(INK); c.circle(X0, Y0_, 0.7, stroke=0, fill=1)
                text(c, T, x+vx/d*2.5, y+vy/d*2.5, str(i+1), 5.5, DIM, bold=True)
            text(c, T, 0, -3.5, "origine (0 ; 0)", 6, MUTED, anchor="start")
            text(c, T, Lb, -3.5, "face inférieure du brut (axe X)", 6, MUTED, anchor="end")
        story.append(Fig(world, draw_board, WL_, 105*mm))
        story.append(Spacer(1, 4))
        rows = [[str(i+1), fr(x), fr(y)] for i, (x, y) in enumerate(pts)]
        story.append(split_cols(rows, 6 if len(rows) > 24 else 4, ["Point", "X", "Y"]))
        if bolts:
            story.append(Spacer(1, 3))
            story.append(Paragraph("Trous de boulons : " + " ; ".join(f"({fr(x)} ; {fr(y)})" for x, y in bolts), st['small']))
        if E.RODS.get(k):
            story.append(Paragraph("Tiges d'ancrage dans le bout (de l'entrée à la mortaise d'écrou) : " +
                                   " ; ".join(f"({fr(a[0])} ; {fr(a[1])}) à ({fr(b_[0])} ; {fr(b_[1])})" for a, b_ in E.RODS[k]), st['small']))
        story.append(NextPageTemplate('portrait'))

    # --- assemblages, soutien, montage, débit
    story.append(PageBreak()); story.append(Paragraph("Assemblages", st['h2']))
    story.append(Paragraph("<b>Angle côté mur.</b> La crémaillère de départ va jusqu'au mur d'arrivée ; la crémaillère d'arrivée vient buter contre sa face. "
                           "Les deux se vissent dans les montants, dont ceux de l'angle, et reposent sur le bastaing de soutien.", st['p']))
    bb = E.BOLTS
    txt = ""
    if bb['int_bas'][1] and bb['int_haut'][1]:
        txt = (f" Boulons M10 : crémaillère basse à {' et '.join(fr(z, 0) for z in bb['int_bas'][1])} cm, crémaillère haute à "
               f"{' et '.join(fr(z, 0) for z in bb['int_haut'][1])} cm de hauteur, pour qu'ils ne se croisent pas dans le poteau.")
    if getattr(E, 'POT_AUTO', False):
        pot_txt = (f" Le poteau monte du sol jusqu'à {fr(E.POT_H)} cm, le dessus des crémaillères à son contact : il ne dépasse pas, "
                   f"et les marches qui passent au-dessus n'ont pas besoin d'être entaillées.")
    else:
        pot_txt = f" Le poteau monte du sol jusqu'à {fr(E.POT_H)} cm ; les marches qu'il traverse sont entaillées à son droit."
    story.append(Paragraph("<b>Angle côté jour.</b> La crémaillère basse descend jusqu'à l'angle ; la crémaillère haute vient buter contre sa face arrière. "
                           "Chacune est boulonnée sur une face du poteau d'angle." + txt + pot_txt, st['p']))
    if E.ancrage_chevetre('int_haut'):
        story.append(Paragraph(f"<b>En haut.</b> La crémaillère intérieure haute monte jusqu'au niveau du plancher fini sur ses {fr(P.ancrage)} derniers "
                               f"centimètres et vient contre la face du chevêtre, entre {fr(E.CHEV)} et {fr(P.hauteur)} cm. Elle y est fixée par deux tiges "
                               f"filetées M10 qui traversent le chevêtre et entrent dans son bout ; les écrous côté crémaillère se logent dans des "
                               f"mortaises creusées dans sa face arrière, à {fr(P.ancrage-2.5)} cm du bout. Les tiges travaillent en cisaillement : c'est "
                               f"un appui franc. La marche {E.n-1} est entaillée à son coin arrière côté jour pour laisser passer la crémaillère. "
                               f"La crémaillère mur d'arrivée s'arrête contre le chevêtre ; elle est portée par les montants du mur.", st['p']))
    elif E.talon_ok_pre():
        story.append(Paragraph(f"<b>En haut.</b> Les deux crémaillères d'arrivée se prolongent de {fr(P.talon)} cm sous le chevêtre (dessus du talon à "
                               f"{fr(E.CHEV)} cm) et se vissent de bas en haut dans le chevêtre, ou par une équerre. Ce talon suppose un chevêtre "
                               f"d'au moins {fr(P.talon, 0)} cm de large.", st['p']))
    else:
        story.append(Paragraph("<b>En haut.</b> Les crémaillères d'arrivée se fixent sur le chevêtre par une platine métallique.", st['p']))
    story.append(Paragraph("<b>En bas.</b> Les pieds des crémaillères de départ, du poteau d'angle et du bastaing de soutien se fixent au sol par équerres.", st['p']))
    story.append(Paragraph("Bastaing de soutien côté mur", st['h2']))
    sw = P.soutien_largeur; sh = max(q[1] for q in E.SUP_POLY)
    z_step = E.SUP_POLY[3][1]; z_end = E.SUP_POLY[2][1]
    if abs(z_step-E.CORNER_Z) > 0.2:
        desc = (f"Dessus horizontal à {fr(E.CORNER_Z)} cm sur les {fr(E.WL)} premiers centimètres, côté angle, sous le bout de la crémaillère "
                f"de départ ; puis redescente à {fr(z_step)} cm et biais jusqu'à {fr(z_end)} cm, sous la crémaillère d'arrivée.")
    else:
        desc = (f"Dessus horizontal à {fr(E.CORNER_Z)} cm sur les {fr(E.WL)} premiers centimètres, côté angle, sous le bout de la crémaillère "
                f"de départ ; puis biais jusqu'à {fr(z_end)} cm sous la crémaillère d'arrivée.")
    story.append(Paragraph(f"Bastaing de {fr(P.ep_cremaillere)} × {fr(sw)} cm plaqué contre le mur d'arrivée dans l'angle. " + desc, st['p']))
    sp = E.SUP_POLY if not E.left else [(sw-q[0], q[1]) for q in E.SUP_POLY]
    def draw_sup(c, T, s):
        poly_path(c, T, sp, fill=WOOD, stroke=INK, width=0.7)
        text(c, T, sw/2, -5, fr(sw), 7, DIM)
        text(c, T, -2 if not E.left else sw+2, E.CORNER_Z/2, fr(E.CORNER_Z), 7, DIM, anchor="end" if not E.left else "start")
        text(c, T, sw+2 if not E.left else -2, z_end/2, fr(z_end), 7, DIM, anchor="start" if not E.left else "end")
        if abs(z_step-E.CORNER_Z) > 0.2:
            xs_ = E.WL if not E.left else sw-E.WL
            text(c, T, xs_+(1 if not E.left else -1), z_step-4, fr(z_step), 6.5, DIM, anchor="start" if not E.left else "end")
    story.append(Fig((-20, -9, sw+20, sh+4), draw_sup, 50*mm, 70*mm))
    story.append(Paragraph("Ordre de montage", st['h2']))
    story.append(Paragraph("1. Poser le bastaing de soutien, puis la crémaillère mur de départ et la crémaillère mur d'arrivée, vissées dans les montants. "
                           "2. Poser le poteau d'angle et les deux crémaillères intérieures, les boulonner, fixer les talons sous le chevêtre et les pieds "
                           "au sol ; vérifier que les paliers sont de niveau d'un côté à l'autre. 3. Poser les marches de bas en haut, collées "
                           "(colle polyuréthane) et vissées par-dessus.", st['p']))
    story.append(CondPageBreak(90*mm))
    story.append(Paragraph("Liste de débit", st['h2']))
    rows = [["Pièce", "Longueur × largeur × épaisseur"]]
    for m, l, w in deb: rows.append([f"Marche {m}", f"{math.ceil(l)} × {math.ceil(w)} × {fr(P.ep_marche)}"])
    for k in E.CR:
        _, _, Lb, Wb, _ = E.board(k); rows.append([NAMES[k], f"{math.ceil(Lb)} × {math.ceil(Wb)} × {fr(P.ep_cremaillere)}"])
    if P.poteau > 0:
        rows.append(["Poteau d'angle", f"{math.ceil(E.POT_H)} × {fr(P.poteau)} × {fr(P.poteau)}"])
    rows.append(["Bastaing de soutien", f"{math.ceil(sh)} × {fr(sw)} × {fr(P.ep_cremaillere)}"])
    rows.append(["Boulons ou tiges filetées M10, avec rondelles (poteau)", "4"])
    if E.ancrage_chevetre('int_haut'):
        rows.append(["Tiges filetées M10 (chevêtre), écrous et rondelles", f"2, longueur {fr(P.ancrage+P.plancher, 0)} cm environ (à ajuster au chevêtre)"])
    story.append(tbl(rows, size=8))
    story.append(Paragraph("Prévoir les surlongueurs d'usinage.", st['small']))

    doc = BaseDocTemplate(path, pagesize=A4, title=f"Escalier quart tournant à {sens}", author="escalier_quart_tournant.py")
    def pt(name, size):
        fw, fh = size
        fr_ = Frame(12*mm, 14*mm, fw-24*mm, fh-26*mm, id=name, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        def on_page(c, d, size=size):
            c.setPageSize(size)
            c.saveState(); c.setFont("Helvetica", 7); c.setFillColor(MUTED)
            c.drawCentredString(size[0]/2, 8*mm, f"Escalier quart tournant à {sens}, page {d.page}")
            c.restoreState()
        return PageTemplate(id=name, frames=[fr_], pagesize=size, onPage=on_page)
    doc.addPageTemplates([pt('portrait', A4), pt('paysage', landscape(A4))])
    doc.build(story)

def main(argv=None):
    P = parse_args(argv)
    try:
        E = Escalier(P)
    except EscalierErreur as e:
        sys.exit(str(e))
    build_pdf(E, P.sortie)
    print(f"{P.sortie} : {E.n} hauteurs de {E.h:.2f} cm, giron {E.g:.2f} cm, 2h+g = {E.blondel:.1f}, "
          f"échappée {E.echappee:.1f} cm")
    for a in E.alertes: print("Attention :", a)

if __name__ == "__main__":
    main()
