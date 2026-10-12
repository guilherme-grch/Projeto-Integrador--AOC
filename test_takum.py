"""
test_takum.py - Versao SIMPLIFICADA (mesmos testes da versao original).

Como rodar:   python3 test_takum.py
(o arquivo takum.py precisa estar na mesma pasta)
"""

import math
import takum

# Contadores: quantos testes rodaram e quais falharam
total = 0
falhas = []


def aprox(a, b, tolerancia=1e-9):
    """True se a e b sao quase iguais (erro relativo menor que a tolerancia)."""
    if a == b:
        return True
    if b == 0:
        return abs(a) < tolerancia
    return abs((a - b) / b) < tolerancia


def check(nome, condicao, extra=""):
    """Registra um teste: imprime OK ou FALHA e guarda a contagem."""
    global total
    total = total + 1
    if condicao:
        print("  OK   " + nome)
    else:
        print("  FALHA " + nome + "  " + extra)
        falhas.append(nome)


def titulo(texto):
    print()
    print("=" * 62)
    print(texto)
    print("=" * 62)


# ---------------------------------------------------------------------------
titulo("1. CASOS ESPECIAIS (zero e NaR)")
for n in (8, 16, 32):
    check("T%d: zero decodifica como 0.0" % n, takum.decode(0, n) == 0.0)
    check("T%d: NaR decodifica como NaN" % n,
          math.isnan(takum.decode(takum.nar_pattern(n), n)))
    check("T%d: encode(0.0) == 0" % n, takum.encode(0.0, n) == 0)

# ---------------------------------------------------------------------------
titulo("2. VALORES CONHECIDOS (do paper)")
# Com 2 bits: "01" vale +1 e "11" vale -1
check("bits '01' (n=2) == +1.0", aprox(takum.decode(0b01, 2), 1.0))
check("bits '11' (n=2) == -1.0", aprox(takum.decode(0b11, 2), -1.0))

# ---------------------------------------------------------------------------
titulo("3. IDA E VOLTA (encode -> decode) EM T32")
valores = [1.0, -1.0, 2.0, 0.5, -0.5, 3.14159265, 100.0, -0.001,
           1e10, 1e-10, 6.02214076e23, -7.5]
for v in valores:
    bits = takum.encode(v, 32)
    voltou = takum.decode(bits, 32)
    erro = abs((voltou - v) / v)
    check("T32 ida e volta %14.6e (erro relativo %.2e)" % (v, erro),
          erro < 1e-6, "-> " + str(voltou))

# ---------------------------------------------------------------------------
titulo("4. PRECISAO POR LARGURA (T8, T16, T32)")
print("  Esperado: quanto MENOS bits, MAIOR o erro.")
pi = 3.14159265358979
erros = {}
for n in (8, 16, 32):
    voltou = takum.decode(takum.encode(pi, n), n)
    erros[n] = abs((voltou - pi) / pi)
    print("  T%-2d: pi -> %.10f   erro relativo = %.3e" % (n, voltou, erros[n]))
check("erro T8 > erro T16", erros[8] > erros[16])
check("erro T16 > erro T32", erros[16] > erros[32])

# ---------------------------------------------------------------------------
titulo("5. OPERACOES EM T32 (soma, subtracao, multiplicacao, divisao)")
# cada caso: (nome, funcao, x, y, resultado esperado)
casos = [
    ("soma",      takum.add, 7.5,  10.25, 17.75),
    ("subtracao", takum.sub, 7.5,  10.25, -2.75),
    ("multipl.",  takum.mul, 7.5,  3.2,   24.0),
    ("divisao",   takum.div, 24.0, 3.2,   7.5),
]
for nome, operacao, x, y, esperado in casos:
    bits_x = takum.encode(x, 32)
    bits_y = takum.encode(y, 32)
    bits_resultado = operacao(bits_x, bits_y, 32)
    obtido = takum.decode(bits_resultado, 32)
    check("T32 %s: %s e %s = %.6f (esperado %s)" % (nome, x, y, obtido, esperado),
          aprox(obtido, esperado, 1e-6))

# divisao por zero deve dar NaR
r = takum.div(takum.encode(1.0, 32), takum.encode(0.0, 32), 32)
check("T32 divisao por zero -> NaR", math.isnan(takum.decode(r, 32)))

# ---------------------------------------------------------------------------
titulo("6. FMA (multiplica e soma de uma vez)")
a = 2.5
b = 4.0
c = 1.5
bits = takum.fma(takum.encode(a, 32), takum.encode(b, 32),
                 takum.encode(c, 32), 32)
obtido = takum.decode(bits, 32)
check("T32 FMA: %s*%s+%s = %.6f (esperado %s)" % (a, b, c, obtido, a * b + c),
      aprox(obtido, a * b + c, 1e-6))

