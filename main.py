# -*- coding: utf-8 -*-
"""Interfaz del juego. Conecta la página con automatas.py.

Orden de cada penal (sección 10 del informe):
  1. se compara el remate con la predicción del arquero  -> g o f
  2. esa letra entra al AFD (estado siguiente)
  3. se actualizan el marcador y los grafos
  4. si pateó Argentina, la Mealy lee el remate y emite la próxima predicción

El azar (lado de la PC y primer salto del arquero) se genera acá, afuera de los
autómatas, con Math.random del navegador.
"""
from pyscript import document, window
from pyscript.ffi import create_proxy

import automatas as A
import grafo

EQUIPO = {"A": "Argentina", "B": "Francia"}
NOMBRE_LADO = {"I": "a la izquierda", "C": "al centro", "D": "a la derecha"}
TECLAS = {"i": "I", "c": "C", "d": "D", "arrowleft": "I", "arrowright": "D",
          "arrowdown": "C", "arrowup": "C"}

# Destino de la pelota desde el punto penal (unidades del SVG de la escena).
DESTINO_GOL = {"I": (-150, -212, 0.58), "C": (0, -228, 0.56), "D": (150, -212, 0.58)}
DESTINO_ATAJADA = {"I": (-128, -170, 0.66), "C": (0, -168, 0.64), "D": (128, -170, 0.66)}
REBOTE = {"I": (-300, -90, 0.8), "C": (90, -40, 0.9), "D": (300, -90, 0.8)}

# Ejemplos de las Tablas 3 y 5 del informe (3 penales) y equivalentes para 5.
PRESETS = {
    3: [("gfgf", "Tabla 5: acepta, gana A"), ("fgfg", "Tabla 5: acepta, gana B"),
        ("gggggf", "Tabla 5: acepta, 3 a 2"), ("ffffffgf", "Tabla 5: acepta, muerte súbita"),
        ("ggggggfg", "Tabla 3: gana B en muerte súbita"), ("", "Tabla 5: λ, rechaza"),
        ("gggggg", "Tabla 5: rechaza, 3 a 3"), ("gfgfg", "Tabla 5: rechaza, penal de más"),
        ("GFGF", "Tabla 5: rechaza, fuera de Σ")],
    5: [("gfgfgf", "gana A 3 a 0"), ("fgfgfg", "gana B 0 a 3"),
        ("gggggggggf", "gana A 5 a 4"), ("ffffffffffgf", "muerte súbita"),
        ("", "λ, rechaza"), ("gggggggggg", "rechaza, 5 a 5"),
        ("gfgfgfg", "rechaza, penal de más"), ("GFGF", "rechaza, fuera de Σ")],
}
PRESETS_MEALY = [("IDID", "Tabla 8: salida IIDI"), ("ICDICD", "salida IICDIC, no ataja ninguno"),
                 ("CCCC", "siempre al centro"), ("IIDD", "")]


# ---------------------------------------------------------------------------
# Utilidades de la página
# ---------------------------------------------------------------------------
def el(i):
    return document.getElementById(i)


def todos(selector):
    lista = document.querySelectorAll(selector)
    return [lista.item(i) for i in range(lista.length)]


def al_azar():
    """Lado al azar. Math.random del navegador: no se repite entre partidas."""
    n = int(window.Math.random() * 3)
    return "ICD"[min(n, 2)]


def reportar(e):
    try:
        window.console.error("[penales] " + str(e))
    except Exception:
        pass


class Reloj:
    """setTimeout con cancelación en bloque y generación (evita callbacks viejos)."""

    def __init__(self):
        self.ids = []
        self.gen = 0

    def despues(self, ms, fn):
        gen = self.gen

        def _f(*_):
            if gen != self.gen:
                return
            try:
                fn()
            except Exception as e:
                reportar(e)
                S.bloqueado = False
                actualizar_turno()
        self.ids.append(window.setTimeout(create_proxy(_f), int(ms)))

    def cancelar(self):
        self.gen += 1
        for i in self.ids:
            window.clearTimeout(i)
        self.ids = []


def manejador(fn):
    """Envuelve un handler de evento: nunca deja una excepción suelta."""
    def _h(ev):
        try:
            fn(ev)
        except Exception as e:
            reportar(e)
    return create_proxy(_h)


# ---------------------------------------------------------------------------
# Estado de la interfaz
# ---------------------------------------------------------------------------
class Estado:
    def __init__(self):
        self.modo = "jugar"          # jugar | simular | probar
        self.N = 3
        self.tanda = A.Tanda(3)
        self.bloqueado = False       # True mientras corre la animación de un penal
        self.simulando = False
        self.vel = 1.0
        self.reducido = False
        self.afd_marcas = []         # (id, clase) puestos en el SVG del AFD
        self.mealy_marcas = []
        self.prueba = {"tipo": "afd", "palabra": "", "i": 0, "res": None, "auto": False}


S = Estado()
R = Reloj()


def factor():
    base = S.vel if S.modo == "simular" else 1.0
    return base * (0.15 if S.reducido else 1.0)


def aplicar_factor():
    document.documentElement.style.setProperty("--t", str(factor()))


# ---------------------------------------------------------------------------
# Grafos: marcar estados y transiciones
# ---------------------------------------------------------------------------
def _marcar(lista, eid, clase):
    nodo = el(eid)
    if nodo is not None:
        nodo.classList.add(clase)
        lista.append((eid, clase))


