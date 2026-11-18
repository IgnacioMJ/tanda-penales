# -*- coding: utf-8 -*-
"""Lógica de los autómatas del TP "Tanda de penales".

Este módulo no toca la página: solo contiene las tablas del informe y las
funciones que las recorren. Corre igual en MicroPython (navegador, PyScript)
y en CPython (tests en tests/test_automatas.py).

  * AFD de la tanda  -> Tabla 4 del informe (3 penales) y su versión de 5.
  * Arquero (Mealy)  -> Tabla 7 del informe.
  * Tanda            -> une los dos autómatas con la regla de la Tabla 2 y el
                        orden de la sección 10. No genera azar: el lado al azar
                        se recibe como parámetro (el azar queda fuera del modelo).
"""

# ---------------------------------------------------------------------------
# Alfabetos
# ---------------------------------------------------------------------------
SIGMA_TANDA = ("g", "f")          # g = gol, f = no fue gol
SIGMA_ARQUERO = ("I", "C", "D")   # izquierda, centro, derecha (de la pantalla)

INICIAL = "q0_0"
GANA_A = "GANA_A"
GANA_B = "GANA_B"
SUMIDERO = "SUM"
FINALES = (GANA_A, GANA_B)

# ---------------------------------------------------------------------------
# AFD de 3 penales por equipo: Tabla 4 del informe (18 estados)
# ---------------------------------------------------------------------------
AFD_3 = {
    "q0_0":  {"g": "q1_1",   "f": "q1_0"},
    "q1_1":  {"g": "q2_0",   "f": "q2_1"},
    "q1_0":  {"g": "q2_-1",  "f": "q2_0"},
    "q2_1":  {"g": "q3_2",   "f": "q3_1"},
    "q2_0":  {"g": "q3_1",   "f": "q3_0"},
    "q2_-1": {"g": "q3_0",   "f": "q3_-1"},
    "q3_2":  {"g": "q4_1",   "f": "GANA_A"},
    "q3_1":  {"g": "q4_0",   "f": "q4_1"},
    "q3_0":  {"g": "q4_-1",  "f": "q4_0"},
    "q3_-1": {"g": "GANA_B", "f": "q4_-1"},
    "q4_1":  {"g": "GANA_A", "f": "q5_1"},
    "q4_0":  {"g": "q5_1",   "f": "q5_0"},
    "q4_-1": {"g": "q5_0",   "f": "GANA_B"},
    "q5_1":  {"g": "q4_0",   "f": "GANA_A"},
    "q5_0":  {"g": "GANA_B", "f": "q4_0"},
    "GANA_A": {"g": "SUM",   "f": "SUM"},
    "GANA_B": {"g": "SUM",   "f": "SUM"},
    "SUM":   {"g": "SUM",    "f": "SUM"},
}

# Coordenadas tomadas de jflap/tanda_3_penales.jff (el grafo del juego es el
# mismo dibujo que la Figura 2 del informe).
POS_3 = {
    "GANA_A": (740, 80), "q3_2": (410, 180),
    "q1_1": (190, 270), "q2_1": (300, 270), "q3_1": (410, 270),
    "q4_1": (520, 270), "q5_1": (630, 270),
    "q0_0": (80, 360), "q1_0": (190, 360), "q2_0": (300, 360),
    "q3_0": (410, 360), "q4_0": (520, 360), "q5_0": (630, 360),
    "SUM": (900, 360),
    "q2_-1": (300, 450), "q3_-1": (410, 450), "q4_-1": (520, 450),
    "GANA_B": (740, 640),
}

