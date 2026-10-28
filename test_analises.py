"""
test_analises.py - Testes dos scripts de analise da Fase 3.

Confere analise_erro.py, contagem_instrucoes.py e analise_csr.py, sempre
contra algo INDEPENDENTE (numpy, relacoes conhecidas entre formatos, contas
feitas a mao), para nao testar o codigo contra ele mesmo.

Rodar com:  python3 test_analises.py
"""

import math
import random
import sys
from fractions import Fraction

import numpy as np

import analise_csr
import analise_erro
import contagem_instrucoes
import eval_spmv
import takum
import zvtakum

total = 0
falhas = []


def check(nome, condicao, extra=""):
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


def mesmo_valor(a, b):
    """True se a == b, ou se os dois sao NaN."""
    if math.isnan(a) and math.isnan(b):
        return True
    return a == b


# ---------------------------------------------------------------------------
titulo("1. FLOAT128 EMULADO (analise_erro.arredonda_quad)")
quad = analise_erro.arredonda_quad

check("zero, inteiros, potencias de 2 e 1/8 ficam exatos",
      all(quad(Fraction(v)) == Fraction(v) for v in (0, 1, 2, 3, 1024, Fraction(1, 8))))
check("sinal: quad(-x) == -quad(x)",
      quad(Fraction(-1, 3)) == -quad(Fraction(1, 3)))

# 1 + 2^-113 e exatamente metade do passo acima de 1 (passo = 2^-112): empate -> par -> 1
check("empate vai para o par: 1 + 2^-113 -> 1",
      quad(1 + Fraction(1, 2 ** 113)) == 1)
check("empate vai para o par: 1 + 3*2^-113 -> 1 + 2^-111",
      quad(1 + Fraction(3, 2 ** 113)) == 1 + Fraction(1, 2 ** 111))

random.seed(5)
erros_meio_passo = 0
erros_double = 0
erros_produto = 0
for _ in range(2000):
    # fracao qualquer: erro relativo tem que ser <= 2^-113 (meio passo)
    f = Fraction(random.randint(1, 10 ** 30), random.randint(1, 10 ** 30))
    if abs(quad(f) - f) > f * Fraction(1, 2 ** 113):
        erros_meio_passo = erros_meio_passo + 1
    # todo double (53 bits) cabe exato em 113 bits
    d = random.choice([-1, 1]) * 10.0 ** random.uniform(-30, 30)
    if quad(Fraction(d)) != Fraction(d):
        erros_double = erros_double + 1
    # produto de dois doubles tem ate 106 bits: tambem cabe exato
    e = random.choice([-1, 1]) * 10.0 ** random.uniform(-30, 30)
    if quad(Fraction(d) * Fraction(e)) != Fraction(d) * Fraction(e):
        erros_produto = erros_produto + 1
check("erro relativo <= 2^-113 em 2000 fracoes aleatorias (%d erros)" % erros_meio_passo,
      erros_meio_passo == 0)
check("2000 doubles aleatorios ficam exatos (%d erros)" % erros_double, erros_double == 0)
check("2000 produtos de doubles ficam exatos (%d erros)" % erros_produto, erros_produto == 0)

# o SpMV em quad tem que coincidir com o exato ate ~1e-33
random.seed(21)
entradas = eval_spmv.gerar_matriz_esparsa(32, 0.1, 20)
x = [random.uniform(0.1, 10.0) for _ in range(32)]
dif = analise_erro.maior_diferenca_relativa(
    analise_erro.spmv_quad(entradas, x, 32), eval_spmv.spmv_exato(entradas, x, 32))
check("SpMV Float128 vs exato: diferenca relativa %.1e < 1e-30" % dif, dif < 1e-30)

# ---------------------------------------------------------------------------
titulo("2. ESTATISTICAS DA DISTRIBUICAO (analise_erro)")
check("combinar: inf e NaN viram 1.0; acima de 1.0 e limitado a 1.0",
      analise_erro.combinar([0.5, math.inf, math.nan, 7.0, 0.0]) == [0.5, 1.0, 1.0, 1.0, 0.0])