def _limpiar(lista, pref):
    for eid, clase in lista:
        nodo = el(eid)
        if nodo is not None:
            nodo.classList.remove(clase)
            if clase == "activa" and not eid.endswith("-t"):
                p = el(eid + "-p")
                if p is not None:
                    p.setAttribute("marker-end", "url(#%s-flecha)" % pref)
    del lista[:]


def _quitar_clase(lista, clase, pref):
    resto = []
    for eid, c in lista:
        if c == clase:
            nodo = el(eid)
            if nodo is not None:
                nodo.classList.remove(c)
                if c == "activa" and not eid.endswith("-t"):
                    p = el(eid + "-p")
                    if p is not None:
                        p.setAttribute("marker-end", "url(#%s-flecha)" % pref)
        else:
            resto.append((eid, c))
    lista[:] = resto


def _clase_estado(q):
    if q == A.GANA_A:
        return "gana-a"
    if q == A.GANA_B:
        return "gana-b"
    if q == A.SUMIDERO:
        return "sumidero"
    return None


def afd_reiniciar():
    _limpiar(S.afd_marcas, "a")
    _marcar(S.afd_marcas, grafo.id_nodo(A.INICIAL), "actual")
    el("a-ficha").innerHTML = ""
    chip = el("estado-chip")
    chip.textContent = A.INICIAL
    chip.classList.remove("gana-a")
    chip.classList.remove("gana-b")


def afd_paso(de, a, animar=True):
    """Resalta la transición f(de, x) = a y deja 'a' como estado actual."""
    _quitar_clase(S.afd_marcas, "actual", "a")
    _quitar_clase(S.afd_marcas, "activa", "a")
    _quitar_clase(S.afd_marcas, "pulso", "a")
    eid = grafo.id_arista(de, a)
    _marcar(S.afd_marcas, grafo.id_nodo(de), "visitado")
    _marcar(S.afd_marcas, eid, "recorrida")
    _marcar(S.afd_marcas, eid + "-t", "recorrida")
    _marcar(S.afd_marcas, eid, "activa")
    _marcar(S.afd_marcas, eid + "-t", "activa")
    p = el(eid + "-p")
    if p is not None:
        p.setAttribute("marker-end", "url(#a-flecha-activa)")
    _marcar(S.afd_marcas, grafo.id_nodo(a), "actual")
    c = _clase_estado(a)
    if c:
        _marcar(S.afd_marcas, grafo.id_nodo(a), c)
    if animar:
        _marcar(S.afd_marcas, grafo.id_nodo(a), "pulso")
        mover_ficha("a", eid)
    chip = el("estado-chip")
    chip.textContent = a
    chip.classList.toggle("gana-a", a == A.GANA_A)
    chip.classList.toggle("gana-b", a == A.GANA_B)


def mover_ficha(pref, eid):
    """Una ficha recorre la flecha (SMIL animateMotion sobre el mismo path)."""
    if S.reducido:
        return
    capa = el(pref + "-ficha")
    if capa is None:
        return
    dur = 0.55 * factor()
    capa.innerHTML = ('<circle r="7" class="ficha"><animateMotion id="%s-mov" dur="%.2fs" '
                      'fill="freeze" begin="indefinite"><mpath href="#%s-p"/></animateMotion>'
                      '</circle>' % (pref, dur, eid))
    mov = el(pref + "-mov")
    if mov is not None:
        mov.beginElement()
    R.despues(dur * 1000 + 60, lambda: _vaciar(capa))


def _vaciar(capa):
    capa.innerHTML = ""


def mealy_reiniciar():
    _limpiar(S.mealy_marcas, "m")
    _marcar(S.mealy_marcas, grafo.id_nodo(A.MEALY_INICIAL, "m"), "actual")
    el("m-ficha").innerHTML = ""


def mealy_paso(de, a, animar=True):
    _quitar_clase(S.mealy_marcas, "actual", "m")
    _quitar_clase(S.mealy_marcas, "activa", "m")
    _quitar_clase(S.mealy_marcas, "pulso", "m")
    eid = grafo.id_arista(de, a, "m")
    _marcar(S.mealy_marcas, eid, "activa")
    _marcar(S.mealy_marcas, eid + "-t", "activa")
    p = el(eid + "-p")
    if p is not None:
        p.setAttribute("marker-end", "url(#m-flecha-activa)")
    _marcar(S.mealy_marcas, grafo.id_nodo(a, "m"), "actual")
    if animar:
        _marcar(S.mealy_marcas, grafo.id_nodo(a, "m"), "pulso")
        mover_ficha("m", eid)


def dibujar_afd():
    v = A.VERSIONES[S.N]
    el("afd-host").innerHTML = grafo.svg_afd(v["tabla"], v["pos"], A.INICIAL, A.FINALES)
    el("afd-sub").textContent = "AFD de %d estados, %d penales por equipo" % (v["estados"], S.N)
    S.afd_marcas = []
    afd_reiniciar()


def dibujar_mealy():
    el("mealy-host").innerHTML = grafo.svg_mealy(A.MEALY, A.POS_MEALY, A.MEALY_INICIAL)
    S.mealy_marcas = []
    mealy_reiniciar()


# ---------------------------------------------------------------------------
# Cintas, marcador y registro
# ---------------------------------------------------------------------------
def celda(simbolo, clases):
    li = document.createElement("li")
    li.className = clases
    li.textContent = simbolo
    return li


def cinta_afd_reset():
    c = el("cinta-afd")
    c.innerHTML = ""
    c.appendChild(celda("", "cabezal"))


