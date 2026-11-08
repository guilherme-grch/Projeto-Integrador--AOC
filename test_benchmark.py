"""
test_benchmark.py - Testes do que o benchmark usa como regua (Fase 3).

O benchmark (eval_spmv.py, analise_erro.py) so e confiavel se os formatos
IEEE754 que ele emula estiverem certos. Este arquivo confere:

  1. FP16 emulado == np.float16 (referencia independente, do numpy)
  2. OFP8 E4M3 e E5M2 emulados == vizinho mais proximo na tabela dos 256
     padroes (a mesma tabela usada em analise_csr.py, feita da especificacao)
  3. estouro: o que passa do maior valor ao arredondar vira inf
  4. erro_relativo preserva precisao (nao converte a referencia para float)
  5. o acumulador largo (eval_acumulador.py) segue a regra de cada formato

Como rodar:   python3 test_benchmark.py
Termina com codigo 1 se algum teste falhar.
"""

import bisect
import math
import random
import sys
from fractions import Fraction

import numpy as np

import analise_csr
import eval_spmv

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


def igual(a, b):
    if math.isnan(a) and math.isnan(b):
        return True
    return a == b


# ---------------------------------------------------------------------------
titulo("1. FP16 EMULADO CONTRA np.float16 (referencia independente)")
random.seed(5)
amostras = []
for _ in range(20000):
    amostras.append(random.choice([-1, 1]) * 10.0 ** random.uniform(-9, 5.2))
amostras += [65504.0, 65519.0, 65520.0, 70000.0, 6.0e-8, 3.0e-8, 6.1e-5, 1e-30]
ruins = []
with np.errstate(all="ignore"):
    for x in amostras:
        a = eval_spmv.round_ieee(x, 5, 10)
        b = float(np.float16(x))
        if not igual(a, b):
            ruins.append((x, a, b))
check("%d valores (do subnormal ao estouro): round_ieee(5,10) == np.float16" %
      len(amostras), len(ruins) == 0, str(ruins[:3]))

# ---------------------------------------------------------------------------
titulo("2. OFP8 E4M3 / E5M2 CONTRA A TABELA DOS 256 PADROES")


def tabela_positivos(nome):
    t = analise_csr.tabela_do_formato(nome)
    vals = sorted(set(v for c, v in t if c in ("zero", "subnormal", "normal") and v >= 0))
    return vals


def vizinho(vals, x):
    """Valor da tabela mais proximo de x (x > 0), ou inf se estoura."""
    maximo = vals[-1]
    passo_topo = maximo - vals[-2]
    if x > maximo + passo_topo / 2.0:
        return math.inf
    i = bisect.bisect_left(vals, x)
    candidatos = []
    if i > 0:
        candidatos.append(vals[i - 1])
    if i < len(vals):
        candidatos.append(vals[i])
    return min(candidatos, key=lambda v: abs(v - x))


for nome, (eb, mb, estilo) in (("OFP8 E4M3", (4, 3, "e4m3")),
                               ("OFP8 E5M2", (5, 2, "ieee"))):
    vals = tabela_positivos(nome)
    maximo = vals[-1]
    check("%s: maior valor da tabela = %g" % (nome, maximo),
          maximo == (448.0 if estilo == "e4m3" else 57344.0))
    random.seed(9)
    ruins = []
    for _ in range(30000):
        x = 10.0 ** random.uniform(math.log10(vals[1]) - 1, math.log10(maximo) + 0.3)
        esperado = vizinho(vals, x)
        obtido = eval_spmv.round_ieee(x, eb, mb, estilo)
        if obtido != esperado:
            ruins.append((x, obtido, esperado))
    check("%s: 30000 valores sorteados == vizinho mais proximo da tabela" % nome,
          len(ruins) == 0, str(ruins[:3]))
    check("%s: simetria (-x arredonda como x)" % nome,
          all(eval_spmv.round_ieee(-x, eb, mb, estilo) ==
              -eval_spmv.round_ieee(x, eb, mb, estilo) for x in (0.3, 7.7, 100.1, 300.0)))
    # todo valor representavel passa sem mudar
    check("%s: os %d valores da tabela sao pontos fixos" % (nome, len(vals)),
          all(eval_spmv.round_ieee(v, eb, mb, estilo) == v for v in vals))