check("percentil de [1,2,3,4,5]: p50=3, p0=1, p100=5",
      analise_erro.percentil([1, 2, 3, 4, 5], 0.5) == 3
      and analise_erro.percentil([1, 2, 3, 4, 5], 0.0) == 1
      and analise_erro.percentil([1, 2, 3, 4, 5], 1.0) == 5)

# um elemento em cada faixa do histograma
amostra = [5e-8, 1e-7, 1e-5, 1e-3, 1e-2, 1e-1, 1.0]
h = analise_erro.histograma(amostra)
check("histograma: cada faixa recebe exatamente 1 elemento %s" % h, h == [1] * 7)
check("histograma: a soma e o numero de elementos",
      sum(analise_erro.histograma([0.0, 0.3, 1.0, 1.0])) == 4)

r = analise_erro.resumo([0.1, 0.2, math.inf, 0.3])
check("resumo: 1 overflow em 4 = 25%", r["overflow_%"] == 25.0)
check("resumo: o maximo combinado e 1.0", r["max"] == 1.0)

# ---------------------------------------------------------------------------
titulo("3. CONTAGEM DE INSTRUCOES: EXEMPLO FEITO A MAO")
# 3 linhas, 8 colunas. Linha 0: 5 nao-zeros. Linha 1: vazia. Linha 2: 1 nao-zero.
entradas = [(0, 0, 1.0), (0, 1, 2.0), (0, 2, 3.0), (0, 3, 4.0), (0, 4, 5.0),
            (2, 7, 6.0)]
x = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0]
r = contagem_instrucoes.medir(entradas, x, 3, 32, 128)     # VLMAX = 4
# pedacos: linha 0 -> 2 (4 + 1), linha 2 -> 1.  Total 3; nao vazias 2; extras 1.
check("VLMAX=4: 3 pedacos", r["pedacos"] == 3)
# no simulador: 3 vsetvli + 3 vtdot + (1 vsetvli + 1 vtadd do pedaco extra) = 8
check("instrucoes contadas pelo simulador = 8 (obtido %d)" % r["no_simulador"],
      r["no_simulador"] == 8)
# memoria: 3 por pedaco (9) + 1 por linha (3) = 12
check("instrucoes de memoria do modelo = 12 (obtido %d)" % r["memoria"],
      r["memoria"] == 12)
check("total Zvtakum = 20 (obtido %d)" % r["total_medido"], r["total_medido"] == 20)
check("formula Zvtakum = 20 (obtido %d)" % r["total_formula"], r["total_formula"] == 20)
check("escalar = 5*6 + 2*3 = 36 (obtido %d)" % r["escalar"], r["escalar"] == 36)
check("RVV IEEE = 6*3 + 2 + 3 = 23 (obtido %d)" % r["rvv_ieee"], r["rvv_ieee"] == 23)

# o resultado numerico: linha 0 = 1+2+3+4+5 = 15, linha 1 = 0, linha 2 = 6*2 = 12
y = [takum.decode(b, r["n_acc"]) for b in r["y_bits"]]
check("y = [15, 0, 12] (obtido %s)" % [round(v, 4) for v in y],
      abs(y[0] - 15) < 1e-6 and y[1] == 0.0 and abs(y[2] - 12) < 1e-6)

# ---------------------------------------------------------------------------
titulo("4. CONTAGEM: SIMULADOR == FORMULA EM MUITOS CASOS")
divergencias = 0
casos = 0
for semente in range(6):
    for densidade in (0.02, 0.05, 0.3):
        entradas, x = contagem_instrucoes.gerar_dados(densidade, 6, semente)
        for vlen in (128, 256, 512):
            for sew in (8, 16, 32):
                casos = casos + 1
                r = contagem_instrucoes.medir(entradas, x, 64, sew, vlen)
                if r["total_medido"] != r["total_formula"]:
                    divergencias = divergencias + 1
check("%d combinacoes (semente x densidade x VLEN x SEW) sem divergencia (%d)" % (
    casos, divergencias), divergencias == 0)

