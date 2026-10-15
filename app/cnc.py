# -*- coding: utf-8 -*-
"""
Fabrication à la CNC : G-code GRBL des usinages précis (rainures, pré-trous) et gravure des contours
à scier ensuite à la main. Les pièces ne sont PAS découpées à la CNC (voir CONCEPTION.md, « Fabrication
à la CNC »).

Dépendance : aucune (bibliothèque standard uniquement). Les cotes de l'escalier sont en cm ; tout ce
module qui touche à la machine (G-code, réglages) est en mm, mm/min et tr/min.

Chaque pièce est posée **dessous vers le haut** (la face qui porte la rainure et les pré-trous des
marches, et qui reste cachée une fois l'escalier monté). Repère machine : origine au coin avant gauche
du brut, X vers la droite, Y vers l'arrière, Z = 0 sur le dessus du brut (négatif dans le bois).

    plan_cnc(E)        -> Plan : pièces, programmes (un par pièce et par outil), alertes, durée totale
    zip_cnc(plan, E)   -> octets d'un .zip : un .nc par programme + GUIDE_FRAISAGE.txt
    guide_fraisage(plan, E) -> texte du guide d'atelier
"""
import io
import math
import unicodedata
import zipfile

from .geometrie import EscalierErreur, JEU_RAINURE, pip

# --- constantes d'usinage (pas des paramètres : voir CONCEPTION.md) ------------------------------
RAPIDE = 5000.0          # mm/min : déplacements rapides G0, pour l'estimation de durée seulement
Z_DEGAGE = 5.0           # mm au-dessus du brut
MARGE = 10.0             # mm de brut autour de la pièce
AVANCE_Z_MAX = 800.0     # mm/min en Z
ANGLE_RAMPE = 3.0        # degrés : entrée en rampe dans la rainure
PAS_LATERAL = 0.6        # recouvrement des passes de la rainure, en fraction du diamètre
PASSE_RELATIVE = 0.5     # profondeur d'une passe, en fraction du diamètre
BROCHE_TRAVAIL = 12000.0 # tr/min visés pour la fraise principale (bas régime : voir CONCEPTION.md)
BROCHE_GRAVURE = 18000.0
AVANCE_GRAVURE = 1500.0
POINTAGE = 1.5           # mm : profondeur d'un point de repère
DIAM_FRAISE_TROUS = 3.0  # mm : seconde fraise, pour les pré-trous
PROF_PASSE_TROU = 3.0    # mm : perçage par passes (débourrage)
PAS_HELICE = 1.0         # mm de descente par tour (trous plus larges que la fraise)
ATTENTE_BROCHE = 3       # s : montée en vitesse de la broche

# charge par dent (mm) pour une fraise de 6 mm : (nominale, mini). Ordre de grandeur des tableaux de
# fabricants (CNC Router Store, Amana Tool, Engineers Edge), à ajuster à l'oreille et aux copeaux :
# de la poussière = trop faible, des éclats = trop forte. Elle varie à peu près comme le diamètre.
CHARGE = {'resineux': (0.08, 0.05), 'feuillu_tendre': (0.07, 0.045), 'feuillu_dur': (0.055, 0.035),
          'contreplaque': (0.07, 0.045), 'mdf': (0.09, 0.055)}