# ---------------------------------------------------------------------------
# AFD de 5 penales por equipo (38 estados). Generado con
# tools/generar_afd.py a partir del reglamento; mismo esquema qk_d.
# Exportado también como jflap/tanda_5_penales.jff.
# ---------------------------------------------------------------------------
AFD_5 = {
    "q0_0":  {"g": "q1_1",   "f": "q1_0"},
    "q1_1":  {"g": "q2_0",   "f": "q2_1"},
    "q1_0":  {"g": "q2_-1",  "f": "q2_0"},
    "q2_1":  {"g": "q3_2",   "f": "q3_1"},
    "q2_0":  {"g": "q3_1",   "f": "q3_0"},
    "q2_-1": {"g": "q3_0",   "f": "q3_-1"},
    "q3_2":  {"g": "q4_1",   "f": "q4_2"},
    "q3_1":  {"g": "q4_0",   "f": "q4_1"},
    "q3_0":  {"g": "q4_-1",  "f": "q4_0"},
    "q3_-1": {"g": "q4_-2",  "f": "q4_-1"},
    "q4_2":  {"g": "q5_3",   "f": "q5_2"},
    "q4_1":  {"g": "q5_2",   "f": "q5_1"},
    "q4_0":  {"g": "q5_1",   "f": "q5_0"},
    "q4_-1": {"g": "q5_0",   "f": "q5_-1"},
    "q4_-2": {"g": "q5_-1",  "f": "q5_-2"},
    "q5_3":  {"g": "q6_2",   "f": "GANA_A"},
    "q5_2":  {"g": "q6_1",   "f": "q6_2"},
    "q5_1":  {"g": "q6_0",   "f": "q6_1"},
    "q5_0":  {"g": "q6_-1",  "f": "q6_0"},
    "q5_-1": {"g": "q6_-2",  "f": "q6_-1"},
    "q5_-2": {"g": "GANA_B", "f": "q6_-2"},
    "q6_2":  {"g": "GANA_A", "f": "q7_2"},
    "q6_1":  {"g": "q7_2",   "f": "q7_1"},
    "q6_0":  {"g": "q7_1",   "f": "q7_0"},
    "q6_-1": {"g": "q7_0",   "f": "q7_-1"},
    "q6_-2": {"g": "q7_-1",  "f": "GANA_B"},
    "q7_2":  {"g": "q8_1",   "f": "GANA_A"},
    "q7_1":  {"g": "q8_0",   "f": "q8_1"},
    "q7_0":  {"g": "q8_-1",  "f": "q8_0"},
    "q7_-1": {"g": "GANA_B", "f": "q8_-1"},
    "q8_1":  {"g": "GANA_A", "f": "q9_1"},
    "q8_0":  {"g": "q9_1",   "f": "q9_0"},
    "q8_-1": {"g": "q9_0",   "f": "GANA_B"},
    "q9_1":  {"g": "q8_0",   "f": "GANA_A"},
    "q9_0":  {"g": "GANA_B", "f": "q8_0"},
    "GANA_A": {"g": "SUM",   "f": "SUM"},
    "GANA_B": {"g": "SUM",   "f": "SUM"},
    "SUM":   {"g": "SUM",    "f": "SUM"},
}

POS_5 = {
    "q0_0": (70, 388),
    "q1_1": (170, 302), "q1_0": (170, 388),
    "q2_1": (270, 302), "q2_0": (270, 388), "q2_-1": (270, 474),
    "q3_2": (370, 216), "q3_1": (370, 302), "q3_0": (370, 388), "q3_-1": (370, 474),
    "q4_2": (470, 216), "q4_1": (470, 302), "q4_0": (470, 388), "q4_-1": (470, 474),
    "q4_-2": (470, 560),
    "q5_3": (570, 130), "q5_2": (570, 216), "q5_1": (570, 302), "q5_0": (570, 388),
    "q5_-1": (570, 474), "q5_-2": (570, 560),
    "q6_2": (670, 216), "q6_1": (670, 302), "q6_0": (670, 388), "q6_-1": (670, 474),
    "q6_-2": (670, 560),
    "q7_2": (770, 216), "q7_1": (770, 302), "q7_0": (770, 388), "q7_-1": (770, 474),
    "q8_1": (870, 302), "q8_0": (870, 388), "q8_-1": (870, 474),
    "q9_1": (970, 302), "q9_0": (970, 388),
    "GANA_A": (1090, 70), "GANA_B": (1090, 620), "SUM": (1220, 388),
}

# ---------------------------------------------------------------------------
# Arquero: máquina de Mealy, Tabla 7 del informe.
# MEALY[estado][remate] = (estado_nuevo, salida)
# La salida es la predicción: el lado al que se tira en el remate siguiente.
# ---------------------------------------------------------------------------
MEALY_INICIAL = "q0"
MEALY = {
    "q0": {"I": ("qI", "I"), "C": ("qC", "C"), "D": ("qD", "D")},
    "qI": {"I": ("qI", "I"), "C": ("qC", "I"), "D": ("qD", "I")},
    "qC": {"I": ("qI", "C"), "C": ("qC", "C"), "D": ("qD", "C")},
    "qD": {"I": ("qI", "D"), "C": ("qC", "D"), "D": ("qD", "D")},
}
# Coordenadas de jflap/arquero_mealy.jff (Figura 4 del informe).
POS_MEALY = {"qI": (320, 80), "q0": (320, 300), "qD": (80, 460), "qC": (560, 460)}

