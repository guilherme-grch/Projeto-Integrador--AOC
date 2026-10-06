"""
takum.py - Versao SIMPLIFICADA (mesma logica da versao original).

Formato Takum de n bits, do bit mais significativo para o menos:

    S (1 bit)  sinal:          0 = positivo, 1 = negativo
    D (1 bit)  direcao:        ajuda a definir o tamanho de C
    R (3 bits) regime:         diz quantos bits o campo C tem
    C (r bits) caracteristica: parte INTEIRA do logaritmo
    M (p bits) mantissa:       parte FRACIONARIA do logaritmo

    r = R        se D == 1
    r = 7 - R    se D == 0
    p = n - r - 5

Valor do numero:
    valor = (-1)^S * raiz(e) ^ ell
    ell   = (-1)^S * (c + m)

Casos especiais:
    zero = todos os bits 0
    NaR  = 1 seguido de zeros (equivale ao NaN)
"""

import math

# ln(raiz de e) = 0.5. Usamos para trocar de base no logaritmo.
LN_RAIZ_E = 0.5


# ---------------------------------------------------------------------------
# Funcoes auxiliares pequenas
# ---------------------------------------------------------------------------
def nar_pattern(n):
    """Padrao do NaR para n bits: 1 seguido de zeros. Ex.: n=8 -> 10000000"""
    return 1 << (n - 1)


def pegar_bits(numero, posicao, quantidade):
    """Pega 'quantidade' bits de 'numero', comecando na 'posicao'.

    posicao 0 = bit mais a direita (menos significativo).
    Se quantidade for 0 ou menos, devolve 0.
    """
    if quantidade <= 0:
        return 0
    mascara = (1 << quantidade) - 1      # ex.: quantidade=3 -> 0b111
    return (numero >> posicao) & mascara


# ---------------------------------------------------------------------------
# DECODE: bits -> numero real
# ---------------------------------------------------------------------------
def decode(bits, n):
    """Converte 'n' bits no formato Takum para um numero (float)."""

    # 1) garante que temos so n bits
    bits = bits & ((1 << n) - 1)

    # 2) o decodificador precisa de pelo menos 12 bits. Se n for menor
    #    (ex.: 8), completamos com zeros a direita (nao muda o valor).
    largura = max(n, 12)
    b = bits << (largura - n)

    # 3) casos especiais
    if b == 0:
        return 0.0
    if b == nar_pattern(largura):
        return math.nan

    # 4) separa os campos
    S = pegar_bits(b, largura - 1, 1)
    D = pegar_bits(b, largura - 2, 1)
    R = pegar_bits(b, largura - 5, 3)

    # 5) tamanho de C
    if D == 1:
        r = R
    else:
        r = 7 - R

    C = pegar_bits(b, largura - 5 - r, r)

    # 6) calcula c (a parte inteira do logaritmo)
    if D == 1:
        c = (1 << r) - 1 + C              # 2^r - 1 + C
    else:
        c = -(1 << (r + 1)) + 1 + C       # -2^(r+1) + 1 + C

    # 7) calcula m (a parte fracionaria), entre 0 e 1
    p = largura - r - 5
    M = pegar_bits(b, 0, p)
    if p > 0:
        m = M / (1 << p)
    else:
        m = 0.0

    # 8) ell = (c + m) com o sinal certo
    if S == 1:
        ell = -(c + m)
    else:
        ell = c + m

    # 9) valor = raiz(e) ^ ell = e ^ (ell * 0.5)
    magnitude = math.exp(ell * LN_RAIZ_E)

    if S == 1:
        return -magnitude
    return magnitude


# ---------------------------------------------------------------------------
# ENCODE: numero real -> bits
# ---------------------------------------------------------------------------
def campos_de_c(c):
    """Dado o inteiro c, devolve (D, r, C).

    c vai de -255 ate 254.
    """
    if c >= 0:
        D = 1
        r = int(math.floor(math.log2(c + 1)))
        C = c - (1 << r) + 1
    else:
        D = 0
        r = int(math.floor(math.log2(-c)))
        C = c + (1 << (r + 1)) - 1
    return D, r, C


def para_complemento_de_dois(bits, n):
    """Le um padrao de n bits como inteiro COM sinal.

    Ex.: n=8, bits=0b11111111 -> -1
    Usamos isso porque os padroes Takum, lidos assim, ficam em ordem
    crescente de valor. Entao arredondar o padrao = arredondar o numero.
    """
    if bits & (1 << (n - 1)):
        return bits - (1 << n)
    return bits