# ---------------------------------------------------------------------------
titulo("5. PROGRAMA NO SIMULADOR == MESMA CONTA FEITA DIRETO COM takum.py")
# Reproduz o algoritmo sem passar pelo simulador: vtdot por pedaco (fma com
# acumulador ampliado) e soma dos parciais com takum.add.
erros_bits = 0
erros_valor = 0
for sew in (8, 16, 32):
    entradas, x = contagem_instrucoes.gerar_dados(0.3, 2, 3)
    linhas = contagem_instrucoes.montar_linhas(entradas, 64, sew)
    x_bits = [takum.encode(v, sew) for v in x]
    r = contagem_instrucoes.medir(entradas, x, 64, sew, 128)
    n_acc = r["n_acc"]
    vlmax = 128 // sew

    esperado = []
    for linha in linhas:
        acc = None
        for inicio in range(0, len(linha), vlmax):
            parcial = takum.encode(0.0, n_acc)
            for c, b in linha[inicio:inicio + vlmax]:
                parcial = takum.fma(b, x_bits[c], parcial, sew, n_out=n_acc)
            if acc is None:
                acc = parcial
            else:
                acc = takum.add(acc, parcial, n_acc)
        if acc is None:
            acc = 0
        esperado.append(acc)
    if esperado != r["y_bits"]:
        erros_bits = erros_bits + 1

    # e o resultado tem que estar perto do exato. O erro e medido em relacao
    # a SOMA DOS |TERMOS| da linha (a escala natural do erro de uma soma):
    # medir em relacao ao resultado exagera quando ha cancelamento (termos
    # positivos e negativos quase se anulando), em qualquer formato.
    y_exato = eval_spmv.spmv_exato(entradas, x, 64)
    escala = [Fraction(0)] * 64
    for i, j, v in entradas:
        escala[i] = escala[i] + abs(Fraction(v) * Fraction(x[j]))
    tolerancia = {8: 0.3, 16: 2e-3, 32: 1e-6}[sew]
    for b, ye, esc in zip(r["y_bits"], y_exato, escala):
        if esc != 0:
            if abs(takum.decode(b, n_acc) - float(ye)) / float(esc) > tolerancia:
                erros_valor = erros_valor + 1
    check("T%-2d: bits de y identicos ao calculo direto (acumulador T%d)" % (sew, n_acc),
          erros_bits == 0)
check("y perto do exato em T8, T16 e T32, medido pela soma dos |termos| (%d fora)" % erros_valor,
      erros_valor == 0)

# ---------------------------------------------------------------------------
titulo("6. CENSO DE PADROES (analise_csr) CONTRA NUMPY E RELACOES CONHECIDAS")
tab_fp16 = analise_csr.tabela_do_formato("FP16")
ref16 = np.arange(65536, dtype=np.uint16).view(np.float16).astype(np.float64)

divergentes = 0
for (classe, valor), v_np in zip(tab_fp16, ref16):
    if classe == "nan":
        if not math.isnan(v_np):
            divergentes = divergentes + 1
    elif valor != v_np:
        divergentes = divergentes + 1
check("FP16: os 65536 padroes decodificam igual ao numpy (%d diferencas)" % divergentes,
      divergentes == 0)

c = analise_csr.censo(tab_fp16)
check("FP16: contagens batem com numpy (zero, inf, nan, subnormal)",
      c["zero"] == int(np.sum(ref16 == 0))
      and c["inf"] == int(np.sum(np.isinf(ref16)))
      and c["nan"] == int(np.sum(np.isnan(ref16)))
      and c["subnormal"] == int(np.sum((ref16 != 0) & (np.abs(ref16) < 2.0 ** -14))))
check("FP16: 2 zeros, 2 infinitos, 2046 NaN, 2046 subnormais, 61440 normais",
      (c["zero"], c["inf"], c["nan"], c["subnormal"], c["normal"]) == (2, 2, 2046, 2046, 61440))

# bfloat16 e o float32 sem os 16 bits de baixo
divergentes = 0
tab_bf = analise_csr.tabela_do_formato("bfloat16")
for p in range(65536):
    v32 = float(np.array([p << 16], dtype=np.uint32).view(np.float32)[0])
    classe, valor = tab_bf[p]
    if classe == "nan":
        if not math.isnan(v32):
            divergentes = divergentes + 1
    elif valor != v32:
        divergentes = divergentes + 1
check("bfloat16: os 65536 padroes batem com o float32 do numpy (%d diferencas)" % divergentes,
      divergentes == 0)