VERSIONES = {
    3: {"tabla": AFD_3, "pos": POS_3, "estados": 18},
    5: {"tabla": AFD_5, "pos": POS_5, "estados": 38},
}


# ---------------------------------------------------------------------------
# Recorridos
# ---------------------------------------------------------------------------
def paso_afd(tabla, estado, simbolo):
    """f(q, a). Lanza ValueError si el símbolo no es del alfabeto."""
    if simbolo not in SIGMA_TANDA:
        raise ValueError("símbolo fuera del alfabeto: %r" % simbolo)
    return tabla[estado][simbolo]


def recorrer_afd(tabla, palabra):
    """Recorre la palabra completa, como Input > Multiple Run de JFLAP.

    Devuelve un dict con:
      estados  -> lista de estados visitados (empieza en q0_0)
      aceptada -> True si termina en GANA_A o GANA_B
      final    -> último estado alcanzado
      error    -> posición del primer símbolo fuera del alfabeto (o None)
      motivo   -> explicación en castellano del resultado
    """
    estados = [INICIAL]
    for i in range(len(palabra)):
        c = palabra[i]
        if c not in SIGMA_TANDA:
            return {"estados": estados, "aceptada": False, "final": estados[-1],
                    "error": i,
                    "motivo": "El símbolo «%s» (posición %d) no pertenece a Σ = {g, f}." % (c, i + 1)}
        estados.append(tabla[estados[-1]][c])
    final = estados[-1]
    aceptada = final in FINALES
    if len(palabra) == 0:
        motivo = "λ: no se pateó ningún penal; q0_0 no es final."
    elif final == GANA_A:
        motivo = "Termina en GANA_A: gana el equipo A con el último penal."
    elif final == GANA_B:
        motivo = "Termina en GANA_B: gana el equipo B con el último penal."
    elif final == SUMIDERO:
        j = 0
        while estados[j] not in FINALES:
            j += 1
        motivo = ("Penal de más: la tanda se definió en el penal %d (%s) y el siguiente "
                  "lleva al sumidero." % (j, estados[j]))
    else:
        motivo = "La tanda no terminó: %s no es un estado final." % final
    return {"estados": estados, "aceptada": aceptada, "final": final,
            "error": None, "motivo": motivo}


def paso_mealy(estado, remate):
    if remate not in SIGMA_ARQUERO:
        raise ValueError("remate fuera del alfabeto: %r" % remate)
    return MEALY[estado][remate]


def traducir_mealy(palabra):
    """Devuelve (estados, salidas, error) para una palabra de remates."""
    estados, salidas = [MEALY_INICIAL], []
    for i in range(len(palabra)):
        c = palabra[i]
        if c not in SIGMA_ARQUERO:
            return estados, salidas, i
        nuevo, salida = MEALY[estados[-1]][c]
        estados.append(nuevo)
        salidas.append(salida)
    return estados, salidas, None


def descomponer(estado):
    """'q3_-1' -> (3, -1). Devuelve None para GANA_A, GANA_B y SUM."""
    if not estado.startswith("q"):
        return None
    k, d = estado[1:].split("_")
    return int(k), int(d)


# ---------------------------------------------------------------------------
# La tanda: une el AFD y la Mealy (Tabla 2 + sección 10 del informe)
# ---------------------------------------------------------------------------
class TandaError(Exception):
    pass