def cinta_afd_agregar(simbolo, equipo):
    c = el("cinta-afd")
    cab = c.lastElementChild
    li = celda(simbolo, "s-%s pos-%s nuevo" % (simbolo, equipo.lower()))
    c.insertBefore(li, cab)
    if S.tanda.terminada():
        cab.remove()


def cintas_mealy_reset():
    el("cinta-in").innerHTML = ""
    el("cinta-tiro").innerHTML = ""
    el("cinta-out").innerHTML = ""


def cintas_mealy_agregar(j):
    """Columna k: tu remate k, adónde se tiró el arquero en ese remate (la salida
    del remate k-1, o el azar en el primero) y la salida que emitió para el k+1."""
    el("cinta-in").appendChild(celda(j["remate"], "nuevo"))
    clases = "nuevo"
    if j["fuente"] == "azar":
        clases += " azar"
    if j["simbolo"] == "f":
        clases += " atajo"
    tiro = celda(j["arquero"], clases)
    tiro.title = "al azar (todavía no había predicción)" if j["fuente"] == "azar" else (
        "salida del remate anterior" + (": atajó" if j["simbolo"] == "f" else ": gol"))
    el("cinta-tiro").appendChild(tiro)
    el("cinta-out").appendChild(celda(j["salida"], "nuevo"))


def texto_prediccion(recien=False):
    """Explica la última flecha de la Mealy. La predicción la da la FLECHA
    (remate ; salida), no el estado de llegada: por eso puede estar en qD y
    predecir I. 'recien' = se llama justo después de un remate de Argentina."""
    t = S.tanda
    if t.prediccion is None:
        if t.terminada():
            return "Tanda terminada."
        return ("Primer remate: la Mealy está en q0 y todavía no predijo nada, "
                "así que el arquero se tira al azar.")
    ult = None
    for j in t.historial:
        if j["equipo"] == "A":
            ult = j
    flecha = ("Leyó tu remate <b>%s</b> con la flecha %s → %s (%s ; %s) y emitió <b>%s</b>"
              % (ult["remate"], ult["mealy_de"], ult["mealy_a"], ult["remate"], ult["salida"], ult["salida"]))
    aclara = ""
    if ult["mealy_a"][1:] != ult["salida"]:
        aclara = ('<span class="aclara">La predicción sale de la flecha, no del estado: por eso está en %s '
                  'y predice %s.</span>' % (ult["mealy_a"], ult["salida"]))
    if t.terminada():
        return flecha + ". Tanda terminada." + aclara
    if t.turno() == "B" and not recien:
        return ("Patea Francia: la Mealy no lee este penal y se queda en %s. %s: en tu próximo "
                "remate se tira %s.%s" % (t.estado_mealy, flecha, NOMBRE_LADO[t.prediccion], aclara))
    return "%s: en tu próximo remate se tira %s.%s" % (flecha, NOMBRE_LADO[t.prediccion], aclara)


def marcador_dibujar(nueva=None):
    t, N = S.tanda, S.N
    for eq, sid, gid in (("A", "serie-a", "goles-a"), ("B", "serie-b", "goles-b")):
        res = t.resultados(eq)
        ol = el(sid)
        ol.innerHTML = ""
        total = max(N, len(res))
        if t.muerte_subita() and not t.terminada() and len(res) == total:
            total += 1                            # lugar para el próximo de muerte súbita
        for i in range(total):
            clases = []
            if i < len(res):
                clases.append(res[i])
            if i >= N:
                clases.append("extra")
            if nueva is not None and nueva[0] == eq and nueva[1] == i:
                clases.append("nuevo")
            li = document.createElement("li")
            li.className = " ".join(clases)
            if i < len(res):
                li.setAttribute("aria-label", "penal %d: %s" % (i + 1, "gol" if res[i] == "g" else "no fue gol"))
            ol.appendChild(li)
        el(gid).textContent = str(t.goles[0 if eq == "A" else 1])


def registro_reset():
    if S.modo == "probar":
        texto = "Todavía no se leyó ningún símbolo."
    else:
        texto = "Todavía no se pateó ningún penal."
    el("registro").innerHTML = '<li class="vacio">%s</li>' % texto


def registro_paso_palabra(k, simbolo, de, a):
    """En Probar palabra: un renglón por símbolo leído (posición impar = A, par = B)."""
    ol = el("registro")
    if ol.firstElementChild is not None and ol.firstElementChild.classList.contains("vacio"):
        ol.innerHTML = ""
    equipo = "a" if k % 2 == 0 else "b"
    quien = "ARG" if equipo == "a" else "FRA"
    lectura = "lee %s (%s)" % (simbolo, "gol" if simbolo == "g" else "no fue gol")
    li = document.createElement("li")
    li.innerHTML = ('<span class="n">%d</span><span class="quien %s">%s</span>'
                    '<span>%s</span><span class="tr">%s <b>%s</b> %s</span>'
                    % (k + 1, equipo, quien, lectura, de, simbolo, a))
    ol.appendChild(li)
    ol.scrollTop = ol.scrollHeight