# E5M2 e exatamente o byte de cima do FP16
tab_e5 = analise_csr.tabela_do_formato("OFP8 E5M2")
divergentes = 0
for p in range(256):
    classe5, valor5 = tab_e5[p]
    classe16, valor16 = tab_fp16[p << 8]
    if classe5 != classe16 or not mesmo_valor(valor5, valor16):
        divergentes = divergentes + 1
check("E5M2 == byte de cima do FP16, nos 256 padroes (%d diferencas)" % divergentes,
      divergentes == 0)

# E4M3 (OFP8): valores conhecidos da especificacao
tab_e4 = analise_csr.tabela_do_formato("OFP8 E4M3")
check("E4M3: 0x38 = 1.0, 0x7E = 448 (maximo), 0x01 = 2^-9, 0x08 = 2^-6",
      tab_e4[0x38][1] == 1.0 and tab_e4[0x7E][1] == 448.0
      and tab_e4[0x01][1] == 2.0 ** -9 and tab_e4[0x08][1] == 2.0 ** -6)
check("E4M3: 0x7F e 0xFF sao NaN e nao existe infinito",
      tab_e4[0x7F][0] == "nan" and tab_e4[0xFF][0] == "nan"
      and analise_csr.censo(tab_e4)["inf"] == 0)
check("E5M2: maximo 57344 e menor subnormal 2^-16",
      tab_e5[0x7B][1] == 57344.0 and tab_e5[0x01][1] == 2.0 ** -16)

for nome, n in (("Takum T8", 8), ("Takum T16", 16)):
    c = analise_csr.censo(analise_csr.tabela_do_formato(nome))
    check("%s: 1 zero, 1 NaR e %d normais, sem subnormal nem infinito" % (nome, (1 << n) - 2),
          (c["zero"], c["nar"], c["normal"], c["subnormal"], c["inf"], c["nan"])
          == (1, 1, (1 << n) - 2, 0, 0, 0))
    check("%s: %d classes especiais (zero e NaR)" % (nome, 2),
          analise_csr.classes_especiais(c) == 2)

check("classes especiais: FP16=4, E5M2=4, E4M3=3",
      analise_csr.classes_especiais(analise_csr.censo(tab_fp16)) == 4
      and analise_csr.classes_especiais(analise_csr.censo(tab_e5)) == 4
      and analise_csr.classes_especiais(analise_csr.censo(tab_e4)) == 3)

# ---------------------------------------------------------------------------
titulo("7. EVENTOS DE EXCECAO (analise_csr) - CASOS FEITOS A MAO")
info16 = analise_csr.preparar_ieee(tab_fp16)
check("FP16: maximo 65504, overflow a partir de 65520, menor normal 2^-14",
      info16["maximo"] == 65504.0 and info16["limite_overflow"] == 65520.0
      and info16["menor_normal"] == 2.0 ** -14)
info_e4 = analise_csr.preparar_ieee(tab_e4)
check("E4M3: maximo 448, overflow a partir de 464",
      info_e4["maximo"] == 448.0 and info_e4["limite_overflow"] == 464.0)


def ev16(a, b, op):
    """Eventos IEEE para dois valores FP16 (a, b sao numeros)."""
    def par(v):
        if math.isnan(v):
            return ("nan", v)
        if math.isinf(v):
            return ("inf", v)
        if v == 0:
            return ("zero", v)
        return ("normal", v)
    return analise_csr.eventos_ieee(par(a), par(b), op, info16)


minimo = 2.0 ** -24
check("FP16: 60000 + 60000 -> OF", ev16(60000.0, 60000.0, "add") == ["OF"])
check("FP16: 65504 * 1 -> sem evento", ev16(65504.0, 1.0, "mul") == [])
check("FP16: minimo * minimo -> UF (minusculo e inexato)", ev16(minimo, minimo, "mul") == ["UF"])
check("FP16: minimo + minimo = 2^-23 exato -> sem UF", ev16(minimo, minimo, "add") == [])
check("FP16: 1 / 0 -> DZ", ev16(1.0, 0.0, "div") == ["DZ"])
check("FP16: 0 / 0 -> NV", ev16(0.0, 0.0, "div") == ["NV"])
check("FP16: inf - inf -> NV", ev16(math.inf, -math.inf, "add") == ["NV"])
check("FP16: 0 * inf -> NV", ev16(0.0, math.inf, "mul") == ["NV"])
check("FP16: inf + 1 e inf * 2 -> sem evento (inf ja era operando)",
      ev16(math.inf, 1.0, "add") == [] and ev16(math.inf, 2.0, "mul") == [])