# IMPORTANTE (vale um paragrafo no artigo):
# No IEEE754, 3, 2 e 6 sao exatos, entao -3*2+6 da zero exato.
# No Takum (logaritmico) eles NAO sao exatos (3.0 vira ~2.9999999924 em T32).
# Sobra um residuo minusculo. Nao e bug: e caracteristica do formato.
bits = takum.fma(takum.encode(-3.0, 32), takum.encode(2.0, 32),
                 takum.encode(6.0, 32), 32)
obtido = takum.decode(bits, 32)
check("T32 FMA: -3*2+6 = %.3e (sobra residuo do tamanho da precisao)" % obtido,
      abs(obtido) / 6.0 < 1e-7)

# Entradas em T16, resultado em T32 (caso da instrucao vtdot.vv).
# T16 tem precisao de ~2.4e-4, entao a tolerancia precisa ser maior.
bits = takum.fma(takum.encode(1.5, 16), takum.encode(2.5, 16),
                 takum.encode(0.25, 32), 16, n_out=32)
obtido = takum.decode(bits, 32)
check("FMA T16xT16 -> T32: 1.5*2.5+0.25 = %.6f (esperado ~4.0)" % obtido,
      aprox(obtido, 4.0, 1e-3))

# ---------------------------------------------------------------------------
titulo("7. MULTIPLICACAO VIA LOGARITMOS (mul_lns)")
print("  mul() e mul_lns() devem dar o mesmo resultado.")
pares = [(2.0, 3.0), (7.5, 3.2), (-2.0, 4.0), (-1.5, -6.0), (0.25, 8.0)]
for x, y in pares:
    bx = takum.encode(x, 32)
    by = takum.encode(y, 32)
    r1 = takum.decode(takum.mul(bx, by, 32), 32)
    r2 = takum.decode(takum.mul_lns(bx, by, 32), 32)
    check("T32 %s * %s: mul=%.6f mul_lns=%.6f" % (x, y, r1, r2),
          aprox(r1, r2, 1e-6))

# ---------------------------------------------------------------------------
titulo("8. CONVERSAO ENTRE LARGURAS (instrucao vncvt.t.t)")
for v in [1.0, 3.14159, 100.0, 0.001]:
    b32 = takum.encode(v, 32)
    b16 = takum.convert(b32, 32, 16)
    b8 = takum.convert(b32, 32, 8)
    print("  %10.5f:  T32=%.6f  T16=%.6f  T8=%.6f" % (
        v, takum.decode(b32, 32), takum.decode(b16, 16), takum.decode(b8, 8)))

b32 = takum.encode(100.0, 32)
b16 = takum.convert(b32, 32, 16)
check("conversao T32->T16 mantem o valor aproximado",
      aprox(takum.decode(b16, 16), 100.0, 0.05))

# ---------------------------------------------------------------------------
titulo("9. REGRESSAO: T8 COM NUMEROS MUITO GRANDES/PEQUENOS")
print("  (este caso dava erro antes da correcao do encode)")
for v in (1e-30, 1e-12, 1.0, 1e12, 1e30, -1e12):
    try:
        b = takum.encode(v, 8)
        d = takum.decode(b, 8)
        diferente_de_zero = (d != 0.0)
        mesmo_sinal = ((d > 0) == (v > 0))
        finito = math.isfinite(d)
        ok = diferente_de_zero and mesmo_sinal and finito
        check("T8 encode/decode %9.0e -> %11.4e" % (v, d), ok)
    except Exception as erro:
        check("T8 encode/decode %9.0e" % v, False, "EXCECAO: " + str(erro))

# ---------------------------------------------------------------------------
titulo("9b. REGRESSAO: T8 DEVE ESCOLHER O VIZINHO MAIS PROXIMO")
print("  (antes da correcao, o encode arredondava 2 vezes e errava ~3%)")
# Para cada valor abaixo, o ell cai mais perto do vizinho de baixo.
# Valores esperados: os dois vizinhos de T8 sao potencias de raiz(e).
casos_t8 = [
    (42.0, 33.1155),     # vizinhos: 33.1155 e 54.5982 -> o de baixo e o mais perto
    (29.0, 25.7903),     # vizinhos: 20.0855 e 33.1155
    (70.0, 54.5982),     # vizinhos: 54.5982 e 90.0171
]
for valor, esperado in casos_t8:
    obtido = takum.decode(takum.encode(valor, 8), 8)
    check("T8 encode(%s) = %.4f (esperado %.4f)" % (valor, obtido, esperado),
          aprox(obtido, esperado, 1e-4))

