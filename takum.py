"""
takum.py - Codec e aritmetica do formato Takum LOGARITMICO (T8, T16, T32).

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


# Funcoes auxiliares pequenas
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


# DECODE: bits -> numero real
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


# ENCODE: numero real -> bits
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


def log_value(bits, n):
    """Logaritmo ell EXATO como Fraction, sem exp/log; exclui zero/NaR."""
    from fractions import Fraction
    width=max(n,12); b=bits << (width-n)
    if bits in (0,nar_pattern(n)): raise ValueError('padrao especial')
    S=(b>>(width-1))&1;D=(b>>(width-2))&1;R=(b>>(width-5))&7
    r=R if D else 7-R
    C=pegar_bits(b,width-5-r,r);p=width-5-r
    c=(1<<r)-1+C if D else -(1<<(r+1))+1+C
    value=Fraction(c)+Fraction(pegar_bits(b,0,p),1<<p)
    return -value if S else value


def encode_log(ell, n, negative=False):
    """Quantiza ell na escala logaritmica. Empates para padrao par.

    Entrada exata Fraction permite testar empates sem erro de math.log.
    Saturacao/clamp impedem criar NaR ou zero a partir de um valor normal.
    """
    from fractions import Fraction
    if type(n) is not int or n<2: raise ValueError('largura invalida')
    ell=Fraction(ell); maximum=(1<<(n-1))-1
    if ell<=log_value(1,n): bits=1
    elif ell>=log_value(maximum,n): bits=maximum
    else:
        c=math.floor(ell);m=ell-c
        D,r,C=campos_de_c(c);R=r if D else 7-r
        W=max(n,12);p=W-5-r
        raw=(D<<(W-2)) | (R<<(W-5)) | (C<<p) | int(m*(1<<p))
        low=raw>>(W-n)
        low=max(1,min(low,maximum-1))
        middle=(log_value(low,n)+log_value(low+1,n))/2
        bits=low+(ell>middle or (ell==middle and low%2==1))
    return (-bits)&((1<<n)-1) if negative else bits


def encode(x, n):
    """Real -> Takum, vizinho no log com empate par.

    log/exp em float64 sao aproximacoes do modelo funcional. Para testar
    arredondamento exato no dominio logaritmico, use encode_log(Fraction,...).
    Infinito de entrada satura por decisao explicita deste projeto.
    """
    if isinstance(x,complex): raise TypeError('Takum nao representa complexos')
    if type(n) is not int or n<2: raise ValueError('largura invalida')
    x=float(x)
    if math.isnan(x): return nar_pattern(n)
    if x==0: return 0
    if math.isinf(x):
        b=(1<<(n-1))-1
        return (-b)&((1<<n)-1) if x<0 else b
    return encode_log(math.log(abs(x))/LN_RAIZ_E,n,x<0)


# INSPECT: mostra os campos (util para estudar e para slides)
def inspect(bits, n):
    """Devolve um dicionario com todos os campos de um padrao Takum."""
    bits = bits & ((1 << n) - 1)
    largura = max(n, 12)
    b = bits << (largura - n)
    texto_bits = format(bits, "0%db" % n)

    if b == 0:
        return {"especial": "zero", "bits": texto_bits, "valor": 0.0}
    if b == nar_pattern(largura):
        return {"especial": "NaR", "bits": texto_bits, "valor": math.nan}

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

    # Para n < 12 o campo C pode nao caber nos n bits. Os bits que faltam
    # valem 0 (o padrao e "estendido com zeros" ate 12 bits para decodificar).
    # Por isso a mantissa so tem os bits que realmente existem:
    r_visivel = min(r, n - 5)
    p = n - 5 - r_visivel
    M = pegar_bits(bits, 0, p)
    if p > 0:
        m = M / (1 << p)
    else:
        m = 0.0

    if S == 1:
        ell = -(c + m)
    else:
        ell = c + m

    # texto com os campos separados: S | D | RRR | C | M
    parte_c = texto_bits[5:5 + r_visivel]
    parte_m = texto_bits[5 + r_visivel:]
    if parte_c == "":
        parte_c = "-"
    if parte_m == "":
        parte_m = "-"
    campos = texto_bits[0] + " | " + texto_bits[1] + " | " + texto_bits[2:5] + " | " + parte_c + " | " + parte_m
    if r > r_visivel:
        campos = campos + "   (C precisa de %d bits, so %d cabem: o resto vale 0)" % (r, r_visivel)

    return {
        "bits": texto_bits,
        "campos": campos,
        "S": S, "D": D, "R": R,
        "r (tamanho de C)": r,
        "C": C, "c (parte inteira)": c,
        "p (tamanho de M)": p,
        "M": M, "m (parte fracionaria)": round(m, 6),
        "ell": round(ell, 6),
        "valor": decode(bits, n),
    }


# OPERACOES: decodifica -> faz a conta em float -> codifica de volta
# Modelo FUNCIONAL: a conta e feita em float64 (53 bits de significando, bem
# mais que os <= 27 bits de fracao de um T32) e o resultado e arredondado UMA
# vez para n bits. Isso da o resultado arredondado corretamente na grande
# maioria dos casos, mas NAO foi demonstrado que um hardware Takum produziria
# exatamente os mesmos bits (ele pode usar aproximacoes proprias para somar
# logaritmos). Trate este modelo como a referencia de projeto, nao como prova
# de equivalencia com hardware.
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
    """(a * b) + c, arredondado uma vez para n_out bits no final.

    Com Python >= 3.13 usa math.fma (produto e soma com um unico
    arredondamento em float64). Em versoes anteriores faz x*y + z, que
    arredonda duas vezes em float64 (o efeito e desprezivel perto da
    precisao de T8/T16/T32, mas os bits podem diferir em casos raros).

    a e b tem n bits. c e o resultado tem n_out bits (se n_out nao for
    dado, usa n). Isso permite somar em precisao maior: entradas T16,
    saida T32 (usado pelo baseline sequencial; o modelo paralelo usa acumulacao de 113 bits).
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


# MULTIPLICACAO "hardware": soma dos logaritmos
def mul_lns(a, b, n):
    """Multiplica SOMANDO os logaritmos (ell) e fazendo XOR dos sinais.

    Mostra por que multiplicar em Takum e barato em hardware.
    O resultado deve ser igual ao de mul().
    """
    x = decode(a, n)
    y = decode(b, n)

    # NaR vem ANTES de zero: 0 * NaR = NaR (igual a mul()).
    if math.isnan(x) or math.isnan(y):
        return nar_pattern(n)
    if x == 0.0 or y == 0.0:
        return 0

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