check("FP16: operando NaN -> None (so propaga)", ev16(math.nan, 1.0, "add") is None)

info_t8 = analise_csr.preparar_takum(8)
maior8 = takum.decode(0x7F, 8)
menor8 = takum.decode(0x01, 8)


def evt8(a, b, op):
    """Eventos Takum T8 para dois numeros."""
    def par(v):
        if math.isnan(v):
            return ("nar", v)
        if v == 0:
            return ("zero", v)
        return ("normal", v)
    return analise_csr.eventos_takum(par(a), par(b), op, info_t8)


check("T8: maior * maior -> SAT", evt8(maior8, maior8, "mul") == ["SAT"])
check("T8: menor * menor -> CLAMP", evt8(menor8, menor8, "mul") == ["CLAMP"])
check("T8: 2 + 3 -> sem evento", evt8(2.0, 3.0, "add") == [])
check("T8: x + (-x) = 0 exato -> sem evento", evt8(2.5, -2.5, "add") == [])
check("T8: 1 / 0 e 0 / 0 -> NaR", evt8(1.0, 0.0, "div") == ["NaR"] and evt8(0.0, 0.0, "div") == ["NaR"])
check("T8: operando NaR -> None", evt8(math.nan, 1.0, "add") is None)

# Ponto medio: o limite fica NO MEIO entre o maior valor e o "proximo" (que nao
# existe), como o IEEE faz com o infinito. O espaco entre os dois maiores
# padroes vem direto do decode, sem usar a formula do analise_csr.
for n in (8, 16):
    mx = (1 << (n - 1)) - 1
    ell_max = 2.0 * math.log(takum.decode(mx, n))
    passo = ell_max - 2.0 * math.log(takum.decode(mx - 1, n))
    ell_min = 2.0 * math.log(takum.decode(1, n))
    passo_base = 2.0 * math.log(takum.decode(2, n)) - ell_min
    info = analise_csr.preparar_takum(n)

    def ev(ell):
        valor = math.exp(ell / 2.0)
        return analise_csr.eventos_takum(("normal", valor), ("normal", 1.0), "mul", info)

    check("T%-2d: 40%% de um passo acima do maior valor NAO e SAT" % n,
          ev(ell_max + 0.4 * passo) == [])
    check("T%-2d: 60%% de um passo acima do maior valor e SAT" % n,
          ev(ell_max + 0.6 * passo) == ["SAT"])
    check("T%-2d: 40%% de um passo abaixo do menor valor NAO e CLAMP" % n,
          ev(ell_min - 0.4 * passo_base) == [])
    check("T%-2d: 60%% de um passo abaixo do menor valor e CLAMP" % n,
          ev(ell_min - 0.6 * passo_base) == ["CLAMP"])

# SAT/CLAMP tem que concordar com o que o encode() de verdade faz
erros_sat = 0
erros_clamp = 0
for n in (8, 16):
    info = analise_csr.preparar_takum(n)
    max_padrao = (1 << (n - 1)) - 1
    random.seed(n)
    for _ in range(3000):
        r = 10.0 ** random.uniform(-110, 110)
        ell = 2.0 * math.log(r)
        padrao = takum.encode(r, n)
        if ell >= info["limite_sat"] and padrao != max_padrao:
            erros_sat = erros_sat + 1
        if ell <= info["limite_clamp"] and padrao != 1:
            erros_clamp = erros_clamp + 1
check("T8 e T16: acima do limite SAT o encode() devolve o maior padrao (%d erros)" % erros_sat,
      erros_sat == 0)
check("T8 e T16: abaixo do limite CLAMP o encode() devolve o menor padrao (%d erros)" % erros_clamp,
      erros_clamp == 0)

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

if len(falhas) > 0:
    sys.exit(1)