def registro_agregar(j):
    ol = el("registro")
    if ol.firstElementChild is not None and ol.firstElementChild.classList.contains("vacio"):
        ol.innerHTML = ""
    li = document.createElement("li")
    if j["equipo"] == "A":
        quien = "ARG"
        if j["fuente"] == "azar":
            arq = "arquero %s (azar)" % j["arquero"]
        else:
            arq = "arquero %s (Mealy)" % j["arquero"]
        jugada = "patea %s, %s" % (j["remate"], arq)
        if S.modo == "jugar":
            jugada = "pateás %s, %s" % (j["remate"], arq)
    else:
        quien = "FRA"
        if S.modo == "jugar":
            jugada = "patea %s, te tirás %s" % (j["remate"], j["arquero"])
        else:
            jugada = "patea %s, arquero %s" % (j["remate"], j["arquero"])
    li.innerHTML = ('<span class="n">%d</span><span class="quien %s">%s</span>'
                    '<span>%s</span><span class="tr">%s <b>%s</b> %s</span>'
                    % (j["n"], j["equipo"].lower(), quien, jugada, j["afd_de"], j["simbolo"], j["afd_a"]))
    ol.appendChild(li)
    ol.scrollTop = ol.scrollHeight


# ---------------------------------------------------------------------------
# Turno y consignas
# ---------------------------------------------------------------------------
def actualizar_turno():
    t = S.tanda
    terminada = t.terminada()
    turno = t.turno()
    escena = el("escena")
    escena.classList.toggle("ataja-fra", turno == "A")
    escena.classList.toggle("ataja-arg", turno == "B")
    el("equipo-a").classList.toggle("patea", turno == "A" and not terminada and S.modo != "probar")
    el("equipo-b").classList.toggle("patea", turno == "B" and not terminada and S.modo != "probar")

    fase = el("fase")
    if S.modo == "probar":
        fase.textContent = "Probar palabra"
        fase.classList.remove("subita")
    elif terminada:
        fase.textContent = "Final"
        fase.classList.remove("subita")
    elif t.muerte_subita():
        fase.textContent = "Muerte súbita, penal %d" % t.numero()
        fase.classList.add("subita")
    else:
        fase.textContent = "Penal %d de %d" % (t.numero(), 2 * S.N)
        fase.classList.remove("subita")

    zonas = el("zonas")
    activas = S.modo == "jugar" and not terminada and not S.bloqueado
    zonas.classList.toggle("apagadas", not activas)
    zonas.classList.toggle("ocultas", S.modo != "jugar")
    for b in todos(".zona"):
        lado = b.getAttribute("data-lado")
        b.disabled = not activas
        verbo = "Patear" if turno == "A" else "Tirarte"
        b.setAttribute("aria-label", "%s %s (%s)" % (verbo, NOMBRE_LADO[lado], lado))

    consigna = el("consigna")
    if S.modo == "probar":
        consigna.textContent = ""
    elif terminada:
        consigna.textContent = "Terminó la tanda: gana %s." % EQUIPO[t.ganador()]
    elif S.modo == "simular":
        if S.simulando:
            consigna.textContent = "Simulando: patea %s." % EQUIPO[turno]
        else:
            consigna.textContent = "Simulación en pausa. Próximo: patea %s." % EQUIPO[turno]
    elif S.bloqueado:
        pass
    elif turno == "A":
        consigna.innerHTML = "Patea Argentina. Elegí dónde patear: <span class=\"lado\">I, C o D</span>."
    else:
        consigna.innerHTML = "Patea Francia. Elegí dónde tirarte: <span class=\"lado\">I, C o D</span>."

    el("prediccion").innerHTML = texto_prediccion()
    tapar = el("tapar").checked and S.modo == "jugar" and turno == "A" and not terminada
    el("pz-mealy").classList.toggle("tapado", tapar)

    bsim = el("btn-sim")
    if terminada:
        bsim.textContent = "Simular otra tanda"
    elif S.simulando:
        bsim.textContent = "Pausar"
    else:
        bsim.textContent = "Simular la tanda" if len(t.palabra) == 0 else "Seguir"
    el("btn-paso-sim").disabled = terminada or S.simulando or S.bloqueado


# ---------------------------------------------------------------------------
# La escena: pelota, arquero, cartel
# ---------------------------------------------------------------------------
def escena_reset():
    arq = el("arquero")
    for lado in "ICD":
        arq.classList.remove("tira-" + lado)
    pel = el("pelota")
    pel.style.transform = ""
    pel.style.opacity = "1"
    sp = el("sombra-pelota")
    sp.style.transform = ""
    sp.style.opacity = ""
    c = el("cartel")
    c.className = "cartel"
    el("red").classList.remove("sacude")


def escena_tiro(j):
    dx, dy, esc = (DESTINO_GOL if j["simbolo"] == "g" else DESTINO_ATAJADA)[j["remate"]]
    pel = el("pelota")
    pel.style.transform = "translate(%dpx, %dpx) scale(%.2f)" % (dx, dy, esc)
    el("sombra-pelota").style.transform = "translate(%dpx, %dpx) scale(%.2f)" % (dx, dy * 0.42, esc)
    el("sombra-pelota").style.opacity = "0.15"
    R.despues(90 * factor(), lambda: el("arquero").classList.add("tira-" + j["arquero"]))


def escena_resultado(j):
    c = el("cartel")
    if j["simbolo"] == "g":
        el("red").classList.add("sacude")
        if j["equipo"] == "A":
            c.textContent = "¡Gol de Argentina!"
            c.className = "cartel gol-a ver"
        else:
            c.textContent = "Gol de Francia"
            c.className = "cartel gol-b ver"
    else:
        dx, dy, esc = REBOTE[j["remate"]]
        pel = el("pelota")
        pel.style.transform = "translate(%dpx, %dpx) scale(%.2f)" % (dx, dy, esc)
        pel.style.opacity = "0"
        if j["equipo"] == "A":
            c.textContent = "Lo atajó el arquero"
        else:
            c.textContent = "¡Atajaste!"
        c.className = "cartel atajada ver"


