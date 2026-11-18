# -*- coding: utf-8 -*-
"""Dibuja los autómatas como SVG a partir de sus tablas.

Cada nodo y cada flecha salen del mismo diccionario que ejecuta el juego
(automatas.py): lo que se ve moverse en pantalla es el autómata del informe.
Corre en MicroPython y en CPython (solo usa math y cadenas).
"""
import math

R_NODO = 24
R_FINAL = 30


def _limpio(q):
    return q.replace("-", "m").replace("+", "p")


def id_nodo(q, pref="a"):
    return "%s-n-%s" % (pref, _limpio(q))


def id_arista(de, a, pref="a"):
    return "%s-e-%s-%s" % (pref, _limpio(de), _limpio(a))


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _bezier(p0, c, p1, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0],
            u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1])


def _unit(dx, dy):
    L = math.sqrt(dx * dx + dy * dy) or 1.0
    return dx / L, dy / L


def _dist_min(punto, p0, c, p1):
    m = 1e9
    for i in range(1, 20):
        x, y = _bezier(p0, c, p1, i / 20.0)
        d = math.sqrt((x - punto[0]) ** 2 + (y - punto[1]) ** 2)
        if d < m:
            m = d
    return m


def _f(v):
    return "%.1f" % v


def _lugar_etiqueta(s, c, e, nx, ny, pos, radio, puestas):
    """Busca sobre la flecha un lugar para la etiqueta que no pise nodos ni
    otras etiquetas. Prueba primero el medio y del lado de la curvatura."""
    mejor, mejor_puntaje = None, -1e9
    for t in (0.5, 0.42, 0.58, 0.34, 0.66, 0.27, 0.73):
        bx, by = _bezier(s, c, e, t)
        for lado in (1, -1):
            x, y = bx + nx * 11 * lado, by + ny * 11 * lado
            d_nodo = min([math.sqrt((x - p[0]) ** 2 + (y - p[1]) ** 2) - radio[q]
                          for q, p in pos.items()])
            d_etq = min([math.sqrt((x - a) ** 2 + (y - b) ** 2) for a, b in puestas] or [99])
            puntaje = min(d_nodo - 8, d_etq - 18) - abs(t - 0.5) * 6 - (0 if lado == 1 else 2)
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = (x, y), puntaje
            if d_nodo > 10 and d_etq > 20 and t == 0.5 and lado == 1:
                return x, y
    return mejor


def _aristas(transiciones):
    """transiciones: lista de (de, a, etiqueta). Agrupa las de igual (de, a)."""
    grupos, orden = {}, []
    for de, a, etq in transiciones:
        clave = (de, a)
        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)
        grupos[clave].append(etq)
    return [(de, a, grupos[(de, a)]) for de, a in orden]


