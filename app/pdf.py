#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mise en page du PDF de fabrication (reportlab)."""
import io, math, os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Flowable)

from .geometrie import fr, area, JEU_LIMON, RECUL_CREMAILLERE
from .rendu3d import View3D

# ----------------------------------------------------------------------------
# Rendu PDF
# ----------------------------------------------------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether, Flowable)
from reportlab.lib.pagesizes import landscape

INK = colors.HexColor("#1f2a36"); MUTED = colors.HexColor("#5d6874"); RULE = colors.HexColor("#c9ced3")
WOOD = colors.HexColor("#efe4cf"); NEZ = colors.HexColor("#c2410c"); DIM = colors.HexColor("#1d4ed8")
CREM = colors.HexColor("#c9a97e"); TRE = colors.HexColor("#0f766e"); BAND = colors.HexColor("#cfe5df")


class Anchor(Flowable):
    """Marque la page courante comme destination nommée `key`, et note son numéro dans `pages`
    (pour reporter les numéros de page dans le sommaire, construit avant que la pagination soit connue)."""
    def __init__(self, key, pages):
        super().__init__()
        self.key = key; self.pages = pages
        self.width = 0; self.height = 0
    def wrap(self, aw, ah): return 0, 0
    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.pages[self.key] = self.canv.getPageNumber()

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


