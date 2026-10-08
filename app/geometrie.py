#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calcul géométrique de l'escalier quart tournant balancé, marches posées sur crémaillères.

Dépendance : aucune (bibliothèque standard uniquement). Le rendu (PDF, 3D) est dans
app/pdf.py, app/modele3d.py et app/rendu3d.py ; app/escalier.py reste le point d'entrée
en ligne de commande et réexporte ce dont les autres modules ont besoin.

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
import argparse, math


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
    a("--ep-contremarche", type=float, default=0.0, help="épaisseur des contremarches (0 = pas de contremarches)")
    a("--profondeur-rainure", type=float, default=0.8,
      help="profondeur de la rainure creusée dans la face inférieure de la marche du dessus, qui reçoit le haut de la contremarche")
    a("-o", "--sortie", default="escalier_quart_tournant.pdf", help="fichier PDF produit")
    return p.parse_args(argv)

# Jeux de montage des contremarches (posées par en dessous, après coup) : non exposés en paramètres,
# ce sont des tolérances de fabrication plutôt que des choix de conception.
JEU_RAINURE = 0.1   # jeu (cm) sur la largeur de la rainure, pour que le haut du panneau y glisse sans forcer
JEU_LIMON = 0.1     # jeu (cm) de chaque côté du panneau, vis-à-vis des crémaillères (évite le contact chant-contre-limon)
MARGE_PERCAGE = 5.0  # retrait (cm) des pré-perçages par rapport au bord de la marche (place pour la visseuse, sans buter contre la crémaillère)
RECUL_CREMAILLERE = 0.5  # cm, marge au-delà de l'épaisseur de la contremarche (voir contremarches())

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