def _ascii(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


def duree_texte(s):
    m = int(round(s/60))
    return f"{m} min" if m < 60 else f"{m//60} h {m % 60:02d}"


# ----------------------------------------------------------------------------
# Réglages de coupe
# ----------------------------------------------------------------------------
class Reglages:
    def __init__(self, diam, dents, rpm, avance, plongee, passe, charge, charge_mini):
        self.diam, self.dents, self.rpm, self.avance = diam, dents, rpm, avance
        self.plongee, self.passe, self.charge, self.charge_mini = plongee, passe, charge, charge_mini


def reglages(P, diam, dents, alertes, nom):
    """Vitesse de broche, avance, plongée et passe d'une fraise (formule : avance = tr/min × dents ×
    charge par dent), bornées par la machine. Une alerte est ajoutée si la charge par dent reste trop faible."""
    nominale, mini = CHARGE[P.cnc_materiau]
    k = min(1.5, max(0.4, diam/6.0)); nominale *= k; mini *= k
    rpm = min(P.cnc_broche_max, max(P.cnc_broche_min, BROCHE_TRAVAIL))
    avance = min(rpm*dents*nominale, P.cnc_avance_max)
    charge = avance/(rpm*dents)
    if charge < mini:                      # avance plafonnée par la machine : on baisse la broche
        rpm = max(P.cnc_broche_min, min(rpm, avance/(dents*mini)))
        charge = avance/(rpm*dents)
    if charge < mini*0.999:
        alertes.append(f"{nom} : charge par dent de {charge:.3f} mm, sous le mini de {mini:.3f} mm pour ce matériau "
                       f"(broche déjà à {rpm:.0f} tr/min, avance de {avance:.0f} mm/min) : le bois risque de chauffer et de brûler. "
                       f"Une fraise à une dent ou une broche moins rapide corrigerait cela.")
    return Reglages(diam, dents, rpm, avance, min(0.3*avance, AVANCE_Z_MAX), diam*PASSE_RELATIVE, charge, mini)


# ----------------------------------------------------------------------------
# Écriture du G-code
# ----------------------------------------------------------------------------
class Programme:
    """Un fichier G-code (une pièce, un outil). Suit la position de l'outil pour compter la durée et
    les bornes atteintes (XY dans le brut, Z maxi de plongée)."""
    def __init__(self, fichier, piece, outil, resume, rpm, no_outil):
        self.fichier, self.piece, self.outil, self.resume, self.rpm = fichier, piece, outil, resume, rpm
        self.no_outil = no_outil
        self.corps = []; self.x = self.y = 0.0; self.z = Z_DEGAGE; self.s = float(ATTENTE_BROCHE)
        self.f = None; self.avance_max = 0.0
        self.xmin = self.ymin = math.inf; self.xmax = self.ymax = -math.inf; self.zmin = 0.0
        self.entete = []

    @staticmethod
    def _n(v):
        t = f"{v:.3f}".rstrip('0').rstrip('.')
        return '0' if t in ('-0', '') else t

    def _suit(self, x, y, z):
        self.xmin, self.xmax = min(self.xmin, x), max(self.xmax, x)
        self.ymin, self.ymax = min(self.ymin, y), max(self.ymax, y)
        self.zmin = min(self.zmin, z)

    def _va(self, code, x, y, z, f):
        nx = self.x if x is None else x; ny = self.y if y is None else y; nz = self.z if z is None else z
        mots = [code]
        for axe, nv, av in (('X', nx, self.x), ('Y', ny, self.y), ('Z', nz, self.z)):
            if abs(nv-av) > 1e-9: mots.append(f"{axe}{self._n(nv)}")
        d = math.dist((self.x, self.y, self.z), (nx, ny, nz))
        if code == 'G1':
            if self.f != f: mots.append(f"F{self._n(f)}"); self.f = f
            self.s += d/f*60; self.avance_max = max(self.avance_max, f)
        else:
            self.s += d/RAPIDE*60
        if len(mots) > 1: self.corps.append(' '.join(mots))
        self.x, self.y, self.z = nx, ny, nz
        self._suit(nx, ny, nz)

    def rapide(self, x=None, y=None, z=None): self._va('G0', x, y, z, None)
    def lin(self, f, x=None, y=None, z=None): self._va('G1', x, y, z, f)

    def cercle(self, f, r0, z):
        """Tour complet (sens trigonométrique) autour du point où se trouve l'outil moins r0 en X,
        en descendant à z : interpolation hélicoïdale."""
        dz = z-self.z
        mots = f"G3 X{self._n(self.x)} Y{self._n(self.y)} I{self._n(-r0)} J0 Z{self._n(z)}"
        if self.f != f: mots += f" F{self._n(f)}"; self.f = f
        self.corps.append(mots)
        self.s += math.hypot(2*math.pi*r0, dz)/f*60; self.avance_max = max(self.avance_max, f)
        cx = self.x-r0
        self.z = z; self._suit(cx-r0, self.y-r0, z); self._suit(cx+r0, self.y+r0, z)

    def texte(self):
        tete = [f"({_ascii(l)})" for l in self.entete]
        init = ["G21 G90 G17 G94", f"T{self.no_outil}", f"G0 Z{self._n(Z_DEGAGE)}", f"M3 S{self._n(self.rpm)}", f"G4 P{ATTENTE_BROCHE}"]
        fin = [f"G0 Z{self._n(Z_DEGAGE)}", "M5", "G0 X0 Y0", "M30"]
        return '\n'.join(tete+init+self.corps+fin)+'\n'


# ----------------------------------------------------------------------------
# Opérations
# ----------------------------------------------------------------------------
def _graver(prog, boucles, prof, avance, plongee):
    """Trace des contours fermés (outil centré sur le trait : aucun décalage de rayon)."""
    for pts in boucles:
        prog.rapide(z=Z_DEGAGE); prog.rapide(x=pts[0][0], y=pts[0][1])
        prog.lin(plongee, z=-prof)
        for p in pts[1:]+[pts[0]]:
            prog.lin(avance, x=p[0], y=p[1])
        prog.rapide(z=Z_DEGAGE)


def _tracer(prog, traits, prof, avance, plongee):
    """Traits ouverts (texte gravé)."""
    for pts in traits:
        prog.rapide(z=Z_DEGAGE); prog.rapide(x=pts[0][0], y=pts[0][1])
        prog.lin(plongee, z=-prof)
        for p in pts[1:]:
            prog.lin(avance, x=p[0], y=p[1])
        prog.rapide(z=Z_DEGAGE)


def _pointer(prog, points, plongee):
    for x, y in points:
        prog.rapide(z=Z_DEGAGE); prog.rapide(x=x, y=y)
        prog.lin(plongee, z=-POINTAGE)
        prog.rapide(z=Z_DEGAGE)


def _percer(prog, points, d_trou, d_outil, prof, reg):
    """Pré-trous borgnes : par passes si le trou a le diamètre de la fraise, en hélice sinon."""
    r0 = (d_trou-d_outil)/2
    for x, y in points:
        prog.rapide(z=Z_DEGAGE)
        if r0 < 0.1:
            prog.rapide(x=x, y=y)
            z = 0.0
            while z < prof-1e-9:
                prec = z; z = min(prof, z+PROF_PASSE_TROU)
                prog.rapide(z=-prec+0.5 if prec > 0 else 1.0)
                prog.lin(reg.plongee, z=-z)
                prog.rapide(z=1.0)
        else:
            prog.rapide(x=x+r0, y=y); prog.rapide(z=1.0)
            prog.lin(reg.plongee, z=0.0)
            z = 0.0
            while z < prof-1e-9:
                z = min(prof, z+PAS_HELICE); prog.cercle(reg.plongee, r0, -z)
            prog.cercle(reg.avance, r0, -prof)
            prog.lin(reg.avance, x=x)
        prog.rapide(z=Z_DEGAGE)


def _poche(prog, poly, prof, reg, alertes, nom):
    """Rainure (polygone convexe) en poche : passes de profondeur `reg.passe`, allers-retours parallèles
    aux grands côtés espacés de PAS_LATERAL × diamètre, entrée en rampe. Les bouts sont prolongés d'une
    fois et demie le rayon de la fraise : le panneau y entre jusqu'au fond (les angles arrondis par la
    fraise tombent hors de son empreinte, dans la zone qui reste sous la marche)."""
    r = reg.diam/2
    n = len(poly)
    a, b = max(((poly[i], poly[(i+1) % n]) for i in range(n)), key=lambda e: math.dist(*e))
    L = math.dist(a, b); d = ((b[0]-a[0])/L, (b[1]-a[1])/L); nv = (-d[1], d[0])
    ss = [p[0]*nv[0]+p[1]*nv[1] for p in poly]; smin, smax = min(ss), max(ss)
    utile = smax-smin-reg.diam
    if utile < -1e-6:
        alertes.append(f"{nom} : la rainure ({smax-smin:.1f} mm de large) est plus étroite que la fraise de {reg.diam:g} mm ; "
                       "elle sera taillée à la largeur de la fraise.")
    if utile <= 1e-6:
        positions = [(smin+smax)/2]
    else:
        nb = math.ceil(utile/(PAS_LATERAL*reg.diam))+1
        positions = [smin+r+k*utile/(nb-1) for k in range(nb)]
    voies = []
    for s_ in positions:
        ts = []
        for i in range(n):
            p, q = poly[i], poly[(i+1) % n]
            sp, sq = p[0]*nv[0]+p[1]*nv[1]-s_, q[0]*nv[0]+q[1]*nv[1]-s_
            if sp*sq <= 0 and abs(sp-sq) > 1e-12:
                t = sp/(sp-sq); ts.append((p[0]+t*(q[0]-p[0]))*d[0]+(p[1]+t*(q[1]-p[1]))*d[1])
        if not ts: continue
        t0, t1 = min(ts)-1.5*r, max(ts)+1.5*r
        pt = lambda t: (nv[0]*s_+d[0]*t, nv[1]*s_+d[1]*t)
        voies.append((pt(t0), pt(t1)))
    nb_passes = max(1, math.ceil(prof/reg.passe-1e-9)); pas = prof/nb_passes
    for k in range(1, nb_passes+1):
        z = -k*pas; zp = -(k-1)*pas
        (x0, y0), (x1, y1) = voies[0]
        prog.rapide(z=Z_DEGAGE); prog.rapide(x=x0, y=y0); prog.rapide(z=1.0)
        prog.lin(reg.plongee, z=zp)
        Lv = math.dist((x0, y0), (x1, y1)); lr = min(Lv/2, pas/math.tan(math.radians(ANGLE_RAMPE)))
        prog.lin(reg.plongee, x=x0+(x1-x0)*lr/Lv, y=y0+(y1-y0)*lr/Lv, z=z)
        prog.lin(reg.avance, x=x0, y=y0)
        for i, (p, q) in enumerate(voies):
            if i % 2: p, q = q, p
            prog.lin(reg.avance, x=p[0], y=p[1]); prog.lin(reg.avance, x=q[0], y=q[1])
        prog.rapide(z=Z_DEGAGE)


# ----------------------------------------------------------------------------
# Identification des pièces (texte gravé, police en traits)
# ----------------------------------------------------------------------------
# Caractères sur une grille de 2 × 4 ; chaque tracé est une ligne brisée (ouverte).
GLYPHES = {
    '0': [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)]],
    '1': [[(0, 3), (1, 4), (1, 0)]],
    '2': [[(0, 4), (2, 4), (2, 2), (0, 2), (0, 0), (2, 0)]],
    '3': [[(0, 4), (2, 4), (2, 0), (0, 0)], [(0, 2), (2, 2)]],
    '4': [[(0, 4), (0, 2), (2, 2)], [(2, 4), (2, 0)]],
    '5': [[(2, 4), (0, 4), (0, 2), (2, 2), (2, 0), (0, 0)]],
    '6': [[(2, 4), (0, 4), (0, 0), (2, 0), (2, 2), (0, 2)]],
    '7': [[(0, 4), (2, 4), (2, 0)]],
    '8': [[(0, 0), (2, 0), (2, 4), (0, 4), (0, 0)], [(0, 2), (2, 2)]],
    '9': [[(2, 2), (0, 2), (0, 4), (2, 4), (2, 0), (0, 0)]],
    'A': [[(0, 0), (1, 4), (2, 0)], [(0.5, 1.6), (1.5, 1.6)]],
    'B': [[(0, 0), (0, 4), (1.5, 4), (2, 3.2), (1.5, 2), (0, 2)], [(1.5, 2), (2, 1.2), (1.5, 0), (0, 0)]],
    'C': [[(2, 4), (0, 4), (0, 0), (2, 0)]],
    'D': [[(0, 0), (0, 4), (1.5, 4), (2, 3), (2, 1), (1.5, 0), (0, 0)]],
    'H': [[(0, 0), (0, 4)], [(2, 0), (2, 4)], [(0, 2), (2, 2)]],
    'I': [[(0, 4), (2, 4)], [(1, 4), (1, 0)], [(0, 0), (2, 0)]],
    'M': [[(0, 0), (0, 4), (1, 2), (2, 4), (2, 0)]],
}
ETIQUETTES = {'mur_dep': "MD", 'mur_arr': "MA", 'int_bas': "IB", 'int_haut': "IH"}   # crémaillères
TEXTE_HAUT = 30.0        # mm, hauteur des caractères gravés (réduite à 20 puis 12 mm si la pièce est étroite)
TEXTE_LARGE = 1.4        # élargissement des caractères (lisibles même dans un simulateur à résolution grossière)
TEXTE_DEGAGE = 4.0       # mm libres autour du texte : contour, rainure, trous