def encode(x, n):
    """Converte um numero (float) para o padrao Takum de n bits mais proximo."""

    if isinstance(x, complex):
        raise TypeError("Takum nao representa numeros complexos")
    x = float(x)

    # --- casos especiais ---
    if math.isnan(x):
        return nar_pattern(n)
    if x == 0.0:
        return 0
    if math.isinf(x):
        x = math.copysign(1e300, x)   # Takum nao tem infinito: usa um numero enorme

    # --- sinal e logaritmo ---
    if x < 0:
        S = 1
    else:
        S = 0

    ell = math.log(abs(x)) / LN_RAIZ_E    # logaritmo na base raiz(e)

    # Lp = c + m (sempre como se fosse positivo)
    if S == 1:
        Lp = -ell
    else:
        Lp = ell

    # --- limita na faixa que o Takum aguenta: c entre -255 e 254 ---
    EPS = 1e-12
    if Lp >= 255.0:
        Lp = 255.0 - EPS
    elif Lp < -255.0:
        Lp = -255.0

    # --- separa parte inteira (c) e fracionaria (m) ---
    c = math.floor(Lp)
    m = Lp - c

    # --- monta o padrao numa largura onde TUDO sempre cabe ---
    # S+D+R+C ocupam no maximo 5+7 = 12 bits, entao qualquer W >= 12 nunca
    # fica sem espaco. Depois reduzimos para n bits.
    #
    # CORRECAO: antes era W = max(n, 12). Para T8 isso arredondava DUAS
    # vezes (primeiro para 12 bits, depois para 8) e em ~3% dos valores
    # escolhia o vizinho mais distante (ex.: 42.0 virava 54.6 em vez de
    # 33.1). Com W = 52 (a precisao de um float do Python) a mantissa e
    # cortada uma unica vez, direto para n bits.
    W = max(n, 52)

    D, r, C = campos_de_c(c)
    p = W - r - 5
    if p > 0:
        M = round(m * (1 << p))
    else:
        M = 0

    # Se o arredondamento da mantissa passou do maximo (ex.: 0.9999 virou 1.0),
    # zera M e soma 1 em c ("vai um").
    if p > 0 and M >= (1 << p):
        M = 0
        c = c + 1
        if c > 254:                          # passou do maior numero possivel
            c = 254
            M = (1 << (W - 7 - 5)) - 1
        D, r, C = campos_de_c(c)
        p = W - r - 5
        if p <= 0:
            M = 0

    # campo R: depende de D
    if D == 1:
        R = r
    else:
        R = 7 - r

    # --- junta os campos num unico numero ---
    padrao = 0
    padrao = padrao | (S << (W - 1))
    padrao = padrao | (D << (W - 2))
    padrao = padrao | ((R & 0b111) << (W - 5))
    if r > 0:
        padrao = padrao | ((C & ((1 << r) - 1)) << (W - 5 - r))
    if p > 0:
        padrao = padrao | (M & ((1 << p) - 1))

    # --- reduz de W bits para n bits, arredondando ---
    if n < W:
        quantos_bits_cortar = W - n
        com_sinal = para_complemento_de_dois(padrao, W)
        # soma "meio" e corta: arredonda para o mais proximo
        arredondado = (com_sinal + (1 << (quantos_bits_cortar - 1))) >> quantos_bits_cortar
        # nao deixa sair da faixa de n bits com sinal
        maximo = (1 << (n - 1)) - 1
        minimo = -(1 << (n - 1))
        if arredondado > maximo:
            arredondado = maximo
        if arredondado < minimo:
            arredondado = minimo
        padrao = arredondado & ((1 << n) - 1)

    padrao = padrao & ((1 << n) - 1)

    # --- correcoes finais ---
    # 1) numero normal nao pode virar NaR: pega o vizinho
    if padrao == nar_pattern(n):
        padrao = (padrao + 1) & ((1 << n) - 1)
    # 2) numero diferente de zero nao pode virar zero
    if padrao == 0:
        if S == 1:
            padrao = (1 << n) - 1
        else:
            padrao = 1

    return padrao