def letra_vuela(simbolo, al_llegar):
    """La letra g/f sale del cartel y cae en la cinta del AFD."""
    if S.reducido:
        al_llegar()
        return
    origen = el("cartel").getBoundingClientRect()
    destino = el("cinta-afd").lastElementChild
    if destino is None:
        al_llegar()
        return
    d = destino.getBoundingClientRect()
    lv = el("letra-vuela")
    lv.className = "letra-vuela"
    lv.textContent = simbolo
    x0 = origen.left + origen.width / 2 - 23
    y0 = origen.top + origen.height / 2
    lv.style.transform = "translate(%dpx, %dpx) scale(1.2)" % (x0, y0)
    lv.style.opacity = "1"
    lv.getBoundingClientRect()                     # fuerza el estado inicial
    lv.className = "letra-vuela vuela"
    x1 = d.left + d.width / 2 - 23
    y1 = d.top + d.height / 2 - 26
    lv.style.transform = "translate(%dpx, %dpx) scale(0.62)" % (x1, y1)

    def fin():
        lv.style.opacity = "0"
        lv.className = "letra-vuela"
        al_llegar()
    R.despues(560 * factor(), fin)


# ---------------------------------------------------------------------------
# Un penal completo
# ---------------------------------------------------------------------------
def jugar_penal(remate_o_salto):
    """Penal del modo Jugar. El usuario eligió un lado."""
    t = S.tanda
    if S.modo != "jugar" or S.bloqueado or t.terminada():
        return
    if t.turno() == "A":
        j = t.patear_a(remate_o_salto, al_azar())
    else:
        j = t.patear_b(al_azar(), remate_o_salto)
    animar_penal(j)


def simular_penal():
    t = S.tanda
    if S.bloqueado or t.terminada():
        return
    if t.turno() == "A":
        j = t.patear_a(al_azar(), al_azar())
    else:
        j = t.patear_b(al_azar(), al_azar())
    animar_penal(j)


def bloquear_controles():
    """Durante la animación solo se bloquean los controles: el resto de la
    pantalla sigue mostrando el estado ANTERIOR hasta que la letra llega al AFD."""
    el("zonas").classList.add("apagadas")
    for b in todos(".zona"):
        b.disabled = True
    el("btn-paso-sim").disabled = True


def animar_penal(j):
    S.bloqueado = True
    aplicar_factor()
    f = factor()
    bloquear_controles()
    if S.modo == "jugar":
        if j["equipo"] == "A":
            el("consigna").innerHTML = 'Pateaste <span class="lado">%s</span>…' % NOMBRE_LADO[j["remate"]]
        else:
            el("consigna").innerHTML = 'Te tiraste <span class="lado">%s</span>…' % NOMBRE_LADO[j["arquero"]]
    elif S.modo == "simular":
        el("consigna").textContent = "Patea %s…" % EQUIPO[j["equipo"]]
    escena_tiro(j)
    R.despues(600 * f, lambda: escena_resultado(j))

    def letra():
        letra_vuela(j["simbolo"], lambda: aplicar_en_modelo(j))
    R.despues(980 * f, letra)


def aplicar_en_modelo(j):
    """Se ve en la pizarra lo que ya hizo automatas.py."""
    t = S.tanda
    cinta_afd_agregar(j["simbolo"], j["equipo"])
    afd_paso(j["afd_de"], j["afd_a"])
    if j["equipo"] == "A":
        mealy_paso(j["mealy_de"], j["mealy_a"])
        cintas_mealy_agregar(j)
        el("prediccion").innerHTML = texto_prediccion(recien=True)
    eq = j["equipo"]
    marcador_dibujar((eq, len(t.resultados(eq)) - 1))
    registro_agregar(j)
    el("consigna").textContent = describir(j)
    R.despues(700 * factor(), lambda: cerrar_penal(j))


def describir(j):
    if j["equipo"] == "A":
        if j["simbolo"] == "g":
            base = "Gol: pateaste %s y el arquero se tiró %s." % (NOMBRE_LADO[j["remate"]], NOMBRE_LADO[j["arquero"]])
        else:
            base = "Atajado: el arquero se tiró %s, como pateaste." % NOMBRE_LADO[j["arquero"]]
        if j["fuente"] == "azar":
            base += " (Primer remate: el arquero saltó al azar.)"
        return base
    if j["simbolo"] == "g":
        return "Gol de Francia: pateó %s y te tiraste %s." % (NOMBRE_LADO[j["remate"]], NOMBRE_LADO[j["arquero"]])
    return "¡Atajaste! Francia pateó %s." % NOMBRE_LADO[j["remate"]]


def cerrar_penal(j):
    escena_reset()
    S.bloqueado = False
    t = S.tanda
    if t.terminada():
        S.simulando = False
        actualizar_turno()
        R.despues(550 * factor(), mostrar_campeon)
        return
    actualizar_turno()
    if S.modo == "simular" and S.simulando:
        R.despues(380 * factor(), simular_penal)