def _dist_segment(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    L2 = dx*dx+dy*dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L2))
    return math.dist(p, (a[0]+t*dx, a[1]+t*dy))


def _dist_poly(p, poly):
    return min(_dist_segment(p, poly[i], poly[(i+1) % len(poly)]) for i in range(len(poly)))


def _pas(a, b, pas):
    out = []
    x = a
    while x <= b+1e-9:
        out.append(x)
        x += pas
    return out


def largeur_texte(texte, haut):
    return (3.0*len(texte)-1.0)*haut/4.0*TEXTE_LARGE


def trace_texte(texte, x, y, haut):
    """Traits (lignes brisées, mm) du texte dont le coin bas gauche est en (x, y)."""
    k = haut/4.0
    out = []
    for i, c in enumerate(texte):
        for ligne in GLYPHES[c]:
            out.append([(x+(i*3.0+px)*k*TEXTE_LARGE, y+py*k) for px, py in ligne])
    return out


def placer_texte(texte, contour, evites):
    """Place le texte à l'intérieur de la pièce, hors du contour, des rainures et des trous (`evites` :
    liste de (point ou polygone, distance mini)), le plus près possible du centre. Renvoie les traits,
    ou None si rien ne tient."""
    cx = sum(p[0] for p in contour)/len(contour)
    cy = sum(p[1] for p in contour)/len(contour)
    xs = [p[0] for p in contour]
    ys = [p[1] for p in contour]
    for haut in (TEXTE_HAUT, 20.0, 12.0):
        w = largeur_texte(texte, haut)
        cands = [(x, y) for x in _pas(min(xs), max(xs)-w, 15.0) for y in _pas(min(ys), max(ys)-haut, 15.0)]
        cands.sort(key=lambda c: math.dist((c[0]+w/2, c[1]+haut/2), (cx, cy)))
        for x, y in cands:
            ok = True
            for i in range(int(w//6)+2):
                for j in range(int(haut//6)+2):
                    q = (x+min(w, i*6.0), y+min(haut, j*6.0))
                    if not pip(q, contour) or _dist_poly(q, contour) < TEXTE_DEGAGE:
                        ok = False
                    for cible, d in evites:
                        if isinstance(cible, tuple):
                            dd = math.dist(q, cible)
                        else:
                            dd = 0.0 if pip(q, cible) else _dist_poly(q, cible)
                        if dd < d: ok = False
                    if not ok: break
                if not ok: break
            if ok:
                return trace_texte(texte, x, y, haut)
    return None


# ----------------------------------------------------------------------------
# Pièces
# ----------------------------------------------------------------------------
class Piece:
    def __init__(self, nom, titre, epaisseur):
        self.nom, self.titre, self.epaisseur = nom, titre, epaisseur   # épaisseur en mm
        self.brut = None          # (X, Y) du brut en mm, une fois placé
        self.tient = True; self.motif = ""; self.tourne = False
        self.programmes = []; self.notes = []; self.a_la_main = []
        self.contour_machine = []; self.trous_machine = []; self.rainure_machine = []
        self.etiquette = ""; self.traits_etiquette = []


def _gabarit(points_cm, miroir, zone):
    """Place la pièce dans le brut : miroir (pièce retournée) puis, si elle ne tient pas dans le sens
    de la fiche, rotation de 90°. Renvoie (transformation cm -> mm machine, (X, Y) du brut, tient, tourne)."""
    sgn = -1.0 if miroir else 1.0
    pts = [(10*sgn*x, 10*y) for x, y in points_cm]
    x0 = min(p[0] for p in pts); y0 = min(p[1] for p in pts)
    w = max(p[0] for p in pts)-x0+2*MARGE; h = max(p[1] for p in pts)-y0+2*MARGE
    zx, zy = zone
    tourne = False; tient = True; W, H = w, h
    if not (w <= zx and h <= zy):
        if h <= zx and w <= zy: tourne = True; W, H = h, w
        else: tient = False

    def f(p):
        X, Y = 10*sgn*p[0]-x0+MARGE, 10*p[1]-y0+MARGE
        return (h-Y, X) if tourne else (X, Y)
    return f, (W, H), tient, tourne


def _placer(piece, points_cm, miroir, P):
    f, brut, tient, tourne = _gabarit(points_cm, miroir, (P.cnc_zone_x, P.cnc_zone_y))
    piece.brut = brut; piece.tient = tient; piece.tourne = tourne
    if not tient:
        piece.motif = (f"brut de {brut[0]:.0f} × {brut[1]:.0f} mm avec la marge, la zone utile est de "
                       f"{P.cnc_zone_x:.0f} × {P.cnc_zone_y:.0f} mm")
    return f


def _boucle(f, pts_cm):
    return [f(p) for p in pts_cm]


class Plan:
    def __init__(self):
        self.pieces = []; self.alertes = []; self.reglages = {}

    @property
    def duree_totale(self):
        return sum(g.s for p in self.pieces for g in p.programmes)


def plan_cnc(E):
    """Calcule les pièces et leurs programmes pour l'escalier E."""
    P = E.P
    if P.cnc_broche_min > P.cnc_broche_max:
        raise EscalierErreur("CNC : la vitesse de broche mini dépasse la maxi.")
    plan = Plan(); al = plan.alertes
    ep_cm = P.ep_contremarche
    prof_rainure = P.profondeur_rainure*10
    r_main = reglages(P, P.cnc_fraise_diam, P.cnc_fraise_dents, al, "Fraise principale")
    r_trou = reglages(P, DIAM_FRAISE_TROUS, 2, al, "Fraise de 3 mm") if P.cnc_fraise_trous == "oui" else None
    r_grav = Reglages(0, 1, min(P.cnc_broche_max, max(P.cnc_broche_min, BROCHE_GRAVURE)), min(AVANCE_GRAVURE, P.cnc_avance_max),
                      min(0.3*AVANCE_GRAVURE, AVANCE_Z_MAX), 0, 0, 0)
    plan.reglages = {'fraise': r_main, 'trous': r_trou, 'gravure': r_grav}
    if ep_cm > 0:
        largeur_rainure = (ep_cm+JEU_RAINURE)*10
        if P.cnc_fraise_diam > largeur_rainure-0.5:
            raise EscalierErreur(f"CNC : la fraise de {P.cnc_fraise_diam:g} mm est trop large pour la rainure de contremarche "
                                 f"({largeur_rainure:.1f} mm).")
        if P.cnc_fraise_coupe < prof_rainure:
            raise EscalierErreur(f"CNC : la longueur de coupe de la fraise ({P.cnc_fraise_coupe:g} mm) est inférieure à la "
                                 f"profondeur de la rainure ({prof_rainure:g} mm).")
    prof_trou = P.cnc_prof_trou
    if prof_trou > P.ep_marche*10-3:
        prof_trou = P.ep_marche*10-3
        al.append(f"Pré-trous ramenés à {prof_trou:.0f} mm de profondeur : la marche ne fait que {P.ep_marche*10:.0f} mm d'épaisseur.")
    if P.cnc_fraise_trous == "oui":
        al.append(f"Fraise de 3 mm pour les pré-trous : sa longueur de coupe doit dépasser {prof_trou+2:.0f} mm.")
    rang = {}

    def programme(piece, outil, slug, resume, reg, no_outil):
        rang[piece.nom] = rang.get(piece.nom, 0)+1
        g = Programme(f"{piece.nom}_{rang[piece.nom]}_{slug}.nc", piece, outil, resume, reg.rpm, no_outil)
        g.entete = [f"Escalier quart tournant {P.sens} - {piece.titre}", f"Etape {rang[piece.nom]} : {resume}",
                    f"Brut {piece.brut[0]:.0f} x {piece.brut[1]:.0f} x {piece.epaisseur:.0f} mm, origine au coin avant gauche, Z0 sur le dessus",
                    f"Outil T{no_outil} : {outil} - broche {reg.rpm:.0f} tr/min"]
        piece.programmes.append(g)
        return g

    def usinages(piece, f, contour_cm, rainure_cm=None, trous_cm=(), pointer=(), etiquette=""):
        """Programmes d'une pièce : rainure (fraise principale), pré-trous (fraise de 3 mm), gravure du
        contour, du contour de la rainure et de l'identification (+ pointage)."""
        piece.contour_machine = _boucle(f, contour_cm)
        piece.trous_machine = _boucle(f, trous_cm)
        marques = _boucle(f, pointer)
        if rainure_cm:
            poly = _boucle(f, rainure_cm); piece.rainure_machine = poly
            g = programme(piece, f"fraise de {P.cnc_fraise_diam:g} mm, bout plat", f"rainure_fraise{P.cnc_fraise_diam:g}mm",
                          f"rainure de la contremarche, {prof_rainure:g} mm de profondeur", r_main, 1)
            _poche(g, poly, prof_rainure, r_main, al, piece.titre)
        if trous_cm and r_trou is not None:
            g = programme(piece, "fraise de 3 mm", "trous_fraise3mm", f"{len(trous_cm)} pré-trous de {P.cnc_diam_trou:g} mm, {prof_trou:g} mm de profondeur", r_trou, 2)
            _percer(g, piece.trous_machine, P.cnc_diam_trou, DIAM_FRAISE_TROUS, prof_trou, r_trou)
        if trous_cm and r_trou is None: marques = piece.trous_machine + marques
        if etiquette:
            evites = [(q, TEXTE_DEGAGE+6.0) for q in piece.trous_machine+marques]
            if piece.rainure_machine: evites.append((piece.rainure_machine, TEXTE_DEGAGE+r_main.diam))
            traits = placer_texte(etiquette, piece.contour_machine, evites)
            if traits is None:
                al.append(f"{piece.titre.capitalize()} : pas de place pour graver son identification « {etiquette} ».")
            else:
                piece.etiquette = etiquette; piece.traits_etiquette = traits
        quoi = ["du contour"] + (["de la rainure"] if piece.rainure_machine else []) + (["de l'identification"] if piece.etiquette else [])
        g = programme(piece, "fraise à graver en V", "gravure",
                      "gravure " + ", ".join(quoi[:-1]) + (" et " if len(quoi) > 1 else "") + quoi[-1]
                      + (" ; pointage des trous" if marques else ""), r_grav, 3)
        if marques: _pointer(g, marques, r_grav.plongee)
        if piece.traits_etiquette: _tracer(g, piece.traits_etiquette, P.cnc_prof_gravure, r_grav.avance, r_grav.plongee)
        boucles = ([piece.rainure_machine] if piece.rainure_machine else []) + [piece.contour_machine]
        _graver(g, boucles, P.cnc_prof_gravure, r_grav.avance, r_grav.plongee)

    # --- marches : dessous vers le haut, donc miroir de la fiche
    for m in range(1, E.n):
        pts, _, _, groove, holes = E.tread_local(m)
        pc = Piece(f"marche_{m:02d}", f"marche {m}", P.ep_marche*10)
        f = _placer(pc, pts+(groove or []), True, P)
        plan.pieces.append(pc)
        if pc.tient: usinages(pc, f, pts, groove, holes, etiquette=f"M{m}")
    # --- contremarches : face arrière vers le haut
    for i in sorted(E.RISERS):
        r = E.RISERS[i]
        Lf, H, Htot, _ = E.riser_local(i)
        ua = (r['b'][0]-r['a'][0], r['b'][1]-r['a'][1]); Lb = math.hypot(*ua)
        u = (ua[0]/Lb, ua[1]/Lb)
        s0 = (r['a'][0]-r['fa'][0])*u[0]+(r['a'][1]-r['fa'][1])*u[1]    # début de la face arrière, depuis la face avant (le long du panneau)
        s0 = max(0.0, s0)
        # face arrière vue de derrière : le bout côté mur est à droite pour un escalier à droite
        if not E.left: x0, x1 = Lf-(s0+Lb), Lf-s0
        else: x0, x1 = s0, s0+Lb
        pc = Piece(f"contremarche_{i:02d}", f"contremarche {i}", ep_cm*10)
        rect = [(x0, 0.0), (x1, 0.0), (x1, Htot), (x0, Htot)]
        f = _placer(pc, rect, False, P)
        plan.pieces.append(pc)
        if pc.tient: usinages(pc, f, rect, etiquette=f"C{i}")
    # --- crémaillères : posées face côté marches vers le haut
    for k in E.CR:
        pts, bolts, Lb, Wb, _ = E.board(k)
        pc = Piece(f"cremaillere_{k}", f"crémaillère {k}", P.ep_cremaillere*10)
        f = _placer(pc, pts, False, P)
        plan.pieces.append(pc)
        if pc.tient: usinages(pc, f, pts, pointer=bolts, etiquette=ETIQUETTES[k])
    # --- bastaing de soutien
    sw = P.soutien_largeur
    sp = E.SUP_POLY if not E.left else [(sw-q[0], q[1]) for q in E.SUP_POLY]
    pc = Piece("bastaing", "bastaing de soutien", P.ep_cremaillere*10)
    f = _placer(pc, sp, False, P)
    plan.pieces.append(pc)
    if pc.tient: usinages(pc, f, sp, etiquette="B")
    return plan


# ----------------------------------------------------------------------------
# Guide d'atelier et export
# ----------------------------------------------------------------------------
def guide_fraisage(plan, E):
    P = E.P; r = plan.reglages['fraise']; rg = plan.reglages['gravure']; rt = plan.reglages['trous']
    L = []
    t = L.append
    t(f"GUIDE DE FRAISAGE : escalier quart tournant {P.sens}")
    t("=" * 60)
    t("")
    t("1. PRINCIPE")
    t("La CNC ne découpe pas les pièces. Elle fait ce qui est difficile à la main : la rainure de contremarche")
    t("sous les marches et les pré-trous de vis, puis elle GRAVE le contour de chaque pièce, que tu scies ensuite")
    t("(scie circulaire, sauteuse, scie à ruban ou égoïne) en laissant le trait visible, avant de raboter ou poncer")
    t("jusqu'au trait. Un fichier G-code par pièce et par outil ; GRBL ne change pas d'outil tout seul : à chaque")
    t("fichier, change la fraise, refais le zéro Z (et seulement Z) sans desserrer la pièce, puis lance le fichier.")
    t("")
    t("2. FICHIERS DANS L'ORDRE D'EXÉCUTION")
    t("Pour chaque pièce : rainure, pré-trous, puis gravure ; les fichiers d'une même pièce se font sans la déplacer.")
    t("")
    for pc in plan.pieces:
        if not pc.tient: continue
        t(f"  {pc.titre.capitalize()} : brut {pc.brut[0]:.0f} × {pc.brut[1]:.0f} × {pc.epaisseur:.0f} mm"
          + (" (posé en travers : pièce tournée de 90°)" if pc.tourne else ""))
        for g in pc.programmes:
            t(f"      {g.fichier} : {g.resume} ({g.outil}), {duree_texte(g.s)}")
    t("")
    t(f"Durée totale estimée de fraisage : {duree_texte(plan.duree_totale)}, sans compter la mise en place (environ 10 minutes par pièce).")
    t("")
    t("3. MISE EN PLACE D'UNE PIÈCE")
    t("- Pose la pièce DESSOUS VERS LE HAUT : pour une marche, la face qui reçoit la rainure et les pré-trous, celle qui")
    t("  restera cachée ; pour une contremarche, la face arrière ; pour une crémaillère, la face côté marches.")
    t("  La gravure se retrouve ainsi sur la face cachée, et l'éclatement d'une scie circulaire à main ou d'une sauteuse")
    t("  (face visible vers le bas) tombe aussi du côté caché.")
    t("- Plaque le brut contre la butée gauche et la butée avant de la table ; bride-le dans les marges de 10 mm")
    t("  autour de la pièce, jamais sur le trait ni dans la rainure.")
    t("- Origine X/Y : coin avant gauche du brut. Z0 : DESSUS du brut (palpeur), car une planche gauchie varie plus que la")
    t(f"  profondeur de gravure ({P.cnc_prof_gravure:g} mm).")
    t("- Avant la première vraie pièce : un passage à vide (Z décalé de 20 mm), puis un essai sur une chute pour")
    t("  régler les vitesses à l'oreille et aux copeaux (de la poussière : charge trop faible ; des éclats : trop forte).")
    t("- Aspire les copeaux de la rainure en cours de fraisage (air comprimé ou aspirateur près de la fraise).")
    t("")
    t("4. OUTILS ET RÉGLAGES CALCULÉS")
    t("Chaque fichier commence par un numéro d'outil (T1, T2 ou T3, sans M6 : GRBL l'ignore). Dans un simulateur comme")
    t("CAMotics, définis ces outils dans la table des outils : sans cela, il simule un outil par défaut beaucoup plus")
    t(f"fin et la rainure paraît mal creusée. T1 = fraise cylindrique de {r.diam:g} mm ; T2 = fraise cylindrique de 3 mm ;")
    t("T3 = fraise à graver en V (cône de 60°, pointe de 0,1 mm).")
    t(f"Matériau : {P.cnc_materiau.replace('_', ' ')}. Machine : zone utile {P.cnc_zone_x:g} × {P.cnc_zone_y:g} mm, avance maxi {P.cnc_avance_max:g} mm/min.")
    t(f"- Fraise de {r.diam:g} mm, {r.dents} dent(s), bout plat, hélice montante : {r.rpm:.0f} tr/min, avance {r.avance:.0f} mm/min,")
    t(f"  plongée {r.plongee:.0f} mm/min, passes de {r.passe:g} mm, charge par dent {r.charge:.3f} mm. Entrée en rampe de {ANGLE_RAMPE:g}°.")
    if rt is not None:
        t(f"- Fraise de 3 mm (pré-trous) : {rt.rpm:.0f} tr/min, avance {rt.avance:.0f} mm/min, plongée {rt.plongee:.0f} mm/min.")
    t(f"- Fraise à graver en V (30 à 60°) : {rg.rpm:.0f} tr/min, avance {rg.avance:.0f} mm/min, profondeur {P.cnc_prof_gravure:g} mm.")
    t("")
    t("Identification gravée sur chaque pièce (face cachée) : M n = marche n, C n = contremarche n, B = bastaing,")
    t("MD / MA = crémaillère mur de départ / d'arrivée, IB / IH = crémaillère intérieure basse / haute.")
    t("Le contour de la rainure est gravé en plus de la rainure fraisée, pour la repérer à l'œil et la contrôler.")
    t("")
    t("5. CE QUI RESTE À FAIRE À LA MAIN")
    t("- Scier chaque pièce d'après le trait gravé, du côté de la chute, en laissant le trait visible ; raboter ou")
    t("  poncer jusqu'au trait (précision de coupe à la main : environ 1 mm). Angles rentrants : égoïne ou sauteuse.")
    t("- Scie circulaire à main ou sauteuse : la face gravée (cachée) est vers le haut, c'est la bonne disposition.")
    t("  Scie sur table ou égoïne : l'éclatement se fait sur la face du dessous, donc visible ; colle une bande de scotch")
    t("  de peintre sur la face visible le long de la coupe, utilise une lame fine de 60 à 80 dents et scie à 1 mm du trait.")
    t("- Pré-trous : " + ("à percer à la main aux points gravés (Ø "+f"{P.cnc_diam_trou:g} mm, {P.cnc_prof_trou:g} mm de profondeur)." if rt is None
                          else "faits à la CNC ; les vis des contremarches entrent par le dessous de la marche, dans la languette."))
    t("- Contremarches : les vis entrent dans le chant du bas (pas de trous à la CNC). Le trait gravé donne la face ARRIÈRE ;")
    t("  la longueur de débit est celle de la face AVANT, plus longue d'un biseau à chaque bout concerné (voir ci-dessous).")
    biseaux = []
    for i in sorted(E.RISERS):
        for cote, gd, ang in E.riser_biseaux(i):
            biseaux.append(f"  contremarche {i} : bout côté {cote} biseauté de {ang:.1f}° sur la face arrière "
                           f"(face avant : {math.dist(E.RISERS[i]['fa'], E.RISERS[i]['fb']):.1f} cm), à ajuster de 1 à 2° de dépouille")
    if biseaux:
        t("  Biseaux (angle de la lame par rapport à l'équerre) :")
        for b in biseaux: t(b)
        if any(ang > 45 for i in E.RISERS for _, _, ang in E.riser_biseaux(i)):
            t("  Attention : un biseau dépasse 45°, au-delà de ce que fait une scie sur table.")
    t("- Crémaillères : boulons du poteau, tiges M10 en bout et leurs mortaises ; les trous des boulons sont seulement pointés")
    t("  (traversent 45 mm : à percer à la main). Poteau d'angle : hors CNC (perçages latéraux).")
    horszone = [pc for pc in plan.pieces if not pc.tient]
    if horszone:
        t("")
        t("6. PIÈCES HORS DE LA ZONE UTILE (aucun fichier, à tracer à la main d'après les fiches du PDF)")
        for pc in horszone: t(f"- {pc.titre.capitalize()} : {pc.motif}")
    if plan.alertes:
        t("")
        t("7. ALERTES")
        for a in plan.alertes: t(f"- {a}")
    return '\n'.join(L)+'\n'


def zip_cnc(plan, E):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for pc in plan.pieces:
            for g in pc.programmes: z.writestr(g.fichier, g.texte())
        z.writestr("GUIDE_FRAISAGE.txt", guide_fraisage(plan, E))
    buf.seek(0)
    return buf