def build_pdf(E, path):
    P = E.P; st = styles()
    W = A4[0] - 24*mm
    sens = "droite" if not E.left else "gauche"
    MX = (lambda x: -x) if E.left else (lambda x: x)
    VERSION = os.environ.get("APP_VERSION", "dev")

    TOC = [("resultats", "Résultats et paramètres"), ("plan", "Plan d'ensemble (vue de dessus)"),
           ("vue3d", "Vue en perspective"), ("debit", "Liste de débit"), ("montage", "Principe de montage"),
           ("cremailleres", "Les crémaillères"), ("marches", "Les marches")]
    if E.RISERS: TOC.append(("contremarches", "Les contremarches"))

    def make_story(pages):
        """Construit le document ; `pages` donne le numéro de page de chaque section du sommaire
        (vide au premier passage, rempli par ce même passage pour alimenter le second)."""
        story = []
        # --- sommaire
        story.append(Paragraph(f"Escalier quart tournant à {sens} : plans de fabrication", st['h1']))
        story.append(Paragraph(f"Version {VERSION}", st['small']))
        story.append(Paragraph("Marches posées sur crémaillères, poteau d'angle côté vide. Toutes les cotes sont en centimètres.", st['p']))
        story.append(Spacer(1, 8)); story.append(Paragraph("Sommaire", st['h2']))
        for key, title in TOC:
            pg = pages.get(key, "")
            story.append(Paragraph(f'<a href="#{key}" color="#1d4ed8"><u>{title}</u></a>' + (f" — p. {pg}" if pg else ""), st['p']))
        story.append(Spacer(1, 8))

        # --- résultats et paramètres
        story.append(Anchor("resultats", pages)); story.append(Paragraph("Résultats et paramètres", st['h2']))
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
        if P.ep_contremarche > 0:
            prow.append(["Contremarches, épaisseur / rainure", f"{fr(P.ep_contremarche)} / {fr(P.profondeur_rainure)}"])
        t = Table([[tbl(rows, size=8), tbl(prow, size=8)]], hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 12)]))
        story.append(t); story.append(Spacer(1, 6))
        for a in E.alertes: story.append(Paragraph("Attention : " + a, st['alert']))

        # --- plan d'ensemble
        story.append(PageBreak()); story.append(Anchor("plan", pages)); story.append(Paragraph("Plan d'ensemble", st['h2']))
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
        story.append(Anchor("vue3d", pages)); story.append(Paragraph("Vue en perspective, à hauteur d'homme", st['h2']))
        WL3 = landscape(A4)[0] - 24*mm
        cam = (E.JR + 210, E.Y0 + 190, 165); tgt = (E.JR*0.55, E.JR*0.35, 125)
        story.append(View3D(E, cam, tgt, WL3, 150*mm))
        story.append(Paragraph("Œil à 1,65 m du sol, dans la pièce, face au départ de l'escalier. Le plancher d'arrivée est figuré en transparence "
                               "autour de la trémie ; les murs et le sol en gris clair.", st['small']))
        story.append(NextPageTemplate('portrait'))

        # --- précalcul des débits (marches), nécessaire avant la liste de débit
        deb = []
        for m in range(1, E.n):
            Lc, _, _, _, _ = E.tread_local(m)
            xs = [p[0] for p in Lc]; ys = [p[1] for p in Lc]
            deb.append((m, max(xs)-min(xs), max(ys)-min(ys)))
        sw = P.soutien_largeur; sh = max(q[1] for q in E.SUP_POLY)

        # --- liste de débit
        story.append(PageBreak()); story.append(Anchor("debit", pages)); story.append(Paragraph("Liste de débit", st['h2']))
        rows = [["Pièce", "Longueur × largeur × épaisseur"]]
        for m, l, w in deb: rows.append([f"Marche {m}", f"{math.ceil(l)} × {math.ceil(w)} × {fr(P.ep_marche)}"])
        for i in sorted(E.RISERS):
            L, H, Htot, holes = E.riser_local(i)
            rows.append([f"Contremarche {i}", f"{math.ceil(L)} × {math.ceil(Htot)} × {fr(P.ep_contremarche)}"])
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

        # --- principe de montage
        story.append(PageBreak()); story.append(Anchor("montage", pages)); story.append(Paragraph("Principe de montage", st['h2']))
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
        if P.ep_contremarche > 0:
            story.append(Paragraph(
                f"Contremarches : panneaux de {fr(P.ep_contremarche)} cm d'épaisseur, posés après coup par le dessous de l'escalier. En haut, "
                f"ils s'encastrent dans une rainure de {fr(P.profondeur_rainure)} cm de profondeur creusée dans la face inférieure de la marche "
                f"du dessus ; en bas, ils se vissent dans des pré-perçages, dans la face inférieure de la marche du dessous, cachés sous le "
                f"recouvrement de la marche suivante. Largeur resserrée de {fr(JEU_LIMON, 1)} cm de chaque côté par rapport aux crémaillères.", st['p']))
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
        story.append(Paragraph("Bastaing de soutien côté mur", st['h3']))
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
        story.append(Paragraph("Ordre de montage", st['h3']))
        story.append(Paragraph("1. Poser le bastaing de soutien, puis la crémaillère mur de départ et la crémaillère mur d'arrivée, vissées dans les montants. "
                               "2. Poser le poteau d'angle et les deux crémaillères intérieures, les boulonner, fixer les talons sous le chevêtre et les pieds "
                               "au sol ; vérifier que les paliers sont de niveau d'un côté à l'autre. 3. Poser les marches de bas en haut, collées "
                               "(colle polyuréthane) et vissées par-dessus." +
                               (" 4. Visser les contremarches par le dessous, après coup." if P.ep_contremarche > 0 else ""), st['p']))

        # --- crémaillères
        story.append(PageBreak()); story.append(Anchor("cremailleres", pages)); story.append(Paragraph("Les crémaillères", st['h2']))
        story.append(Paragraph("Quatre crémaillères : deux côté mur, deux côté jour (intérieures), détaillées ci-après (développé puis tracé dans le brut).",
                               st['p']))
        for idx, k in enumerate(E.CR):
            if idx > 0: story.append(PageBreak())
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

        # --- marches
        story.append(PageBreak()); story.append(Anchor("marches", pages)); story.append(Paragraph("Les marches", st['h2']))
        cote = "mur à gauche, jour à droite" if not E.left else "jour à gauche, mur à droite"
        story.append(Paragraph(f"Chaque marche est dessinée vue de dessus, nez en bas ({cote}). Origine : extrémité gauche du nez (point A). "
                               f"X le long du nez vers la droite, Y vers l'arrière. En vert pâle, les zones qui portent sur les crémaillères : "
                               f"c'est là qu'on visse (deux vis par appui, noyées et bouchonnées). Le nez est en rouge." +
                               (" En pointillé orange, la rainure de la contremarche du dessous ; en points oranges, les pré-perçages pour la "
                                "contremarche du dessus." if P.ep_contremarche > 0 else ""), st['p']))
        cells = []
        for m in range(1, E.n):
            Lc, kinds, bands, groove, holes = E.tread_local(m); an = E.angles(Lc)
            xs = [p[0] for p in Lc]; ys = [p[1] for p in Lc]
            world = (min(xs)-8, min(ys)-8, max(xs)+8, max(ys)+8)
            def draw_tread(c, T, s, Lc=Lc, kinds=kinds, bands=bands, groove=groove, holes=holes):
                poly_path(c, T, Lc, fill=WOOD, stroke=None)
                for b in bands: poly_path(c, T, b, fill=BAND, stroke=None)
                if groove: poly_path(c, T, groove, fill=None, stroke=NEZ, width=0.8, dash=(2, 1.5))
                for hx, hy in holes:
                    X0, Y0_ = T(hx, hy); c.setFillColor(NEZ); c.circle(X0, Y0_, 1.3, stroke=0, fill=1)
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

        # --- contremarches
        if E.RISERS:
            story.append(PageBreak()); story.append(Anchor("contremarches", pages)); story.append(Paragraph("Les contremarches", st['h2']))
            story.append(Paragraph(
                f"Chaque contremarche est un panneau plan de {fr(P.ep_contremarche)} cm d'épaisseur, vu de face côté escalier. En haut (partie "
                f"grisée), il s'engage de {fr(P.profondeur_rainure)} cm dans la rainure de la marche du dessus ; en bas, il repose sur la "
                f"languette prévue à l'arrière de la marche du dessous (voir sa fiche) et s'y visse par-dessous, aux pré-perçages indiqués "
                f"(points rouges). Le panneau est en retrait du pli des crémaillères (épaisseur plus {fr(RECUL_CREMAILLERE)} cm), avec un jeu "
                f"de {fr(JEU_LIMON)} cm de chaque côté par rapport à leurs faces : au pli exact, le bois des crémaillères ne commence, côté "
                f"marche du dessus, qu'à partir de ce pli, sans aucun appui sur l'épaisseur du panneau s'il y était posé directement.", st['p']))
            rcells = []
            for i in sorted(E.RISERS):
                L, H, Htot, holes = E.riser_local(i)
                world = (-4, -4, L+4, Htot+4)
                def draw_riser(c, T, s, L=L, H=H, Htot=Htot, holes=holes):
                    poly_path(c, T, [(0, Htot-H), (L, Htot-H), (L, Htot), (0, Htot)], fill=WOOD, stroke=INK, width=0.7)
                    if Htot > H:
                        poly_path(c, T, [(0, 0), (L, 0), (L, Htot-H), (0, Htot-H)], fill=BAND, stroke=INK, width=0.4, dash=(2, 2))
                    for hx in holes:
                        X0, Y0_ = T(hx, 0); c.setFillColor(NEZ); c.circle(X0, Y0_, 1.6, stroke=0, fill=1)
                    text(c, T, L/2, Htot+2.5, fr(L), 6.5, DIM)
                    text(c, T, L+2.5, Htot/2, fr(Htot), 6.5, DIM, anchor="start")
                fig = Fig(world, draw_riser, W/2-8*mm, 40*mm)
                niveau = "sol" if i == 0 else f"marche {i}"
                haut = "chevêtre" if i == E.n-1 else f"marche {i+1}"
                note = []
                if i == 0:
                    note.append("Pas de rainure ni de pré-perçages calculés : fixer avec deux tasseaux collés, un au sol et un sous la "
                                "face inférieure de la marche 1, contre lesquels visser la contremarche.")
                elif i == E.n-1:
                    note.append("Haut à fixer contre la face du chevêtre selon la structure du plancher (pas de perçage calculé).")
                cell = [Paragraph(f"Contremarche {i}  <font size=7 color='#5d6874'>({niveau} → {haut})</font>", st['h3']), fig, Spacer(1, 2),
                        Paragraph(f"Panneau {math.ceil(L)} × {math.ceil(Htot)} × {fr(P.ep_contremarche)} cm. " + " ".join(note), st['small'])]
                rcells.append(cell)
            rgrid = [rcells[i:i+2] for i in range(0, len(rcells), 2)]
            if rgrid and len(rgrid[-1]) == 1: rgrid[-1].append("")
            for row in rgrid:
                t = Table([row], colWidths=[W/2, W/2], hAlign='LEFT')
                t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOX', (0, 0), (0, 0), 0.3, RULE),
                                       ('BOX', (1, 0), (1, 0), 0.3 if row[1] != "" else 0, RULE),
                                       ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                                       ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
                story.append(t); story.append(Spacer(1, 5))

        return story

    def build_doc(target, pages):
        doc = BaseDocTemplate(target, pagesize=A4, title=f"Escalier quart tournant à {sens}", author="escalier_quart_tournant.py")
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
        doc.build(make_story(pages))

    # premier passage (dans un flux jeté) pour connaître le numéro de page de chaque section,
    # puis second passage pour de bon : le sommaire peut alors les afficher
    pages = {}
    build_doc(io.BytesIO(), pages)
    build_doc(path, pages)