# Teste geral: o valor escolhido tem que ser um dos dois vizinhos de x
# (o mais baixo e o mais alto entre TODOS os valores finitos de T8) e o
# mais perto deles na escala logaritmica (a escala do Takum).
todos_t8 = []
for b in range(256):
    v = takum.decode(b, 8)
    if not math.isnan(v) and v > 0:
        todos_t8.append(v)
todos_t8.sort()

erros_vizinho = 0
for inteiro in range(1, 1001):
    escolhido = takum.decode(takum.encode(float(inteiro), 8), 8)
    # vizinhos de baixo e de cima de 'inteiro' na lista de todos os T8
    baixo = None
    cima = None
    for v in todos_t8:
        if v <= inteiro:
            baixo = v
        if v >= inteiro and cima is None:
            cima = v
    candidatos = [v for v in (baixo, cima) if v is not None]
    # distancia na escala logaritmica
    melhor = min(candidatos, key=lambda v: abs(math.log(v) - math.log(inteiro)))
    if not aprox(escolhido, melhor, 1e-9):
        erros_vizinho = erros_vizinho + 1
check("T8, inteiros de 1 a 1000: sempre o vizinho mais proximo (%d erros)" % erros_vizinho,
      erros_vizinho == 0)

# ---------------------------------------------------------------------------
titulo("10. ORDEM DOS PADROES (complemento de dois)")
print("  Lendo os bits como inteiro COM sinal, os valores devem crescer.")
for n in (8, 12):
    lista = []          # guarda pares (inteiro com sinal, valor decodificado)
    for b in range(1 << n):
        if b & (1 << (n - 1)):
            com_sinal = b - (1 << n)
        else:
            com_sinal = b
        valor = takum.decode(b, n)
        if not math.isnan(valor):       # ignora o NaR
            lista.append((com_sinal, valor))
    lista.sort()

    crescente = True
    for i in range(len(lista) - 1):
        if not (lista[i][1] < lista[i + 1][1]):
            crescente = False
    check("T%d: %d padroes em ordem estritamente crescente" % (n, len(lista)),
          crescente)

# ---------------------------------------------------------------------------
titulo("11. FAIXA DINAMICA (dado central do artigo)")
for n in (8, 16, 32):
    maior = takum.decode((1 << (n - 1)) - 1, n)
    menor = takum.decode(1, n)
    ordens = math.log10(maior / menor)
    print("  T%-2d: %.3e ate %.3e  -> %.0f ordens de grandeza" % (
        n, menor, maior, ordens))

maior8 = takum.decode((1 << 7) - 1, 8)
menor8 = takum.decode(1, 8)
check("T8 cobre mais de 50 ordens de grandeza (FP8 E4M3 cobre ~5)",
      math.log10(maior8 / menor8) > 50)

# ---------------------------------------------------------------------------
titulo("12. INSPECT (mostra os campos de um numero)")
for v in [1.0, -1.0, 2.0]:
    info = takum.inspect(takum.encode(v, 12), 12)
    print("  valor %s:" % v)
    for nome_campo, conteudo in info.items():
        print("      %-22s = %s" % (nome_campo, conteudo))

# ---------------------------------------------------------------------------
titulo("13. CONFERENCIA COM O ARTIGO DO HUNHOLD (AVX10.2, arXiv 2503.14067)")
print("  Cada teste confere uma afirmacao do artigo.")


def igual_ou_nan(a, b):
    """True se a == b, ou se os dois sao NaN."""
    if math.isnan(a) and math.isnan(b):
        return True
    return a == b


# 13.1 Figura 1 do artigo: S(1) D(1) R(3) C(r bits, r de 0 a 7) F(p bits)
#      com p variando de n-12 ate n-5.
for n in (8, 16, 32, 64):
    valores_p = sorted(set([n - r - 5 for r in range(8)]))
    check("T%-2d: p varia de n-12=%d ate n-5=%d" % (n, n - 12, n - 5),
          valores_p == list(range(n - 12, n - 4)))
check("T64 tem no minimo 52 bits de fracao (o mesmo que o float64)", 64 - 12 >= 52)

# 13.2 Os campos que o inspect devolve respeitam esse layout, em TODOS os padroes.
erros_t16 = 0
for b in range(1 << 16):
    info = takum.inspect(b, 16)
    if "especial" in info:
        continue
    r = info["r (tamanho de C)"]
    p = info["p (tamanho de M)"]
    if not (0 <= r <= 7 and 4 <= p <= 11 and 5 + r + p == 16):
        erros_t16 = erros_t16 + 1
check("T16: 65534 padroes com 0<=r<=7, 4<=p<=11 e 5+r+p=16 (%d erros)" % erros_t16,
      erros_t16 == 0)

erros_t8 = 0
for b in range(256):
    info = takum.inspect(b, 8)
    if "especial" in info:
        continue
    r = info["r (tamanho de C)"]
    p = info["p (tamanho de M)"]
    # em T8 o C pode nao caber: so min(r, 3) bits de C existem
    if not (0 <= r <= 7 and 0 <= p <= 3 and 5 + min(r, 3) + p == 8):
        erros_t8 = erros_t8 + 1