# ---------------------------------------------------------------------------
# Campeón
# ---------------------------------------------------------------------------
def mostrar_campeon():
    t = S.tanda
    g = t.ganador()
    if g is None:
        return
    cap = el("campeon")
    es_a = g == "A"
    cap.classList.toggle("fra", not es_a)
    el("campeon-foto").src = "assets/campeon_arg.jpg" if es_a else "assets/campeon_fra.jpg"
    el("campeon-foto").alt = "Festejo de la Selección %s" % ("Argentina" if es_a else "de Francia")
    el("campeon-escudo").src = "assets/escudo_arg.png" if es_a else "assets/escudo_fra.png"
    el("campeon-escudo").alt = "Escudo de %s" % EQUIPO[g]
    el("campeon-titulo").textContent = "¡%s gana la tanda!" % EQUIPO[g]
    ga, gb = t.goles
    extra = ", en muerte súbita" if len(t.palabra) > 2 * S.N else ""
    el("campeon-marcador").textContent = "Argentina %d, Francia %d%s" % (ga, gb, extra)
    el("campeon-formal").innerHTML = ("La palabra <b>%s</b> llevó al AFD a <b>%s</b> ∈ F en %d penales: "
                                      "la tanda es una palabra de L." % (t.palabra, t.estado, len(t.palabra)))
    confeti(es_a)
    cap.hidden = False
    el("btn-otra").focus()


def confeti(es_a):
    capa = el("confeti")
    if S.reducido:
        capa.innerHTML = ""
        return
    colores = ["#74ACDF", "#FFFFFF", "#F6B40E"] if es_a else ["#3D63C9", "#FFFFFF", "#E1323B"]
    partes = []
    for i in range(90):
        r = window.Math.random
        partes.append('<i style="left:%.1f%%;background:%s;--dx:%dpx;--giro:%ddeg;'
                      'animation-duration:%.2fs;animation-delay:%.2fs"></i>'
                      % (r() * 100, colores[i % 3], int(r() * 240 - 120), int(r() * 900 + 200),
                         2.6 + r() * 2.4, r() * 1.4))
    capa.innerHTML = "".join(partes)


def cerrar_campeon():
    el("campeon").hidden = True
    el("confeti").innerHTML = ""


# ---------------------------------------------------------------------------
# Reiniciar, modos y versión
# ---------------------------------------------------------------------------
def nueva_tanda():
    R.cancelar()
    S.bloqueado = False
    S.simulando = False
    S.tanda = A.Tanda(S.N)
    cerrar_campeon()
    escena_reset()
    afd_reiniciar()
    mealy_reiniciar()
    cinta_afd_reset()
    cintas_mealy_reset()
    registro_reset()
    marcador_dibujar()
    aplicar_factor()
    actualizar_turno()
    if S.modo == "probar":
        prueba_reiniciar()


def poner_segmento(selector, attr, valor):
    for b in todos(selector):
        on = b.getAttribute(attr) == valor
        b.classList.toggle("activo", on)
        b.setAttribute("aria-pressed", "true" if on else "false")


def ubicar_pizarras():
    """En Probar palabra con la Mealy, su pizarra pasa a la columna derecha."""
    mealy_a_la_derecha = S.modo == "probar" and S.prueba["tipo"] == "mealy"
    pz = el("pz-mealy")
    if mealy_a_la_derecha and pz.parentElement.id != "tablero":
        el("tablero").appendChild(pz)
    elif not mealy_a_la_derecha and pz.parentElement.id == "tablero":
        el("col-izq").appendChild(pz)
    el("pz-tanda").hidden = mealy_a_la_derecha
    el("tapar-etq").hidden = S.modo == "probar"
    document.body.classList.toggle("modo-probar", S.modo == "probar")


def cambiar_modo(modo):
    S.modo = modo
    poner_segmento(".barra [data-modo]", "data-modo", modo)
    ubicar_pizarras()
    el("escena").hidden = modo == "probar"
    el("consigna").hidden = modo == "probar"
    el("panel-simular").hidden = modo != "simular"
    el("panel-probar").hidden = modo != "probar"
    el("btn-reiniciar").hidden = modo == "probar"
    nueva_tanda()


def cambiar_version(n):
    if n == S.N:
        return
    S.N = n
    poner_segmento(".barra [data-version]", "data-version", str(n))
    dibujar_afd()
    dibujar_presets()          # los ejemplos dependen de la versión (3 o 5 penales)
    nueva_tanda()


# ---------------------------------------------------------------------------
# Modo Probar palabra
# ---------------------------------------------------------------------------
def prueba_reiniciar():
    P = S.prueba
    R.cancelar()
    P["i"] = 0
    P["res"] = None
    P["auto"] = False
    afd_reiniciar()
    mealy_reiniciar()
    el("veredicto").innerHTML = ""
    el("veredicto").className = "veredicto"
    registro_reset()
    prueba_cinta()
    if P["tipo"] == "mealy":
        prueba_tabla_mealy()
        el("prediccion").innerHTML = "En q0: el primer remate no tiene predicción."


def prueba_tipo(tipo):
    P = S.prueba
    P["tipo"] = tipo
    poner_segmento("#panel-probar [data-prueba]", "data-prueba", tipo)
    if tipo == "afd":
        el("entrada-etq").textContent = "Palabra sobre Σ = {g, f}"
        el("entrada").placeholder = "por ejemplo, gfgf"
    else:
        el("entrada-etq").textContent = "Remates sobre Σ = {I, C, D}"
        el("entrada").placeholder = "por ejemplo, IDID"
    el("tabla-mealy").hidden = tipo != "mealy"
    ubicar_pizarras()
    el("entrada").value = ""
    P["palabra"] = ""
    dibujar_presets()
    prueba_reiniciar()