def add_tab(poly, near_a, near_b, far_a, far_b, tol=1e-3):
    """Insère une languette rectangulaire (near_a -> far_a -> far_b -> near_b) dans le contour
    `poly`, le long du bord qui porte near_a et near_b (doivent être sur le même bord, cas normal
    puisqu'ils proviennent tous deux de la même ligne de clip). `far_a` correspond à `near_a`,
    `far_b` à `near_b`. Si le bord n'est pas trouvé, renvoie `poly` inchangé."""
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i+1) % n]
        dab = math.dist(a, b)
        if dab < 1e-6: continue
        u = ((b[0]-a[0])/dab, (b[1]-a[1])/dab)
        def on_edge(p):
            t = (p[0]-a[0])*u[0] + (p[1]-a[1])*u[1]
            perp = abs((p[0]-a[0])*(-u[1]) + (p[1]-a[1])*u[0])
            return (-tol <= t <= dab+tol and perp < tol), t
        oka, ta = on_edge(near_a); okb, tb = on_edge(near_b)
        if oka and okb:
            ins = [near_a, far_a, far_b, near_b] if ta <= tb else [near_b, far_b, far_a, near_a]
            return poly[:i+1] + ins + poly[i+1:]
    return poly

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
        self.cremailleres()
        self.poteau_hauteur()
        self.marches()
        self.supports()
        self.poteau_entailles()
        self.contremarches()
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

    def base_rect(self):
        """Contour en L du plancher disponible (avant découpe par les lignes de nez)."""
        return [(self.WR, self.WR), (self.XE, self.WR), (self.XE, self.JRa), (self.JRd, self.JRa), (self.JRd, self.Y0), (self.WR, self.Y0)]

    def cut_line(self, p0, nr, off=0.0, rect=None):
        """Segment où le contour `rect` (base_rect par défaut) croise le plan (p0, nr) décalé de off ;
        None si hors du contour."""
        clipped = hp_clip(self.base_rect() if rect is None else rect, p0, nr, off)
        f = lambda p: abs((p[0]-p0[0])*nr[0] + (p[1]-p0[1])*nr[1] - off) < 1e-6
        pts = [p for p in clipped if f(p)]
        if len(pts) < 2: return None
        pts.sort(key=lambda p: p[0]*nr[1] - p[1]*nr[0])
        return pts[0], pts[-1]

    def riser_pair(self, p0, nr, off):
        """Points où la ligne (p0, nr) décalée de `off` croise la face de la crémaillère mur et celle de
        la crémaillère intérieure (jour) réellement présentes à cet endroit (avec la clé de chacune).
        Les quatre crémaillères sont candidates indépendamment (mur_dep comme mur_arr, int_bas comme
        int_haut), chacune validée sur sa propre plage : mur_dep va jusqu'au mur d'arrivée et resterait
        sinon une intersection valide même loin dans le tournant, à la place de mur_arr qui est la vraie
        crémaillère présente à cet endroit."""
        Poff = (p0[0]+nr[0]*off, p0[1]+nr[1]*off)
        D = (-nr[1], nr[0])
        def hit(axis, c):
            if abs(D[axis]) < 1e-9: return None
            t = (c-Poff[axis])/D[axis]
            return (Poff[0]+t*D[0], Poff[1]+t*D[1])
        mur_dep, mur_arr = hit(0, self.WL), hit(1, self.WL)
        int_bas, int_haut = hit(0, self.INx), hit(1, self.INy)
        mur = mur_key = None
        if mur_dep is not None and -1e-6 <= mur_dep[1] <= self.Y0+1e-6: mur, mur_key = mur_dep, 'mur_dep'
        elif mur_arr is not None and self.WL-1e-6 <= mur_arr[0] <= self.XE+1e-6: mur, mur_key = mur_arr, 'mur_arr'
        jour = jour_key = None
        if int_bas is not None and self.INy-1e-6 <= int_bas[1] <= self.Y0+1e-6: jour, jour_key = int_bas, 'int_bas'
        elif int_haut is not None and self.INx-1e-6 <= int_haut[0] <= self.XE+1e-6: jour, jour_key = int_haut, 'int_haut'
        if mur is None or jour is None: return None
        return (mur, mur_key), (jour, jour_key)

    def d_along(self, key, pt):
        """Abscisse développée de pt le long de la crémaillère `key` (même repère que OUT[key])."""
        x, y = pt
        if key == 'mur_dep' or key == 'int_bas': return self.Y0 - y
        if key == 'mur_arr': return x - self.WL + (self.Y0-self.WL)
        return x - self.INx + (self.Y0-self.INy)   # int_haut

    def backed(self, key, pt, z):
        """Vrai si la crémaillère `key` a du bois plein jusqu'à la hauteur z à l'abscisse de pt,
        d'après son propre contour OUT[key] (qui tient compte à la fois de sa face et de son dos
        - voir cremailleres() - contrairement à top_at(pt), qui ignore quelle crémaillère est
        visée et peut être trop optimiste près d'un coin, en particulier tout au début
        d'int_haut/int_bas, juste après le poteau)."""
        return pip((self.d_along(key, pt), z-0.05), self.OUT[key])

    def contremarche_offset(self, i):
        """Décalage (le long de la normale de LINES[i]) auquel poser la contremarche i : au moins
        REC + ep_contremarche + RECUL_CREMAILLERE, reculé davantage si besoin pour que les deux
        crémaillères touchées aient vraiment du bois plein jusqu'en haut du panneau à cet endroit
        (voir `backed` - près d'un coin, l'entaille de la crémaillère peut ne commencer qu'un peu
        plus loin que ce que donnerait la formule simple). None si aucun décalage dans une plage
        raisonnable ne convient (zone trop étroite)."""
        ep = self.P.ep_contremarche
        off = self.REC + ep + RECUL_CREMAILLERE
        p0, nr = self.line_normal(i)
        z_haut = (i+1)*self.h - self.EP if i+1 <= self.n-1 else self.P.hauteur
        for _ in range(100):
            seg = self.riser_pair(p0, nr, off)
            if seg is None: return None
            (mur, mur_key), (jour, jour_key) = seg
            # on teste au point réellement posé (après le jeu latéral, comme dans contremarches()),
            # pas le point brut sur la face : tout près d'un bord de l'entaille, le petit décalage du
            # jeu peut suffire à faire passer le point de l'autre côté de la limite.
            L = math.dist(mur, jour)
            if L > 2*JEU_LIMON + 1:
                ux = ((jour[0]-mur[0])/L, (jour[1]-mur[1])/L)
                mur_t = (mur[0]+ux[0]*JEU_LIMON, mur[1]+ux[1]*JEU_LIMON)
                jour_t = (jour[0]-ux[0]*JEU_LIMON, jour[1]-ux[1]*JEU_LIMON)
                if self.backed(mur_key, mur_t, z_haut) and self.backed(jour_key, jour_t, z_haut):
                    return off
            off += 0.5
        return None

    def tab_ends(self, line_idx, depth0, depth1, jeu):
        """Bouts mur/jour d'une languette rectangulaire entre les deux crémaillères, le long de
        la normale de LINES[line_idx], en profondeur depth0 (bord proche) à depth1 (bord
        éloigné), en retrait de `jeu` de chaque côté par rapport aux faces des deux crémaillères.
        La largeur (mur à jour) n'est déterminée qu'une fois, à depth1 (la profondeur qui doit
        être correctement appuyée - voir contremarche_offset) : le bord proche est le même
        segment, simplement décalé en profondeur (translation le long de la normale), plutôt que
        recalculé indépendamment par une nouvelle intersection avec les crémaillères - près d'un
        coin, celle-ci peut désigner une crémaillère différente à depth0 qu'à depth1 (typiquement
        int_bas puis int_haut), ce qui donnerait une languette qui se croise elle-même. None si
        depth1 n'atteint pas les deux crémaillères."""
        p0, nr = self.line_normal(line_idx)
        seg1 = self.riser_pair(p0, nr, depth1)
        if seg1 is None: return None
        (mur, _), (jour, _) = seg1; L = math.dist(mur, jour)
        if L <= 2*jeu + 1: return None
        ux = ((jour[0]-mur[0])/L, (jour[1]-mur[1])/L)
        far_mur = (mur[0]+ux[0]*jeu, mur[1]+ux[1]*jeu); far_jour = (jour[0]-ux[0]*jeu, jour[1]-ux[1]*jeu)
        dx, dy = nr[0]*(depth0-depth1), nr[1]*(depth0-depth1)
        near_mur = (far_mur[0]+dx, far_mur[1]+dy); near_jour = (far_jour[0]+dx, far_jour[1]+dy)
        return near_mur, near_jour, far_mur, far_jour

    # --- marches
    def marches(self):
        n = self.n; self.TREADS = {}; self.notes = {}
        ep = self.P.ep_contremarche
        for m in range(1, n):
            poly = self.base_rect()
            p0, nr = self.line_normal(m-1); poly = hp_clip(poly, p0, nr, 0)
            p1, nr1 = self.line_normal(m); back = self.REC if m <= n-2 else 0
            poly = clean(hp_clip(poly, p1, (-nr1[0], -nr1[1]), -back))
            note = []
            # languette au-delà du pli de la crémaillère (entre les deux crémaillères uniquement),
            # jusqu'au décalage où la contremarche m sera posée (contremarche_offset) : sans elle,
            # la contremarche n'aurait d'appui plein sur aucune des deux crémaillères, le bois plein
            # ne commençant, côté marche du dessus, qu'à partir de leur pli (voir `backed`).
            if ep > 0 and m <= n-2:
                off = self.contremarche_offset(m)
                if off is None:
                    note.append("Pas assez de place entre les crémaillères pour prolonger la marche sous la contremarche.")
                else:
                    tab = self.tab_ends(m, back, off, JEU_LIMON)
                    if tab is not None:
                        near_mur, near_jour, far_mur, far_jour = tab
                        poly = add_tab(poly, near_mur, near_jour, far_mur, far_jour)
                    else:
                        note.append("Pas assez de place entre les crémaillères pour prolonger la marche sous la contremarche.")
            # marche dont le nez est sur la volée de départ et qui file le long de la crémaillère haute :
            # on l'arrête contre le poteau - mais seulement si le poteau porte encore à cette hauteur
            # (son dessus, self.POT_H, peut être plus bas que le dessus de cette marche : au-delà,
            # rien ne justifie plus la limite, et la couper là tronquerait la languette ajoutée
            # ci-dessus pour la contremarche sans aucun appui supplémentaire en contrepartie).
            if (self.jour_hit(m-1)[0] == 'depart' and m*self.h <= self.POT_H + 1e-6
                    and max(q[0] for q in poly) > self.PO1x+1e-6):
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
    def poteau_hauteur(self):
        """Hauteur du poteau (self.POT_H) : ne dépend que des crémaillères (cremailleres()), pas
        des marches - calculée à part et avant marches() pour que celle-ci sache déjà jusqu'où le
        poteau porte (languette des contremarches : la limite à sa face n'a plus lieu d'être
        au-dessus de lui)."""
        P = self.P; self.POT_H = 0.0
        if P.poteau <= 0: return
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

    def poteau_entailles(self):
        if self.P.poteau <= 0: return
        def overlap(poly):
            cp = poly
            for p0, nrm in (((self.PO0x, 0), (1, 0)), ((self.PO1x, 0), (-1, 0)), ((0, self.PO0y), (0, 1)), ((0, self.PO1y), (0, -1))):
                cp = hp_clip(cp, p0, nrm)
                if len(cp) < 3: return False
            return abs(area(cp)) > 0.05
        # entailles : seulement les marches dont le dessous est plus bas que le haut du poteau
        for m, poly in self.TREADS.items():
            if not overlap(poly): continue
            under = m*self.h - self.EP
            if under < self.POT_H - 0.05:
                self.TREADS[m] = minus_rect(poly, self.PO0x, self.PO1x, self.PO0y, self.PO1y)
                self.notes[m].append("Entaille au droit du poteau.")
            elif under < self.POT_H + 0.5:
                self.notes[m].append("Repose en partie sur le dessus du poteau.")

    # --- contremarches
    @staticmethod
    def hole_positions(L):
        """Pré-perçages d'un segment de longueur L : deux en retrait de MARGE_PERCAGE des bouts, plus
        un au milieu (la pointe des chaussures tape souvent le milieu de la contremarche) si la place
        ne le fait pas trop se rapprocher des deux autres ; un seul au centre si le segment est trop
        court même pour les deux extrêmes."""
        if L <= 2*MARGE_PERCAGE + 2: return [L/2]
        pts = [MARGE_PERCAGE, L-MARGE_PERCAGE]
        if L/2 - MARGE_PERCAGE > MARGE_PERCAGE/2: pts.insert(1, L/2)
        return pts

    def contremarches(self):
        """Panneaux de contremarches : self.RISERS[i] relie le niveau i (0 = sol) au niveau i+1
        (n = chevêtre), pour i = 0..n-1. Chaque contremarche reprend la ligne de nez LINES[i],
        reculée au-delà du pli des deux crémaillères qu'elle touche (voir contremarche_offset -
        au pli exact, le bois plein ne commence, côté marche du dessus, qu'à partir de ce pli,
        rien devant sur toute l'épaisseur du panneau si on le pose dessus), posée sur la languette
        ajoutée à la marche du dessous (marches()), avec un jeu latéral par rapport aux deux
        crémaillères plutôt qu'en butée dessus (elles ne sont pas forcément parallèles entre elles
        dans le tournant, et près d'un coin leur entaille peut ne commencer qu'un peu plus loin que
        la formule simple - d'où la recherche faite par contremarche_offset). Le poteau d'angle,
        plus loin derrière les crémaillères intérieures, n'est jamais atteint."""
        P = self.P; self.RISERS = {}
        if P.ep_contremarche <= 0: return
        if P.profondeur_rainure > 0.5*P.ep_marche:
            self.alertes.append(f"Profondeur de rainure de {fr(P.profondeur_rainure)} cm : plus de la moitié de l'épaisseur de marche "
                                f"({fr(P.ep_marche)} cm), affaiblit trop la marche.")
        n = self.n
        ep = P.ep_contremarche
        for i in range(n):
            if i <= n-2:
                back = self.contremarche_offset(i)
                if back is None: continue
            else:
                back = 0.0
            p0, nr = self.line_normal(i)
            seg = self.riser_pair(p0, nr, back)
            if seg is None: continue
            (mur, _), (jour, _) = seg
            a, b = mur, jour; L = math.dist(a, b)
            if L <= 2*JEU_LIMON + 1: continue
            ux = ((b[0]-a[0])/L, (b[1]-a[1])/L)
            a = (a[0]+ux[0]*JEU_LIMON, a[1]+ux[1]*JEU_LIMON); b = (b[0]-ux[0]*JEU_LIMON, b[1]-ux[1]*JEU_LIMON)
            z_bas = i*self.h if i >= 1 else 0.0
            z_haut = (i+1)*self.h - self.EP if i+1 <= n-1 else self.P.hauteur
            self.RISERS[i] = dict(a=a, b=b, z_bas=z_bas, z_haut=z_haut,
                                  rainure=(1 <= i <= n-2), percage=(i >= 1))
        missing = [i for i in range(n) if i not in self.RISERS]
        if missing:
            self.alertes.append(f"Contremarche(s) {', '.join(str(i) for i in missing)} non calculée(s) "
                                "(zone trop étroite près du tournant).")

    def riser_local(self, i):
        """Contremarche i vue de face côté escalier : largeur, hauteur visible, hauteur totale
        (avec la partie engagée dans la rainure), et pré-perçages (distances depuis le bord
        gauche)."""
        r = self.RISERS[i]; a, b = r['a'], r['b']
        wallpt = self.LINES[i][1]
        if math.dist(b, wallpt) < math.dist(a, wallpt): a, b = b, a
        L = math.dist(a, b); H = r['z_haut']-r['z_bas']
        Htot = H + (self.P.profondeur_rainure if r['rainure'] else 0.0)
        holes = self.hole_positions(L) if r['percage'] else []
        if self.left: holes = [L-x for x in holes]
        return L, H, Htot, holes

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
        X le long du nez vers la droite, Y vers l'arrière. Renvoie (points, types d'arêtes, zones d'appui,
        rainure de la contremarche du dessous (rectangle local ou None), pré-perçages de la contremarche
        du dessus (liste de points locaux))."""
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
        groove = None; holes = []
        if self.P.ep_contremarche > 0:
            rb = self.RISERS.get(m-1)
            if rb is not None and rb['rainure']:
                ax, ay = tf(rb['a']); bx, by = tf(rb['b'])
                hw = (self.P.ep_contremarche + JEU_RAINURE)/2
                x0, x1 = (ax, bx) if ax <= bx else (bx, ax)
                # borné à la largeur réelle du nez : la contremarche du dessous peut être un peu plus
                # large que ce nez dans le tournant (lignes de nez successives non parallèles)
                x0 = max(x0, 0.0); x1 = min(x1, L)
                if x1 > x0: groove = [(x0, ay-hw), (x1, ay-hw), (x1, ay+hw), (x0, ay+hw)]
            ra = self.RISERS.get(m)
            if ra is not None:
                La = math.dist(ra['a'], ra['b'])
                for off in self.hole_positions(La):
                    t = off/La
                    wp = (ra['a'][0]+(ra['b'][0]-ra['a'][0])*t, ra['a'][1]+(ra['b'][1]-ra['a'][1])*t)
                    hx, hy = tf(wp)
                    holes.append((min(max(hx, 0.0), L), hy))
        if self.left:
            # miroir : l'extrémité gauche du nez est alors côté jour
            xs_nose = [pts[i][0] for i in range(n_) if self.on_line(P_[i], m-1)]
            xm = max(xs_nose)
            mir = lambda p: (xm-p[0], p[1])
            pts = [mir(p) for p in pts]; bands = [[mir(p) for p in b] for b in bands]
            if groove is not None: groove = [mir(p) for p in groove]
            holes = [mir(p) for p in holes]
            # renuméroter : départ au nouveau point d'origine (0,0), sens trigonométrique
            pts = pts[::-1]; kinds = kinds[::-1]
            kinds = kinds[1:] + kinds[:1]
            i0 = min(range(n_), key=lambda i: math.hypot(*pts[i]))
            pts = pts[i0:] + pts[:i0]; kinds = kinds[i0:] + kinds[:i0]
        return pts, kinds, bands, groove, holes

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