def _svg(pref, pos, transiciones, inicial, finales, titulo, sep_etq=", ", r_nodo=R_NODO, ancho_char=4.8):
    radio = {}
    for q in pos:
        radio[q] = R_FINAL if q in finales else r_nodo
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    # caja del dibujo: nodos + etiquetas (se amplía más abajo)
    caja = [min(xs) - 70, min(ys) - 40, max(xs) + 40, max(ys) + 40]

    def _incluir(x, y, ancho):
        caja[0] = min(caja[0], x - ancho - 8)
        caja[1] = min(caja[1], y - 16)
        caja[2] = max(caja[2], x + ancho + 8)
        caja[3] = max(caja[3], y + 16)

    pares = set((de, a) for de, a, _ in transiciones)
    partes = []
    partes.append(None)   # cabecera <svg>, se completa al final con la caja
    partes.append('<defs>'
                  '<marker id="%s-flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                  'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                  'class="punta"/></marker>'
                  '<marker id="%s-flecha-activa" viewBox="0 0 10 10" refX="9" refY="5" '
                  'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                  '<path d="M0,0 L10,5 L0,10 z" class="punta-activa"/></marker>'
                  '</defs>' % (pref, pref))

    capa_aristas, capa_etq, puestas = [], [], []
    for de, a, etqs in _aristas(transiciones):
        p0, p1 = pos[de], pos[a]
        r0, r1 = radio[de], radio[a]
        texto = sep_etq.join(etqs)
        eid = id_arista(de, a, pref)
        if de == a:
            ux, uy = _unit(p0[0] - cx, p0[1] - cy)
            if ux == 0 and uy == 0:
                ux, uy = 0.0, -1.0
            ang = math.atan2(uy, ux)
            s = (p0[0] + r0 * math.cos(ang - 0.5), p0[1] + r0 * math.sin(ang - 0.5))
            e = (p0[0] + (r0 + 2) * math.cos(ang + 0.5), p0[1] + (r0 + 2) * math.sin(ang + 0.5))
            c1 = (p0[0] + (r0 + 48) * math.cos(ang - 0.62), p0[1] + (r0 + 48) * math.sin(ang - 0.62))
            c2 = (p0[0] + (r0 + 48) * math.cos(ang + 0.62), p0[1] + (r0 + 48) * math.sin(ang + 0.62))
            d = "M%s,%s C%s,%s %s,%s %s,%s" % (_f(s[0]), _f(s[1]), _f(c1[0]), _f(c1[1]),
                                               _f(c2[0]), _f(c2[1]), _f(e[0]), _f(e[1]))
            lx, ly = p0[0] + (r0 + 50) * ux, p0[1] + (r0 + 50) * uy
        else:
            mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
            nx, ny = _unit(-(p1[1] - p0[1]), p1[0] - p0[0])
            if (a, de) in pares:
                candidatos = [48, 84, 124, 164]
            else:
                candidatos = [0, 46, -46, 90, -90, 140, -140, 190, -190]
            off = candidatos[-1]
            for o in candidatos:
                c = (mx + nx * o, my + ny * o)
                libre = True
                for q, pq in pos.items():
                    if q == de or q == a:
                        continue
                    if _dist_min(pq, p0, c, p1) < radio[q] + 12:
                        libre = False
                        break
                if libre:
                    off = o
                    break
            c = (mx + nx * off, my + ny * off)
            u0 = _unit(c[0] - p0[0], c[1] - p0[1])
            u1 = _unit(c[0] - p1[0], c[1] - p1[1])
            s = (p0[0] + u0[0] * r0, p0[1] + u0[1] * r0)
            e = (p1[0] + u1[0] * (r1 + 2), p1[1] + u1[1] * (r1 + 2))
            d = "M%s,%s Q%s,%s %s,%s" % (_f(s[0]), _f(s[1]), _f(c[0]), _f(c[1]), _f(e[0]), _f(e[1]))
            lado = 1 if off >= 0 else -1
            lx, ly = _lugar_etiqueta(s, c, e, nx * lado, ny * lado, pos, radio, puestas)
        capa_aristas.append(
            '<g class="arista" id="%s" data-de="%s" data-a="%s">'
            '<path id="%s-p" d="%s" pathLength="1" marker-end="url(#%s-flecha)"/></g>'
            % (eid, de, a, eid, d, pref))
        puestas.append((lx, ly))
        _incluir(lx, ly, ancho_char * len(texto))
        capa_etq.append('<text class="etq" id="%s-t" x="%s" y="%s">%s</text>'
                        % (eid, _f(lx), _f(ly), _esc(texto)))

    capa_nodos = []
    for q, (x, y) in pos.items():
        r = radio[q]
        clases = "nodo"
        if q in finales:
            clases += " final"
        if q == inicial:
            clases += " inicial"
        extra = ""
        if q in finales:
            extra = '<circle class="anillo" cx="%s" cy="%s" r="%s"/>' % (_f(x), _f(y), _f(r - 5))
        flecha = ""
        if q == inicial:
            flecha = ('<path class="entrada" d="M%s,%s L%s,%s" marker-end="url(#%s-flecha)"/>'
                      % (_f(x - r - 40), _f(y), _f(x - r - 3), _f(y), pref))
        capa_nodos.append(
            '<g class="%s" id="%s" data-estado="%s">%s<circle class="disco" cx="%s" cy="%s" r="%s"/>'
            '%s<text class="nombre" x="%s" y="%s">%s</text></g>'
            % (clases, id_nodo(q, pref), q, flecha, _f(x), _f(y), r, extra, _f(x), _f(y), _esc(q)))

    partes.append('<g class="capa-aristas">%s</g>' % "".join(capa_aristas))
    partes.append('<g class="capa-etiquetas">%s</g>' % "".join(capa_etq))
    partes.append('<g class="capa-nodos">%s</g>' % "".join(capa_nodos))
    partes.append('<g class="capa-ficha" id="%s-ficha"></g>' % pref)
    partes.append("</svg>")
    for q, (x, y) in pos.items():
        _incluir(x, y, radio[q] + 4)
    partes[0] = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s %s %s %s" '
                 'class="grafo" id="%s-svg" role="img" aria-label="%s">'
                 % (_f(caja[0]), _f(caja[1]), _f(caja[2] - caja[0]), _f(caja[3] - caja[1]),
                    pref, _esc(titulo)))
    return "".join(partes)


def svg_afd(tabla, pos, inicial, finales):
    trans = []
    for q in pos:
        for c in ("g", "f"):
            trans.append((q, tabla[q][c], c))
    return _svg("a", pos, trans, inicial, finales,
                "AFD de la tanda con %d estados" % len(tabla))


def svg_mealy(mealy, pos, inicial):
    trans = []
    for q in pos:
        for c in ("I", "C", "D"):
            nuevo, salida = mealy[q][c]
            trans.append((q, nuevo, "%s;%s" % (c, salida)))
    return _svg("m", pos, trans, inicial, (), "Máquina de Mealy del arquero", sep_etq="  ", r_nodo=32, ancho_char=7.5)