def dibujar_presets():
    cont = el("presets")
    cont.innerHTML = ""
    lista = PRESETS[S.N] if S.prueba["tipo"] == "afd" else PRESETS_MEALY
    for palabra, nota in lista:
        b = document.createElement("button")
        b.type = "button"
        b.className = "preset"
        b.innerHTML = "<code>%s</code><span>%s</span>" % (palabra if palabra else "λ", nota)
        b.addEventListener("click", manejador(_preset(palabra)))
        cont.appendChild(b)


def _preset(palabra):
    def _f(ev):
        el("entrada").value = palabra
        S.prueba["palabra"] = palabra
        prueba_reiniciar()
        prueba_ejecutar()
    return _f


def prueba_calcular():
    P = S.prueba
    if P["res"] is None:
        P["palabra"] = el("entrada").value
        if P["tipo"] == "afd":
            P["res"] = A.recorrer_afd(A.VERSIONES[S.N]["tabla"], P["palabra"])
        else:
            estados, salidas, error = A.traducir_mealy(P["palabra"])
            P["res"] = {"estados": estados, "salidas": salidas, "error": error}
    return P["res"]


def prueba_cinta():
    P = S.prueba
    c = el("cinta-afd") if P["tipo"] == "afd" else el("cinta-in")
    palabra = P["palabra"]
    c.innerHTML = ""
    if P["tipo"] == "mealy":
        el("cinta-out").innerHTML = ""
        el("cinta-tiro").innerHTML = ""
    res = P["res"]
    for k in range(len(palabra)):
        clases = []
        if k < P["i"]:
            if P["tipo"] == "afd":
                clases.append("s-" + palabra[k])
                clases.append("pos-a" if k % 2 == 0 else "pos-b")
        else:
            clases.append("pendiente")
        if res is not None and res.get("error") == k and k <= P["i"]:
            clases = ["error"]
        if k == P["i"] and (res is None or res.get("error") != k):
            clases.append("cabezal")
        c.appendChild(celda(palabra[k], " ".join(clases)))
        if P["tipo"] == "mealy" and k < P["i"] and res is not None and k < len(res["salidas"]):
            if k == 0:
                tiro = celda("?", "azar")
                tiro.title = "sin predicción: depende del azar"
            else:
                tiro = celda(res["salidas"][k - 1], "atajo" if res["salidas"][k - 1] == palabra[k] else "")
            el("cinta-tiro").appendChild(tiro)
            el("cinta-out").appendChild(celda(res["salidas"][k], ""))
    if P["tipo"] == "afd" and len(palabra) == 0:
        c.appendChild(celda("λ", "cabezal"))


def prueba_paso():
    """Avanza un símbolo. Devuelve False cuando ya no hay más pasos."""
    P = S.prueba
    res = prueba_calcular()
    palabra = P["palabra"]
    error = res.get("error")
    if P["i"] >= len(palabra) or (error is not None and P["i"] >= error):
        prueba_cinta()             # marca en rojo el símbolo inválido (aunque sea el primero)
        prueba_veredicto()
        return False
    k = P["i"]
    if P["tipo"] == "afd":
        afd_paso(res["estados"][k], res["estados"][k + 1])
        registro_paso_palabra(k, palabra[k], res["estados"][k], res["estados"][k + 1])
    else:
        mealy_paso(res["estados"][k], res["estados"][k + 1])
    P["i"] = k + 1
    prueba_cinta()
    if P["tipo"] == "mealy":
        prueba_tabla_mealy()
        sal = res["salidas"][k]
        de, a = res["estados"][k], res["estados"][k + 1]
        txt = ("Leyó <b>%s</b> con la flecha %s → %s (%s ; %s) y emitió <b>%s</b>: en el remate "
               "siguiente se tira %s." % (palabra[k], de, a, palabra[k], sal, sal, NOMBRE_LADO[sal]))
        if a[1:] != sal:
            txt += ('<span class="aclara">La predicción sale de la flecha, no del estado: por eso está en %s '
                    'y predice %s.</span>' % (a, sal))
        el("prediccion").innerHTML = txt
    if P["i"] >= len(palabra) or res.get("error") == P["i"]:
        prueba_veredicto()
        return False
    return True


def prueba_ejecutar():
    P = S.prueba
    if P["auto"]:
        return
    if P["res"] is not None and P["i"] >= len(P["palabra"]):
        prueba_reiniciar()
    prueba_calcular()
    P["auto"] = True
    if len(P["palabra"]) == 0:
        P["auto"] = False
        prueba_veredicto()
        return

    def tic():
        if not P["auto"]:
            return
        if prueba_paso():
            R.despues(420 * factor(), tic)
        else:
            P["auto"] = False
    tic()


def prueba_veredicto():
    P = S.prueba
    res = prueba_calcular()
    v = el("veredicto")
    if P["tipo"] == "afd":
        if res["aceptada"]:
            quien = "gana Argentina" if res["final"] == A.GANA_A else "gana Francia"
            v.className = "veredicto acepta"
            v.innerHTML = "<b>Acepta</b>: %s. %s" % (quien, res["motivo"])
        else:
            v.className = "veredicto rechaza"
            v.innerHTML = "<b>Rechaza.</b> %s" % res["motivo"]
    else:
        if res["error"] is not None:
            v.className = "veredicto rechaza"
            v.innerHTML = ("<b>Entrada inválida.</b> El símbolo «%s» (posición %d) no pertenece a Σ = {I, C, D}."
                           % (P["palabra"][res["error"]], res["error"] + 1))
        else:
            v.className = "veredicto acepta"
            sal = "".join(res["salidas"])
            v.innerHTML = "<b>Salida: %s</b>. Cada predicción es el lado al que se tira en el remate siguiente." % (sal or "λ")


