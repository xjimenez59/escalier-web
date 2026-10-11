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
POINTE_MINI = 1.0   # cm : en dessous, la pointe du nez côté jour n'est pas recoupée (trait de scie pour rien)

def fpt(p, d=2):
    return f"({fr(p[0], d)} ; {fr(p[1], d)})"

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

class Cremaillere:
    """Une crémaillère vue en plan. Sa face côté marches est la droite où la coordonnée d'indice
    `axe` vaut `face` (0 : x constant, 1 : y constant) ; l'autre coordonnée suit le développé d :
    vref + sens*(d - dref). `dos` est la coordonnée fixe de son autre côté (limite de la zone
    échantillonnée pour son profil, voir cremailleres()) ; `rng` la plage de développé qu'elle
    couvre réellement."""
    def __init__(self, axe, face, dos, vref, dref, sens, rng):
        self.axe, self.face_c, self.dos_c = axe, face, dos
        self.vref, self.dref, self.sens, self.rng = vref, dref, sens, rng
        self.dir = (0.0, float(sens)) if axe == 0 else (float(sens), 0.0)

    def _pt(self, c, d):
        v = self.vref + self.sens*(d - self.dref)
        return (c, v) if self.axe == 0 else (v, c)

    def face(self, d): return self._pt(self.face_c, d)
    def back(self, d): return self._pt(self.dos_c, d)

    def d_of(self, pt):
        """Développé d'un point (seule sa coordonnée variable compte)."""
        return self.dref + (pt[1-self.axe] - self.vref)*self.sens

    def avec_fixe(self, pt, valeur):
        """`pt` avec sa coordonnée fixe (celle de la face) remplacée par `valeur`."""
        p = list(pt); p[self.axe] = valeur
        return tuple(p)

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

    def backed(self, key, pt, z):
        """Vrai si la crémaillère `key` a du bois plein jusqu'à la hauteur z au droit de pt,
        d'après son propre contour OUT[key] (plus sûr que top_at près d'un coin)."""
        return pip((self.CR[key].d_of(pt), z-0.05), self.OUT[key])

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
            # test au point réellement posé, après le jeu latéral (comme dans contremarches())
            L = math.dist(mur, jour)
            if L > 2*JEU_LIMON + 1:
                ux = ((jour[0]-mur[0])/L, (jour[1]-mur[1])/L)
                mur_t = (mur[0]+ux[0]*JEU_LIMON, mur[1]+ux[1]*JEU_LIMON)
                jour_t = (jour[0]-ux[0]*JEU_LIMON, jour[1]-ux[1]*JEU_LIMON)
                if self.backed(mur_key, mur_t, z_haut) and self.backed(jour_key, jour_t, z_haut):
                    return off
            off += 0.5
        return None

    def montee(self, key, d_from, d_to, z, palier_requis=False):
        """Développé, entre d_from et d_to, de la première arête montante de `key` pour une marche
        posée à la hauteur z : fin du dernier palier pas plus haut que z, juste avant le premier
        palier plus haut (d_from si la crémaillère est déjà plus haute dès d_from). Avec
        `palier_requis` (crémaillère abordée après avoir tourné au coin), seul un palier à la
        hauteur z compte : si elle n'en a pas, elle ne porte pas la marche, qui s'arrête à d_from.
        None si elle ne remonte pas dans cet intervalle."""
        prev = None
        for zp, d0, d1 in self.PAL[key]:
            if zp > z + 1e-6:
                if prev is None: d = d_from if palier_requis else max(d_from, d0)
                else: d = max(d_from, prev)
                return d if d <= d_to + 1e-9 else None
            if not palier_requis or abs(zp - z) < 1e-6: prev = d1
        return None

    def prof_disponible(self, key, p0, z, prof):
        """Profondeur de languette possible depuis `p0`, le long de la face de `key` (sens du
        développé), à la hauteur z : `prof` si le bois de la crémaillère est plein à cette
        distance (`backed`), sinon la plus grande distance qui l'est. En pratique le profil
        continue de monter au-delà du pli et `prof` passe ; seule la fin réelle d'une crémaillère
        peut limiter."""
        fd = self.CR[key].dir
        def pt(d): return (p0[0]+fd[0]*d, p0[1]+fd[1]*d)
        if self.backed(key, pt(prof), z): return prof
        if not self.backed(key, pt(0.0), z): return 0.0
        lo, hi = 0.0, prof
        for _ in range(30):
            mid = (lo+hi)/2
            if self.backed(key, pt(mid), z): lo = mid
            else: hi = mid
        return lo

    def languette_contremarche(self, p3, p4, p5, p6, jour_key, mur_key, ep, z):
        """Points 4a, 4b, 4c, 4d de la languette de contremarche, qui remplace la droite 4->5
        (CONCEPTION.md, « Languette de contremarche ») : 4a à JEU_LIMON au-delà de 4 dans l'axe
        3->4, 4d de même au-delà de 5 dans l'axe 6->5 ; 4a->4b le long de la face de la crémaillère
        jour et 4d->4c le long de celle de la crémaillère mur, chacun sur ep + RECUL_CREMAILLERE
        (prof_disponible, indépendamment) ; 4b et 4c reliés directement. None si les deux
        crémaillères sont trop proches."""
        L = math.dist(p4, p5)
        if L <= 2*JEU_LIMON + 1: return None
        d34 = math.dist(p3, p4); d65 = math.dist(p6, p5)
        if d34 < 1e-6 or d65 < 1e-6: return None
        dir34 = ((p4[0]-p3[0])/d34, (p4[1]-p3[1])/d34)
        dir65 = ((p5[0]-p6[0])/d65, (p5[1]-p6[1])/d65)
        fd_jour = self.CR[jour_key].dir
        fd_mur = self.CR[mur_key].dir
        prof = ep + RECUL_CREMAILLERE
        p4a = (p4[0]+dir34[0]*JEU_LIMON, p4[1]+dir34[1]*JEU_LIMON)
        p4d = (p5[0]+dir65[0]*JEU_LIMON, p5[1]+dir65[1]*JEU_LIMON)
        prof_jour = self.prof_disponible(jour_key, p4a, z, prof)
        prof_mur = self.prof_disponible(mur_key, p4d, z, prof)
        p4b = (p4a[0]+fd_jour[0]*prof_jour, p4a[1]+fd_jour[1]*prof_jour)
        p4c = (p4d[0]+fd_mur[0]*prof_mur, p4d[1]+fd_mur[1]*prof_mur)
        return p4a, p4b, p4c, p4d

    def parcours(self, m, cote, depart, trace=None):
        """Parcours d'un côté ('jour' ou 'mur') de la marche m depuis le bout de son nez `depart`
        (point 2 côté jour, point 1 côté mur) - CONCEPTION.md, « Bord arrière des marches ».

        Suit l'arête extérieure de la crémaillère de la volée de départ (A), tout droit tant
        qu'elle se poursuit, jusqu'à sa première arête montante ; si elle n'en a pas jusqu'à sa
        fin, tourne au coin et suit celle de la volée d'arrivée (B) jusqu'à la sienne (ou jusqu'à
        son bout pour la dernière marche). Traverse alors l'épaisseur jusqu'à l'arête intérieure.
        Si A remonte dans la bande où B est collée contre elle (carré du coin), la marche porte sur
        les deux : le contour suit aussi B jusqu'à sa remontée (double contact). Le parcours se fait
        sur les arêtes réelles ; les points sont reportés sur les mêmes arêtes décalées du débord
        (jour) ou du jeu (mur).

        Renvoie (chemin, p_ext, p_int, cle) : `chemin`, les sommets du contour après le bout du nez
        jusqu'au point d'où part la droite (ou la languette) vers l'autre côté ; (p_ext, p_int,
        cle), les points 3 et 4 (ou 6 et 5) qui précèdent cette droite et leur crémaillère, qui
        porte la languette de contremarche. `trace` : liste complétée par une description du
        parcours, pour la mise au point."""
        z = m*self.h - self.EP
        B_ = self.BORDS[cote]
        (kA, cA, oA), (kB, cB, oB) = B_['A'], B_['B']
        crA, crB = self.CR[kA], self.CR[kB]
        coin = crA.avec_fixe((oB, oB), oA)          # coin du L décalé (oA, oB) quel que soit l'axe de A
        say = trace.append if trace is not None else (lambda t: None)

        def point_A(d):                              # arête montante sur A : (extérieur décalé, intérieur)
            q = crA.face(d); return crA.avec_fixe(q, oA), q

        def suit_B(d_from, requis):
            d = self.montee(kB, d_from, crB.rng[1], z, palier_requis=requis)
            if d is None:
                d = crB.rng[1]; say(f"  {kB} : pas d'arête montante, bout de la crémaillère (d = {fr(d, 2)})")
            else:
                say(f"  {kB} : arête montante en d = {fr(d, 2)} (tout droit depuis d = {fr(d_from, 2)})")
            q = crB.face(d); pe = crB.avec_fixe(q, oB)
            say(f"  point sur l'arête extérieure {fpt(pe)}, traversée de l'épaisseur -> {fpt(q)}")
            return pe, q

        sur_A = abs(depart[crA.axe] - oA) < 1e-6 and depart[1-crA.axe] >= coin[1-crA.axe] - 1e-6
        say(f"Côté {cote}, départ {fpt(depart)} sur l'arête extérieure de {kA if sur_A else kB} (hauteur z = {fr(z, 2)})")
        if not sur_A:
            pe, q = suit_B(max(crB.d_of(depart), crB.rng[0]), False)
            return [pe, q], pe, q, kB
        d_from = max(crA.d_of(depart), crA.rng[0])
        d_carre = crA.d_of(crA.avec_fixe((B_['carre'], B_['carre']), cA))
        d = self.montee(kA, d_from, crA.rng[1], z)
        if d is not None and d <= d_carre + 1e-9:
            pe, q = point_A(d)
            say(f"  {kA} : arête montante en d = {fr(d, 2)} (tout droit depuis d = {fr(d_from, 2)})")
            say(f"  point sur l'arête extérieure {fpt(pe)}, traversée de l'épaisseur -> {fpt(q)}")
            return [pe, q], pe, q, kA
        if d is None:
            say(f"  {kA} : pas d'arête montante jusqu'au bout de la crémaillère (d = {fr(d_from, 2)} à "
                f"{fr(crA.rng[1], 2)}) -> on tourne au coin {fpt(coin)}")
            pe, q = suit_B(crB.rng[0], True)
            return [coin, pe, q], pe, q, kB
        say(f"  {kA} : arête montante en d = {fr(d, 2)}, dans le carré du coin où {kB} est collée "
            f"(au-delà de d = {fr(d_carre, 2)}) -> double contact")
        pa_e, pa_i = point_A(d)
        if B_['contre'] == 'ext':
            # B collée à la face extérieure de A : on contourne par le coin du L, on suit B, puis on
            # revient le long de la jonction des deux jusqu'à la remontée de A
            say(f"  on tourne au coin {fpt(coin)} et on suit {kB}")
            pe, q = suit_B(crB.rng[0], True)
            seam = [crB.face(crB.rng[0]), crA.avec_fixe(pa_i, cA), pa_i]
            say(f"  retour le long de la jonction : {' ; '.join(fpt(v) for v in seam)}")
            return [coin, pe, q] + seam, seam[1], pa_i, kA
        # B collée à la face intérieure de A : remontée de A, puis le long de la jonction jusqu'à
        # l'arête extérieure de B, qu'on suit jusqu'à sa remontée
        say(f"  point sur l'arête extérieure {fpt(pa_e)}, traversée de l'épaisseur -> {fpt(pa_i)}, "
            f"puis le long de la jonction avec {kB}")
        jonction = crA.avec_fixe(crB.avec_fixe(pa_i, oB), crA.face_c)
        pe, q = suit_B(crB.rng[0], True)
        return [pa_e, pa_i, jonction, pe, q], pe, q, kB

    def contour_marche(self, m, trace=None):
        """Contour de la marche m (CONCEPTION.md, « Bord arrière des marches »), sa languette
        de contremarche (points 4a..4d, ou None) et les crémaillères qui la portent (mur, jour) : nez de 1 à 2, parcours côté jour jusqu'aux
        points 3 et 4, languette ou droite directe jusqu'au point 5, parcours côté mur à rebours
        par le point 6 jusqu'au point 1."""
        jour_nez, mur_nez = self.LINES[m-1]
        cj, p3, p4, kj = self.parcours(m, 'jour', jour_nez, trace)
        bout = self.pointe_jour(m, mur_nez, jour_nez, cj[0], trace)
        cm, p6, p5, km = self.parcours(m, 'mur', mur_nez, trace)
        lang = None
        if self.P.ep_contremarche > 0 and m <= self.n-2:
            lang = self.languette_contremarche(p3, p4, p5, p6, kj, km, self.P.ep_contremarche, m*self.h - self.EP)
        if trace is not None:
            trace.append("Points : " + " ; ".join(f"{i} = {fpt(p)}" for i, p in
                                                  ((1, mur_nez), (2, jour_nez), (3, p3), (4, p4), (5, p5), (6, p6))))
        return clean([mur_nez] + bout + cj + (list(lang) if lang else []) + cm[::-1]), lang, (km, kj)

    def pointe_jour(self, m, p1, p2, suivant, trace=None):
        """Bout du nez côté jour (point 2), recoupé si besoin : la marche ne dépasse pas de plus que
        le recouvrement la face avant de la crémaillère jour qui la porte (début de son palier), en
        mesurant le long de cette crémaillère. Un nez très oblique (marches balancées d'un
        escalier raide) formerait sinon une pointe bien plus longue. Coupe d'équerre, parallèle à
        cette face, et seulement au-delà de POINTE_MINI. Renvoie les points qui remplacent le point 2 : [p2], ou [T, U] (T sur la ligne
        de nez, U sur le bord côté jour) ; `suivant` est le sommet qui suit le point 2 sur ce bord."""
        B_ = self.BORDS['jour']; (kA, _, oA), (kB, _, oB) = B_['A'], B_['B']
        crA = self.CR[kA]
        k, o = (kA, oA) if abs(p2[crA.axe] - oA) < 1e-6 and p2[1-crA.axe] >= oB - 1e-6 else (kB, oB)
        cr = self.CR[k]; z = m*self.h - self.EP
        seg = next((sg for sg in self.PAL[k] if abs(sg[0] - z) < 1e-6), None)
        if seg is None: return [p2]
        d_cut = seg[1] - self.REC
        d1, d2 = cr.d_of(p1), cr.d_of(p2)
        if d2 >= d_cut - POINTE_MINI or cr.d_of(suivant) < d_cut or d1 <= d_cut: return [p2]
        t = (d_cut - d2)/(d1 - d2)
        T = (p2[0] + t*(p1[0]-p2[0]), p2[1] + t*(p1[1]-p2[1]))
        U = cr.avec_fixe(cr.face(d_cut), o)
        if trace is not None:
            trace.append(f"Pointe côté jour recoupée : le nez dépassait de {fr(d_cut-d2, 1)} cm de plus que le recouvrement "
                         f"la face avant de {k} ; coupe de {fpt(T)} à {fpt(U)}")
        return [T, U]

    def trace_marche(self, m):
        """Description pas à pas du calcul du contour de la marche m (mise au point)."""
        t = []; self.contour_marche(m, t)
        return "\n".join(t)

    # --- marches
    def marches(self):
        n = self.n; self.TREADS = {}; self.notes = {}; self.LANG = {}; self.LANG_CLES = {}
        ep = self.P.ep_contremarche
        for m in range(1, n):
            poly, lang, cles = self.contour_marche(m)
            note = []
            if lang is not None: self.LANG[m] = lang; self.LANG_CLES[m] = cles
            elif ep > 0 and m <= n-2:
                note.append("Pas assez de place entre les crémaillères pour prolonger la marche sous la contremarche.")
            # marche dont le nez est sur la volée de départ et qui longe la crémaillère haute :
            # arrêtée contre le poteau, tant que celui-ci monte jusqu'à elle (POT_H)
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
        WR = self.WR
        self.CR = {
            'mur_dep': Cremaillere(0, WL, WR+1e-3, Y0, 0, -1, (0, Y0)),
            'mur_arr': Cremaillere(1, WL, WR+1e-3, WL, Y0-WL, 1, (Y0-WL, Y0-WL+XE-WL)),
            'int_bas': Cremaillere(0, INx, JXx-1e-3, Y0, 0, -1, (0, Y0-INy)),
            'int_haut': Cremaillere(1, INy, JXy-1e-3, INx, Y0-INy, 1, (Y0-INy+TH, Y0-INy+XE-INx)),
        }
        # bords parcourus par le tracé des marches (CONCEPTION.md, « Bord arrière des marches ») : pour
        # chaque côté, la crémaillère de la volée de départ (A) puis celle de la volée d'arrivée (B),
        # chacune avec la coordonnée fixe de son arête extérieure réelle et celle de cette arête
        # décalée du débord (jour) ou du jeu (mur) ; la face de A contre laquelle B est collée
        # ('ext' côté jour, 'int' côté mur) et la coordonnée, le long de A, où commence la bande
        # de B (le « carré du coin », où la marche peut toucher les deux).
        self.BORDS = {'jour': dict(A=('int_bas', JXx, self.JRd), B=('int_haut', JXy, self.JRa), contre='ext', carre=JXy),
                      'mur': dict(A=('mur_dep', 0.0, WR), B=('mur_arr', 0.0, WR), contre='int', carre=WL)}
        self.THR = {'mur_dep': self.P.gorge_mur, 'mur_arr': self.P.gorge_mur, 'int_bas': self.P.gorge_jour, 'int_haut': self.P.gorge_jour}
        self.PAL = {}
        for k, c in self.CR.items():
            a, b = c.rng; prof = []
            for d in frange(a, b, 0.05):
                zs = [z for z in (self.top_at(c.face(d)), self.top_at(c.back(d))) if z is not None]
                prof.append((d, min(zs) if zs else None))
            self.PAL[k] = self.steps(prof)
        self.ecreter_bouts()
        noms = {'mur_dep': "mur de départ", 'mur_arr': "mur d'arrivée", 'int_bas': "intérieure basse",
                'int_haut': "intérieure haute"}
        for k, pal in self.PAL.items():
            for (z0, _, _), (z1, _, _) in zip(pal, pal[1:]):
                if z1 - z0 > self.h + 1e-6:
                    sautees = [m for m in range(1, self.n) if z0 + 1e-6 < m*self.h - self.EP < z1 - 1e-6]
                    self.alertes.append(
                        f"Crémaillère {noms[k]} : aucun palier pour la marche {', '.join(map(str, sautees))} (sa ligne "
                        "de nez longe la crémaillère de trop près) ; un vide reste entre les marches voisines. "
                        "Revoir le balancement ou les longueurs.")
        bd = self.bottom_line('mur_dep'); ba = self.bottom_line('mur_arr')
        self.CORNER_Z = min(interp(bd, Y0-WL), ba[0][1])
        self.OUT = {k: self.outline(k) for k in self.CR}
        self.STRIP = {}
        if self.P.rive_basse == "droite":
            self.rives_droites()
        last_top = (self.n-1)*self.h - self.EP
        self.talon_ok = last_top <= self.CHEV + 1e-6
        if not self.talon_ok and self.P.fixation_haut == "talon":
            self.alertes.append("Le dernier palier est plus haut que le dessous du chevêtre : le talon d'appui est impossible, "
                                "prévoir une platine métallique.")

    def ecreter_bouts(self):
        """Supprime le dernier palier d'une crémaillère de départ quand il est entièrement dans le
        carré du coin (la bande où la crémaillère d'arrivée est collée contre elle) et que la
        crémaillère d'arrivée porte déjà la marche précédente et celle de ce palier : ce bout de
        palier n'apporterait presque rien à sa marche et forcerait la précédente à le contourner. La
        crémaillère finit alors au niveau de la marche précédente (CONCEPTION.md, « Bord arrière
        des marches »)."""
        self.ECRETE = {}
        for cote, B_ in self.BORDS.items():
            (kA, cA, _), (kB, _, _) = B_['A'], B_['B']
            crA = self.CR[kA]; pal = self.PAL[kA]
            if len(pal) < 2: continue
            (z0, a0, b0), (z1, a1, b1) = pal[-2], pal[-1]
            d_carre = crA.d_of(crA.avec_fixe((B_['carre'], B_['carre']), cA))
            niveaux_B = [z for z, _, _ in self.PAL[kB]]
            if (a1 >= d_carre - 1e-6 and abs(b1 - crA.rng[1]) < 0.1 and abs(z1 - z0 - self.h) < 1e-6
                    and all(any(abs(z - zz) < 1e-6 for z in niveaux_B) for zz in (z0, z1))):
                self.PAL[kA] = pal[:-2] + [(z0, a0, b1)]
                self.ECRETE[kA] = (z1, a1, b1)

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
        pal = self.PAL[k]; a, b = self.CR[k].rng
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
            pal = self.PAL[k]; a, b = self.CR[k].rng; zb = ZB[k]
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
        b = self.CR[k].rng[1]; La = self.P.ancrage
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
        """Hauteur du poteau (self.POT_H) : ne dépend que des crémaillères, d'où son calcul avant
        marches(), qui en a besoin pour savoir jusqu'où arrêter les marches contre le poteau."""
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
        """Panneaux de contremarche : RISERS[i] relie le niveau i (0 = sol) au niveau i+1 (n =
        chevêtre). Pour i = 1..n-2, posé sur la languette de la marche i (LANG[i] : sa face arrière
        sur la droite 4c-4b) ; sinon (sol, chevêtre, marche sans languette), face arrière cherchée le
        long de la ligne de nez LINES[i] (contremarche_offset). Les bouts sont ensuite calculés par
        `bouts_contremarche`, d'après les coins avant (face visible quand on monte)."""
        P = self.P; self.RISERS = {}
        if P.ep_contremarche <= 0: return
        if P.profondeur_rainure > 0.5*P.ep_marche:
            self.alertes.append(f"Profondeur de rainure de {fr(P.profondeur_rainure)} cm : plus de la moitié de l'épaisseur de marche "
                                f"({fr(P.ep_marche)} cm), affaiblit trop la marche.")
        n = self.n
        for i in range(n):
            if i in self.LANG:
                _, b, a, _ = self.LANG[i]   # 4b (jour), 4c (mur) : face arrière
                km, kj = self.LANG_CLES[i]
            else:
                back = self.contremarche_offset(i) if i <= n-2 else 0.0
                if back is None: continue
                p0, nr = self.line_normal(i)
                seg = self.riser_pair(p0, nr, back)
                if seg is None: continue
                (a, km), (b, kj) = seg
            if math.dist(a, b) <= 2*JEU_LIMON + 1: continue
            bouts = self.bouts_contremarche(a, b, km, kj, i*self.h - self.EP)
            if bouts is None: continue
            z_bas = i*self.h if i >= 1 else 0.0
            z_haut = (i+1)*self.h - self.EP if i+1 <= n-1 else self.P.hauteur
            self.RISERS[i] = dict(bouts, cle_mur=km, cle_jour=kj, z_bas=z_bas, z_haut=z_haut,
                                  rainure=(1 <= i <= n-2), percage=(i >= 1))
        missing = [i for i in range(n) if i not in self.RISERS]
        if missing:
            self.alertes.append(f"Contremarche(s) {', '.join(str(i) for i in missing)} non calculée(s) "
                                "(zone trop étroite près du tournant).")

    def bouts_contremarche(self, a, b, km, kj, z):
        """Bouts d'une contremarche dont la face arrière est sur la droite a (côté mur) - b (côté
        jour), la face avant (visible quand on monte) à ep_contremarche devant, posée sur une
        marche à la hauteur z (CONCEPTION.md, « Contremarches »). Les deux coins avant sont au jeu (JEU_LIMON) de la face de leur
        crémaillère, ou de la coupe de son pli quand le panneau la longe presque (avant le pli, la
        crémaillère est sous la marche, donc sous le panneau). À chaque bout, un bout d'équerre convient si le coin arrière reste alors hors
        du bois ; sinon le bout est biseauté sur la face arrière, de l'angle de biais du panneau,
        son coin arrière étant lui aussi au jeu. Le plus souvent un seul bout, parfois aucun ; les
        deux seulement entre deux crémaillères perpendiculaires qui se rapprochent vers l'avant.
        Renvoie a, b (coins arrière), fa, fb (coins avant), biseau_a, biseau_b (degrés, 0 si
        d'équerre) et les pré-perçages (`trous`, en plan, au milieu de l'épaisseur ; `trous_x`,
        distances depuis le coin avant côté mur), ou None si le panneau est parallèle à une face."""
        ep = self.P.ep_contremarche
        L = math.dist(a, b); u = ((b[0]-a[0])/L, (b[1]-a[1])/L); nv = (-u[1], u[0])
        av = (a[0]+nv[0]*ep, a[1]+nv[1]*ep)

        def bois(p0, k):
            """Intervalle des abscisses t (le long de u, depuis p0) où la droite p0 + t·u est dans le
            bois de la crémaillère `k` à hauteur du panneau, jeu compris : au-delà de sa face et
            au-delà de son pli (là où elle remonte vers la marche du dessus ; en deçà, elle est sous
            la marche du dessous, donc sous le panneau)."""
            cr = self.CR[k]
            s_ = -1 if k in ('mur_dep', 'mur_arr') else 1      # bois du côté des coordonnées < ou > la face
            conds = [(s_*u[cr.axe], s_*(p0[cr.axe] - cr.face_c) + JEU_LIMON)]
            d_pli = self.montee(k, cr.rng[0], cr.rng[1], z)
            if d_pli is not None:
                conds.append((cr.sens*u[1-cr.axe], cr.d_of(p0) - d_pli + JEU_LIMON))
            def intervalle(cs):
                lo, hi = -math.inf, math.inf
                for beta, alpha in cs:                          # alpha + beta·t >= 0
                    if abs(beta) < 1e-12:
                        if alpha < 0: return None
                    elif beta > 0: lo = max(lo, -alpha/beta)
                    else: hi = min(hi, -alpha/beta)
                return (lo, hi) if lo <= hi else None
            # la droite peut aussi passer juste à côté du coin du bois (face et pli) sans le toucher :
            # on retient alors la face seule
            return intervalle(conds) or intervalle(conds[:1])
        Im, Fm, Ij, Fj = bois(a, km), bois(av, km), bois(a, kj), bois(av, kj)
        if None in (Im, Fm, Ij, Fj) or not all(math.isfinite(t) for t in (Im[1], Fm[1], Ij[0], Fj[0])): return None
        # côté mur, le panneau est vers les t croissants : limite = sortie du bois ; côté jour, entrée
        tBm, tFm, tBj, tFj = Im[1], Fm[1], Ij[0], Fj[0]
        tbm = max(tFm, tBm); tbj = min(tFj, tBj)      # coins arrière : d'équerre si possible
        biseau = lambda dt: math.degrees(math.atan2(dt, ep)) if dt > 1e-6 else 0.0
        pt = lambda o, t: (o[0]+u[0]*t, o[1]+u[1]*t)
        mil_m, mil_j = (tFm+tbm)/2, (tFj+tbj)/2
        trous_t = [mil_m + x for x in self.hole_positions(mil_j - mil_m)]
        return dict(a=pt(a, tbm), b=pt(a, tbj), fa=pt(av, tFm), fb=pt(av, tFj),
                    biseau_a=biseau(tBm - tFm), biseau_b=biseau(tFj - tBj),
                    trous=[pt((a[0]+nv[0]*ep/2, a[1]+nv[1]*ep/2), t) for t in trous_t],
                    trous_x=[t - tFm for t in trous_t])

    def riser_local(self, i):
        """Contremarche i vue de face côté escalier : longueur de la face avant (longueur de débit),
        hauteur visible, hauteur totale (avec la partie engagée dans la rainure) et pré-perçages
        (distances depuis le bord gauche de la face avant)."""
        r = self.RISERS[i]
        L = math.dist(r['fa'], r['fb']); H = r['z_haut']-r['z_bas']
        Htot = H + (self.P.profondeur_rainure if r['rainure'] else 0.0)
        holes = list(r['trous_x']) if r['percage'] else []
        if self.left: holes = [L-x for x in holes]
        return L, H, Htot, holes

    def riser_biseaux(self, i):
        """Bouts biseautés de la contremarche i : liste de (côté 'mur' ou 'jour', 'gauche' ou
        'droite' sur sa fiche, angle en degrés)."""
        r = self.RISERS[i]; out = []
        for cote, ang in (('mur', r['biseau_a']), ('jour', r['biseau_b'])):
            if ang > 0.05:
                gauche = (cote == 'mur') != self.left
                out.append((cote, 'gauche' if gauche else 'droite', ang))
        return out

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
                # empreinte du panneau (faces avant et arrière, bouts biseautés compris), élargie du
                # jeu de la rainure, bornée à la largeur réelle du nez
                a, b, fa, fb = rb['a'], rb['b'], rb['fa'], rb['fb']
                L_ = math.dist(a, b); nv = (-(b[1]-a[1])/L_, (b[0]-a[0])/L_); j_ = JEU_RAINURE/2
                q = [(a[0]-nv[0]*j_, a[1]-nv[1]*j_), (b[0]-nv[0]*j_, b[1]-nv[1]*j_),
                     (fb[0]+nv[0]*j_, fb[1]+nv[1]*j_), (fa[0]+nv[0]*j_, fa[1]+nv[1]*j_)]
                g = hp_clip(hp_clip([tf(p) for p in q], (0, 0), (1, 0)), (L, 0), (-1, 0))
                if len(g) >= 3 and abs(area(g)) > 1e-3: groove = clean(g)
            ra = self.RISERS.get(m)
            if ra is not None:
                holes = [tf(p) for p in ra['trous']]
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
        b = self.CR[k].rng[1]
        self.RODS = getattr(self, 'RODS', {})
        self.RODS[k] = [(F((b, z)), F((b-self.P.ancrage+2.5, z))) for z in self.TIGES] if self.ancrage_chevetre(k) else []
        Lb = max(p[0] for p in pts); Wb = max(p[1] for p in pts)
        return pts, bolts, Lb, Wb, abs(math.degrees(th))