# ---------------------------------------------------------------------------
# INSPECT: mostra os campos (util para estudar e para slides)
# ---------------------------------------------------------------------------
def inspect(bits, n):
    """Devolve um dicionario com todos os campos de um padrao Takum."""
    bits = bits & ((1 << n) - 1)
    largura = max(n, 12)
    b = bits << (largura - n)

    if b == 0:
        return {"especial": "zero", "bits": format(bits, "0%db" % n), "valor": 0.0}
    if b == nar_pattern(largura):
        return {"especial": "NaR", "bits": format(bits, "0%db" % n), "valor": math.nan}

    S = pegar_bits(b, largura - 1, 1)
    D = pegar_bits(b, largura - 2, 1)
    R = pegar_bits(b, largura - 5, 3)
    if D == 1:
        r = R
    else:
        r = 7 - R
    C = pegar_bits(b, largura - 5 - r, r)
    if D == 1:
        c = (1 << r) - 1 + C
    else:
        c = -(1 << (r + 1)) + 1 + C
    p = largura - r - 5
    M = pegar_bits(b, 0, p)
    if p > 0:
        m = M / (1 << p)
    else:
        m = 0.0
    if S == 1:
        ell = -(c + m)
    else:
        ell = c + m

    return {
        "bits": format(bits, "0%db" % n),
        "S": S, "D": D, "R": R,
        "r (tamanho de C)": r,
        "C": C, "c (parte inteira)": c,
        "p (tamanho de M)": p,
        "M": M, "m (parte fracionaria)": round(m, 6),
        "ell": round(ell, 6),
        "valor": decode(bits, n),
    }


# ---------------------------------------------------------------------------
# OPERACOES: decodifica -> faz a conta em float -> codifica de volta
# ---------------------------------------------------------------------------
# O float do Python (double, 64 bits) e bem mais preciso que T8/T16/T32,
# entao o resultado e o mesmo que o hardware daria.
# Se qualquer entrada for NaR, o resultado e NaR.

def add(a, b, n):
    """a + b"""
    x = decode(a, n)
    y = decode(b, n)
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)
    return encode(x + y, n)


def sub(a, b, n):
    """a - b"""
    x = decode(a, n)
    y = decode(b, n)
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)
    return encode(x - y, n)


def mul(a, b, n):
    """a * b"""
    x = decode(a, n)
    y = decode(b, n)
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)
    return encode(x * y, n)


def div(a, b, n):
    """a / b  (divisao por zero da NaR)"""
    x = decode(a, n)
    y = decode(b, n)
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)
    if y == 0.0:
        return nar_pattern(n)
    return encode(x / y, n)


def fma(a, b, c, n, n_out=None):
    """(a * b) + c com um unico arredondamento no final.

    a e b tem n bits. c e o resultado tem n_out bits (se n_out nao for
    dado, usa n). Isso permite somar em precisao maior: entradas T16,
    saida T32 (e o que a instrucao vtdot.vv faz).
    """
    if n_out is None:
        n_out = n
    x = decode(a, n)
    y = decode(b, n)
    z = decode(c, n_out)
    if math.isnan(x) or math.isnan(y) or math.isnan(z):
        return nar_pattern(n_out)

    # math.fma so existe em Python 3.13 ou mais novo
    if hasattr(math, "fma"):
        resultado = math.fma(x, y, z)
    else:
        resultado = x * y + z
    return encode(resultado, n_out)


def convert(bits, n_origem, n_destino):
    """Converte de uma largura para outra (ex.: T32 -> T16).

    E o que a instrucao vncvt.t.t faz.
    """
    valor = decode(bits, n_origem)
    if math.isnan(valor):
        return nar_pattern(n_destino)
    return encode(valor, n_destino)


# ---------------------------------------------------------------------------
# MULTIPLICACAO "hardware": soma dos logaritmos
# ---------------------------------------------------------------------------
def mul_lns(a, b, n):
    """Multiplica SOMANDO os logaritmos (ell) e fazendo XOR dos sinais.

    Mostra por que multiplicar em Takum e barato em hardware.
    O resultado deve ser igual ao de mul().
    """
    x = decode(a, n)
    y = decode(b, n)

    if x == 0.0 or y == 0.0:
        return 0
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)

    ell_x = math.log(abs(x)) / LN_RAIZ_E
    ell_y = math.log(abs(y)) / LN_RAIZ_E

    ell_resultado = ell_x + ell_y          # <<< a multiplicacao vira esta SOMA

    sinal_x = 1 if x < 0 else 0
    sinal_y = 1 if y < 0 else 0
    sinal_resultado = sinal_x ^ sinal_y    # <<< XOR dos sinais

    magnitude = math.exp(ell_resultado * LN_RAIZ_E)
    if sinal_resultado == 1:
        return encode(-magnitude, n)
    return encode(magnitude, n)