check("T8: 254 padroes: 5 + bits de C que cabem + p = 8 (%d erros)" % erros_t8,
      erros_t8 == 0)

# 13.3 "Takums sao invariantes sob extensao com zeros":
#      acrescentar zeros a direita nao muda o valor.
erros = 0
for b in range(256):
    for n_maior in (12, 16, 32):
        if not igual_ou_nan(takum.decode(b, 8), takum.decode(b << (n_maior - 8), n_maior)):
            erros = erros + 1
check("T8 + zeros a direita = mesmo valor em T12, T16 e T32 (%d erros)" % erros, erros == 0)

erros = 0
for b in range(4096):
    for n_maior in (16, 32):
        if not igual_ou_nan(takum.decode(b, 12), takum.decode(b << (n_maior - 12), n_maior)):
            erros = erros + 1
check("T12 + zeros a direita = mesmo valor em T16 e T32 (%d erros)" % erros, erros == 0)

erros = 0
for b in range(1 << 16):
    if not igual_ou_nan(takum.decode(b, 16), takum.decode(b << 16, 32)):
        erros = erros + 1
check("T16 + zeros a direita = mesmo valor em T32 (%d erros)" % erros, erros == 0)

# 13.4 "Ordem e negacao naturais em complemento de dois":
#      negar o padrao (complemento de dois) e negar o valor.
for n in (8, 12, 16):
    mascara = (1 << n) - 1
    nar = 1 << (n - 1)
    erros = 0
    for b in range(1, 1 << n):
        if b == nar:
            continue
        negado = (-b) & mascara
        if not aprox(takum.decode(negado, n), -takum.decode(b, n), 1e-12):
            erros = erros + 1
    check("T%-2d: decode(-padrao) == -decode(padrao) (%d erros)" % (n, erros), erros == 0)

# 13.5 "Zero unico, sem sinal": so o padrao 0 vale zero; so o NaR vale NaN;
#      todo o resto e finito e diferente de zero (sem infinito, sem subnormal).
for n in (8, 12):
    nar = 1 << (n - 1)
    zeros = 0
    nans = 0
    estranhos = 0
    for b in range(1 << n):
        v = takum.decode(b, n)
        if math.isnan(v):
            nans = nans + 1
        elif v == 0.0:
            zeros = zeros + 1
        elif not math.isfinite(v):
            estranhos = estranhos + 1
    check("T%-2d: 1 zero, 1 NaR e nenhum infinito (zeros=%d, NaR=%d, infinitos=%d)" % (
        n, zeros, nans, estranhos), zeros == 1 and nans == 1 and estranhos == 0)

# 13.6 "O decodificador so precisa dos 12 bits mais significativos":
#      S, D, R e C (e portanto c) nao mudam se mexermos nos outros bits.
import random
random.seed(3)
mudou = 0
testados = 0
for _ in range(3000):
    b = random.getrandbits(32)
    posicao = random.randint(0, 19)          # um dos 20 bits de baixo
    b2 = b ^ (1 << posicao)
    i1 = takum.inspect(b, 32)
    i2 = takum.inspect(b2, 32)
    if "especial" in i1 or "especial" in i2:
        continue
    testados = testados + 1
    chaves = ["S", "D", "R", "r (tamanho de C)", "C", "c (parte inteira)"]
    for k in chaves:
        if i1[k] != i2[k]:
            mudou = mudou + 1
check("T32: mexer nos 20 bits de baixo nunca muda S, D, R, C (%d testes, %d mudancas)" % (
    testados, mudou), mudou == 0)

# 13.7 "Faixa dinamica grande e quase toda realizada ja com 8 bits".
faixas = {}
for n in (8, 16, 32):
    maior = takum.decode((1 << (n - 1)) - 1, n)
    menor = takum.decode(1, n)
    faixas[n] = math.log10(maior / menor)
check("T8 tem pelo menos 90%% da faixa do T32 (%.0f de %.0f ordens)" % (faixas[8], faixas[32]),
      faixas[8] >= 0.9 * faixas[32])
check("T16 e T32 tem a mesma faixa (%.1f e %.1f ordens)" % (faixas[16], faixas[32]),
      abs(faixas[16] - faixas[32]) < 0.5)

# ---------------------------------------------------------------------------
print()
print("=" * 62)
if len(falhas) > 0:
    print("RESULTADO: %d/%d testes passaram. FALHAS:" % (total - len(falhas), total))
    for nome in falhas:
        print("   - " + nome)
else:
    print("RESULTADO: todos os %d testes passaram." % total)
print("=" * 62)