class Tanda:
    """Equipo A = Argentina (usuario, patea primero); equipo B = Francia (PC).

    * Penal de A: el usuario elige el lado; el arquero de B se tira a la
      predicción de la Mealy (en el primer remate no hay predicción y el lado
      llega al azar desde afuera). f si coinciden, g si no. Después la Mealy
      lee el remate y emite la predicción del siguiente.
    * Penal de B: la PC elige el lado (al azar, desde afuera) y el usuario se
      tira. f si coinciden, g si no. La Mealy no participa.
    """

    def __init__(self, penales=3):
        if penales not in VERSIONES:
            raise TandaError("versión no soportada: %r" % penales)
        self.penales = penales
        self.tabla = VERSIONES[penales]["tabla"]
        self.reiniciar()

    def reiniciar(self):
        self.estado = INICIAL
        self.palabra = ""
        self.estado_mealy = MEALY_INICIAL
        self.prediccion = None          # salida de la Mealy para el próximo remate de A
        self.remates = ""               # entrada de la Mealy (remates del usuario)
        self.predicciones = ""          # salida de la Mealy
        self.goles = [0, 0]
        self.historial = []

    # --- consultas -------------------------------------------------------
    def numero(self):
        """Número del próximo penal (1, 2, 3...)."""
        return len(self.palabra) + 1

    def turno(self):
        """'A' en posiciones impares, 'B' en pares (sección 5)."""
        return "A" if len(self.palabra) % 2 == 0 else "B"

    def terminada(self):
        return self.estado in FINALES

    def ganador(self):
        if self.estado == GANA_A:
            return "A"
        if self.estado == GANA_B:
            return "B"
        return None

    def muerte_subita(self):
        return len(self.palabra) >= 2 * self.penales

    def resultados(self, equipo):
        """Lista de 'g'/'f' de un equipo, en orden."""
        inicio = 0 if equipo == "A" else 1
        return [self.palabra[i] for i in range(inicio, len(self.palabra), 2)]

    # --- jugadas ---------------------------------------------------------
    def _validar(self, equipo, *lados):
        if self.terminada():
            raise TandaError("la tanda ya terminó (%s)" % self.estado)
        if self.turno() != equipo:
            raise TandaError("no es el turno de %s" % equipo)
        for lado in lados:
            if lado not in SIGMA_ARQUERO:
                raise TandaError("lado inválido: %r" % (lado,))

    def _avanzar_afd(self, simbolo):
        previo = self.estado
        self.estado = paso_afd(self.tabla, previo, simbolo)
        self.palabra += simbolo
        return previo, self.estado

    def patear_a(self, remate, lado_azar):
        """Penal del usuario. lado_azar solo se usa si todavía no hay predicción."""
        self._validar("A", remate, lado_azar)
        if self.prediccion is None:
            arquero, fuente = lado_azar, "azar"
        else:
            arquero, fuente = self.prediccion, "mealy"
        simbolo = "f" if arquero == remate else "g"           # regla de la Tabla 2
        afd_de, afd_a = self._avanzar_afd(simbolo)            # AFD
        if simbolo == "g":
            self.goles[0] += 1
        mealy_de = self.estado_mealy                           # Mealy lee el remate
        self.estado_mealy, salida = paso_mealy(mealy_de, remate)
        self.prediccion = salida
        self.remates += remate
        self.predicciones += salida
        jugada = {"n": len(self.palabra), "equipo": "A", "remate": remate,
                  "arquero": arquero, "fuente": fuente, "simbolo": simbolo,
                  "afd_de": afd_de, "afd_a": afd_a,
                  "mealy_de": mealy_de, "mealy_a": self.estado_mealy, "salida": salida}
        self.historial.append(jugada)
        self.verificar()
        return jugada

    def patear_b(self, remate_pc, arquero_usuario):
        """Penal de la PC: remate_pc llega al azar desde afuera."""
        self._validar("B", remate_pc, arquero_usuario)
        simbolo = "f" if arquero_usuario == remate_pc else "g"
        afd_de, afd_a = self._avanzar_afd(simbolo)
        if simbolo == "g":
            self.goles[1] += 1
        jugada = {"n": len(self.palabra), "equipo": "B", "remate": remate_pc,
                  "arquero": arquero_usuario, "fuente": "usuario", "simbolo": simbolo,
                  "afd_de": afd_de, "afd_a": afd_a,
                  "mealy_de": self.estado_mealy, "mealy_a": self.estado_mealy, "salida": None}
        self.historial.append(jugada)
        self.verificar()
        return jugada

    # --- coherencia ------------------------------------------------------
    def verificar(self):
        """Comprueba que el marcador y el estado del AFD cuentan lo mismo.

        Mientras la tanda está abierta, qk_d debe tener k = penales pateados
        (o 2N-2 / 2N-1 en muerte súbita) y d = goles A - goles B.
        """
        n, N = len(self.palabra), self.penales
        kd = descomponer(self.estado)
        if kd is None:
            # El que gana siempre va adelante en el marcador.
            ga, gb = self.goles
            if self.estado == SUMIDERO:
                raise TandaError("la tanda llegó al sumidero")
            if (self.estado == GANA_A) != (ga > gb) or (self.estado == GANA_B) != (gb > ga):
                raise TandaError("%s con marcador %d-%d" % (self.estado, ga, gb))
            return
        k, d = kd
        # Al completar los 2N penales empatados el AFD ya vuelve a q(2N-2)_0.
        k_esperado = n if n < 2 * N else 2 * N - 2 + (n - 2 * N) % 2
        if k != k_esperado or d != self.goles[0] - self.goles[1]:
            raise TandaError("incoherencia: estado %s con %d penales y %d-%d"
                             % (self.estado, n, self.goles[0], self.goles[1]))