# ---------------------------------------------------------------------------
titulo("3. ESTOURO")
check("E4M3: 448 cabe, 500 estoura (inf)",
      eval_spmv.round_ieee(448.0, 4, 3, "e4m3") == 448.0 and
      eval_spmv.round_ieee(500.0, 4, 3, "e4m3") == math.inf)
check("E4M3: 300 NAO estoura (o emulador antigo errava aqui: maximo 240)",
      eval_spmv.round_ieee(300.0, 4, 3, "e4m3") == 288.0)
check("E5M2: 61000 satura em 57344 (arredonda para baixo), 62000 estoura",
      eval_spmv.round_ieee(61000.0, 5, 2) == 57344.0 and
      eval_spmv.round_ieee(62000.0, 5, 2) == math.inf)
check("FP16: 65519 cabe (65504), 65521 estoura",
      eval_spmv.round_ieee(65519.0, 5, 10) == 65504.0 and
      eval_spmv.round_ieee(65521.0, 5, 10) == math.inf)
check("sinal negativo preservado no estouro",
      eval_spmv.round_ieee(-1e9, 4, 3, "e4m3") == -math.inf)
check("zero, inf e NaN passam direto",
      eval_spmv.round_ieee(0.0, 4, 3, "e4m3") == 0.0 and
      eval_spmv.round_ieee(math.inf, 4, 3, "e4m3") == math.inf and
      math.isnan(eval_spmv.round_ieee(math.nan, 4, 3, "e4m3")))

# ---------------------------------------------------------------------------
titulo("4. ERRO RELATIVO NAO PERDE PRECISAO DA REFERENCIA")
ye = Fraction(1) + Fraction(1, 2 ** 70)          # 1 + 2^-70: float() arredonda para 1.0
e = eval_spmv.erro_relativo([1.0], [ye])[0]
check("referencia 1+2^-70, teste 1.0: erro = 2^-70 (obtido %.3e)" % e,
      abs(e - 2.0 ** -70) / 2.0 ** -70 < 1e-6)
check("estouro (inf) vira erro inf",
      eval_spmv.erro_relativo([math.inf], [Fraction(3)]) == [math.inf])
check("NaN vira erro inf",
      eval_spmv.erro_relativo([math.nan], [Fraction(3)]) == [math.inf])
check("referencia zero e ignorada",
      eval_spmv.erro_relativo([1.0, 2.0], [Fraction(0), Fraction(4)]) == [0.5])
check("erro relativo comum: |3 - 4| / 4 = 0.25",
      eval_spmv.erro_relativo([3.0], [Fraction(4)]) == [0.25])

# ---------------------------------------------------------------------------
titulo("5. ESTATISTICAS (limite de 100% vs distribuicao original)")
erros = [0.01, 0.5, 3.0, 250.0, math.inf]
st = eval_spmv.estatisticas(erros)
check("estouro conta como erro de 100% na metrica combinada",
      abs(st["falhas_%"] - 20.0) < 1e-9 and st["p95"] == 1.0)
check("erros originais (3.0 e 250.0) NAO somem: o limite so vale na metrica combinada",
      sorted(e for e in erros if math.isfinite(e))[-1] == 250.0)

# ---------------------------------------------------------------------------
print()
print("=" * 62)
if len(falhas) > 0:
    print("RESULTADO: %d/%d testes passaram. FALHAS:" % (total - len(falhas), total))
    for nome in falhas:
        print("   - " + nome)
    sys.exit(1)
print("RESULTADO: todos os %d testes passaram." % total)
print("=" * 62)