def prueba_tabla_mealy():
    P = S.prueba
    res = prueba_calcular()
    palabra = P["palabra"]
    filas = []
    n = len(palabra) if res["error"] is None else res["error"]
    for k in range(n):
        lado = palabra[k]
        if k == 0:
            tira, resultado = "sin predicción", "depende del azar"
        else:
            tira = res["salidas"][k - 1]
            resultado = "<code>f</code> (atajado)" if tira == lado else "<code>g</code> (gol)"
        clase = ' class="actual"' if k == P["i"] - 1 else ""
        visible = k < P["i"]
        filas.append("<tr%s><td>%d</td><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>"
                     % (clase, k + 1, lado, tira if visible else "", resultado if visible else "",
                        res["estados"][k + 1] if visible else ""))
    el("tabla-mealy").innerHTML = ("<table><thead><tr><th>Remate</th><th>Lado</th><th>Se tira a</th>"
                                   "<th>Resultado</th><th>Estado después</th></tr></thead><tbody>%s</tbody></table>"
                                   % "".join(filas))


# ---------------------------------------------------------------------------
# Eventos
# ---------------------------------------------------------------------------
def _zona(lado):
    def _f(ev):
        jugar_penal(lado)
    return _f


def _modo(modo):
    def _f(ev):
        if modo != S.modo:
            cambiar_modo(modo)
    return _f


def _version(n):
    def _f(ev):
        cambiar_version(n)
    return _f


def _vel(v):
    def _f(ev):
        S.vel = v
        poner_segmento("#panel-simular [data-vel]", "data-vel", ("%g" % v))
        aplicar_factor()
    return _f


def _prueba(tipo):
    def _f(ev):
        prueba_tipo(tipo)
    return _f


def on_tecla(ev):
    if not el("campeon").hidden:
        if ev.key == "Escape":
            cerrar_campeon()
        return
    destino = ev.target
    tag = str(destino.tagName).lower() if destino is not None else ""
    tipo = str(destino.type).lower() if tag == "input" else ""
    escribe = tag in ("textarea", "select") or (tag == "input" and tipo not in ("checkbox", "radio", "button"))
    if escribe:
        if tag == "input" and ev.key == "Enter" and S.modo == "probar":
            ev.preventDefault()
            prueba_reiniciar()
            prueba_ejecutar()
        return
    if ev.ctrlKey or ev.metaKey or ev.altKey:
        return
    clave = str(ev.key).lower()
    if S.modo == "jugar" and clave in TECLAS:
        ev.preventDefault()
        jugar_penal(TECLAS[clave])
    elif S.modo == "simular" and clave == " ":
        ev.preventDefault()
        on_sim(None)


def on_sim(ev):
    if S.tanda.terminada():
        nueva_tanda()
    S.simulando = not S.simulando
    actualizar_turno()
    if S.simulando and not S.bloqueado:
        simular_penal()


def on_paso_sim(ev):
    if not S.simulando:
        simular_penal()


def on_entrada(ev):
    S.prueba["palabra"] = el("entrada").value
    prueba_reiniciar()


def on_paso(ev):
    S.prueba["auto"] = False
    prueba_paso()


def on_volver(ev):
    prueba_reiniciar()


def on_ejecutar(ev):
    prueba_reiniciar()
    prueba_ejecutar()


def on_otra(ev):
    nueva_tanda()


def on_ver(ev):
    cerrar_campeon()


def on_tapar(ev):
    actualizar_turno()


def iniciar():
    S.reducido = bool(window.matchMedia("(prefers-reduced-motion: reduce)").matches)
    for b in todos(".zona"):
        b.addEventListener("click", manejador(_zona(b.getAttribute("data-lado"))))
    for b in todos(".barra [data-modo]"):
        b.addEventListener("click", manejador(_modo(b.getAttribute("data-modo"))))
    for b in todos(".barra [data-version]"):
        b.addEventListener("click", manejador(_version(int(b.getAttribute("data-version")))))
    for b in todos("#panel-simular [data-vel]"):
        b.addEventListener("click", manejador(_vel(float(b.getAttribute("data-vel")))))
    for b in todos("#panel-probar [data-prueba]"):
        b.addEventListener("click", manejador(_prueba(b.getAttribute("data-prueba"))))
    el("btn-reiniciar").addEventListener("click", manejador(on_otra))
    el("btn-sim").addEventListener("click", manejador(on_sim))
    el("btn-paso-sim").addEventListener("click", manejador(on_paso_sim))
    el("entrada").addEventListener("input", manejador(on_entrada))
    el("btn-paso").addEventListener("click", manejador(on_paso))
    el("btn-volver").addEventListener("click", manejador(on_volver))
    el("btn-ejecutar").addEventListener("click", manejador(on_ejecutar))
    el("btn-otra").addEventListener("click", manejador(on_otra))
    el("btn-ver").addEventListener("click", manejador(on_ver))
    el("tapar").addEventListener("change", manejador(on_tapar))
    document.addEventListener("keydown", manejador(on_tecla))

    dibujar_afd()
    dibujar_mealy()
    dibujar_presets()
    nueva_tanda()
    document.body.classList.remove("cargando")
    window.console.log("[penales] listo: AFD de %d estados y Mealy de 4 estados" % A.VERSIONES[S.N]["estados"])


try:
    iniciar()
except Exception as e:
    reportar(e)
    aviso = el("carga-aviso")
    aviso.textContent = "No se pudo iniciar el juego: %s" % e
    aviso.hidden = False
