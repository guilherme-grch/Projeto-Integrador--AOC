"""
eval_spmv.py - Avaliacao experimental (Fase 3).

Compara a precisao do formato Takum (T8/T16/T32) contra o IEEE754
(FP8 E4M3, FP8 E5M2, FP16, FP32) num kernel de multiplicacao
matriz-vetor esparsa:   y = A . x

A referencia "de ouro" usa aritmetica EXATA com fracoes racionais
(fractions.Fraction), que e ainda mais rigorosa que Float128 - assim
o erro medido e puramente do formato testado, sem contaminacao da
referencia.

Rodar com:  python3 eval_spmv.py
"""

import math
import random
from fractions import Fraction

import numpy as np

import takum

random.seed(42)
np.random.seed(42)


# ---------------------------------------------------------------------------
# Emulacao dos formatos IEEE754 de baixa precisao
# ---------------------------------------------------------------------------

def round_ieee(x: float, exp_bits: int, mant_bits: int, estilo: str = "ieee") -> float:
    """Arredonda um float para um formato de ponto flutuante de baixa precisao.

    estilo="ieee": expoente todo 1 reservado para infinito/NaN (FP16, OFP8 E5M2).
    estilo="e4m3": OFP8 E4M3 - NAO tem infinito; o expoente todo 1 vale como
                   numero normal e so S.1111.111 e NaN. Maior valor = 448.

    Arredondamento: para o mais proximo, empate para o par. Resultado acima do
    maior valor (ja apos arredondar) vira inf, que o benchmark conta como
    estouro (no E4M3 real, e o NaN da conversao sem saturacao).
    """
    if x == 0.0 or math.isnan(x) or math.isinf(x):
        return x

    bias = (1 << (exp_bits - 1)) - 1
    if estilo == "e4m3":
        exp_max = (1 << exp_bits) - 1 - bias          # 15 - 7 = 8
        mant_max = (1 << mant_bits) - 2               # S.1111.111 e NaN
    else:
        exp_max = (1 << exp_bits) - 2 - bias          # maior expoente normal
        mant_max = (1 << mant_bits) - 1
    exp_min = 1 - bias                                # menor expoente normal
    maximo = (1.0 + mant_max / (1 << mant_bits)) * 2.0 ** exp_max

    sinal = math.copysign(1.0, x)
    mag = abs(x)

    # e = piso(log2(mag)) exato (frexp nao erra perto de potencias de 2)
    e = math.frexp(mag)[1] - 1
    if e < exp_min:
        passo = 2.0 ** (exp_min - mant_bits)          # regiao subnormal
    else:
        passo = 2.0 ** (e - mant_bits)
    r = round(mag / passo) * passo                    # round(): empate -> par

    if r > maximo:                                    # estouro (inclui o que
        return sinal * float("inf")                   # estoura ao arredondar)
    return sinal * r


FORMATOS = {
    # nome            : (funcao_arredonda, funcao_decodifica_para_float)
    "FP8 E4M3":  lambda v: round_ieee(v, 4, 3, "e4m3"),
    "FP8 E5M2":  lambda v: round_ieee(v, 5, 2),
    "FP16":      lambda v: float(np.float16(v)),
    "FP32":      lambda v: float(np.float32(v)),
    "Takum T8":  lambda v: takum.decode(takum.encode(v, 8), 8),
    "Takum T16": lambda v: takum.decode(takum.encode(v, 16), 16),
    "Takum T32": lambda v: takum.decode(takum.encode(v, 32), 32),
}


# ---------------------------------------------------------------------------
# Geracao da matriz esparsa
# ---------------------------------------------------------------------------

def gerar_matriz_esparsa(n: int, densidade: float, faixa_dinamica: float):
    """Gera uma matriz esparsa n x n em formato de lista de (linha, col, valor).

    `faixa_dinamica` controla quantas ordens de grandeza os valores cobrem.
    Faixa grande e justamente onde o Takum deve levar vantagem sobre o FP8.
    """
    entradas = []
    n_nz = max(n, int(n * n * densidade))
    vistos = set()
    while len(entradas) < n_nz:
        i = random.randrange(n)
        j = random.randrange(n)
        if (i, j) in vistos:
            continue
        vistos.add((i, j))
        expoente = random.uniform(-faixa_dinamica / 2, faixa_dinamica / 2)
        valor = random.choice([-1.0, 1.0]) * (10.0 ** expoente)
        entradas.append((i, j, valor))
    return entradas


def spmv_exato(entradas, x, n):
    """SpMV de referencia com aritmetica EXATA (fracoes racionais)."""
    y = [Fraction(0) for _ in range(n)]
    xf = [Fraction(v) for v in x]
    for i, j, v in entradas:
        y[i] += Fraction(v) * xf[j]
    return y


def spmv_formato(entradas, x, n, arredonda):
    """SpMV simulando um formato numerico: TODO valor intermediario
    passa pelo arredondamento do formato (entradas, produtos e acumulador)."""
    y = [0.0] * n
    xr = [arredonda(v) for v in x]
    for i, j, v in entradas:
        vr = arredonda(v)
        produto = arredonda(vr * xr[j])
        y[i] = arredonda(y[i] + produto)
    return y


def erro_relativo(y_teste, y_exato):
    """Erro relativo por elemento, comparado a referencia exata.

    A diferenca e calculada com Fractions (sem converter a referencia para
    float antes), para nao perder precisao quando o erro e muito pequeno.
    Estouro (inf/NaN) devolve inf; referencia igual a zero e ignorada.
    """
    erros = []
    for yt, ye in zip(y_teste, y_exato):
        ye = Fraction(ye)
        if ye == 0:
            continue
        if math.isnan(yt) or math.isinf(yt):
            erros.append(float("inf"))
            continue
        erros.append(float(abs((Fraction(yt) - ye) / ye)))
    return erros


def estatisticas(erros):
    """Estatisticas de erro.

    CUIDADO METODOLOGICO (importante para o artigo):
    Se calcularmos a mediana apenas sobre os elementos que NAO estouraram,
    criamos vies de sobrevivencia: um formato que estoura em 70% dos casos
    pareceria "preciso" porque so medimos os 30% que deram certo.

    Por isso reportamos DUAS coisas:
      - estatisticas condicionais (so os finitos), marcadas com "_fin"
      - erro COMBINADO, onde um estouro conta como erro de 100% (1.0),
        ja que um resultado infinito nao carrega informacao nenhuma.
    O erro combinado e a metrica honesta para comparar formatos.
    """
    finitos = [e for e in erros if math.isfinite(e)]
    n_inf = len(erros) - len(finitos)

    # erro combinado: estouro = 100% de erro; erros acima de 100% sao
    # saturados em 100% (nao faz sentido dizer que um e "10x pior" que outro
    # quando ambos ja perderam todo o significado)
    combinados = sorted(min(e, 1.0) if math.isfinite(e) else 1.0 for e in erros)

    def percentil(lista, q):
        if not lista:
            return float("nan")
        return lista[min(int(q * (len(lista) - 1)), len(lista) - 1)]

    finitos_ord = sorted(finitos)
    return {
        "mediana_fin": percentil(finitos_ord, 0.5) if finitos else float("inf"),
        "mediana": percentil(combinados, 0.5),
        "p95": percentil(combinados, 0.95),
        "falhas_%": 100.0 * n_inf / len(erros) if erros else 0.0,
    }


# ---------------------------------------------------------------------------
# Experimento principal
# ---------------------------------------------------------------------------

def rodar_experimento(n, densidade, faixa_dinamica, rotulo):
    print()
    print("=" * 78)
    print(f"EXPERIMENTO: {rotulo}")
    print(f"  matriz {n}x{n}, densidade {densidade:.1%}, "
          f"faixa dinamica ~10^{faixa_dinamica:.0f}")
    print("=" * 78)

    entradas = gerar_matriz_esparsa(n, densidade, faixa_dinamica)
    x = [random.choice([-1.0, 1.0]) * (10.0 ** random.uniform(-1, 1))
         for _ in range(n)]

    y_ref = spmv_exato(entradas, x, n)

    print(f"  nao-zeros: {len(entradas)}")
    print()
    print(f"  {'formato':<12} {'bits':>5} {'overflow':>9} "
          f"{'mediana(so finitos)':>20} {'mediana COMBINADA':>19}")
    print("  " + "-" * 70)

    bits_de = {"FP8 E4M3": 8, "FP8 E5M2": 8, "FP16": 16, "FP32": 32,
               "Takum T8": 8, "Takum T16": 16, "Takum T32": 32}

    resultados = {}
    for nome, arredonda in FORMATOS.items():
        y = spmv_formato(entradas, x, n, arredonda)
        st = estatisticas(erro_relativo(y, y_ref))
        resultados[nome] = st
        print(f"  {nome:<12} {bits_de[nome]:>5} {st['falhas_%']:>8.1f}% "
              f"{st['mediana_fin']:>20.3e} {st['mediana']:>19.3e}")

    print()
    print("  Nota: 'so finitos' ignora os elementos que estouraram, o que")
    print("        favorece artificialmente formatos com muito overflow.")
    print("        A metrica honesta e a COMBINADA (estouro = erro de 100%).")

    # comparacao direta por largura de bits, usando a metrica combinada
    print()
    print("  Comparacao justa (mesma largura de bits, metrica combinada):")
    for bits, (ieee, tk) in {
        8: ("FP8 E4M3", "Takum T8"),
        16: ("FP16", "Takum T16"),
        32: ("FP32", "Takum T32"),
    }.items():
        ei, et = resultados[ieee]["mediana"], resultados[tk]["mediana"]
        if et > 0 and ei > 0:
            razao = ei / et
            vencedor = "Takum" if razao > 1 else "IEEE754"
            print(f"    {bits:>2} bits: {ieee:<9} {ei:.2e}  vs  "
                  f"{tk:<10} {et:.2e}   -> {vencedor} melhor "
                  f"({max(razao, 1/razao):.1f}x)")
    return resultados


if __name__ == "__main__":
    print("AVALIACAO EXPERIMENTAL - Takum vs IEEE754 em SpMV (y = A.x)")
    print("Referencia: aritmetica exata com fracoes racionais")

    # Cenario 1: faixa dinamica MODERADA (favorece mantissa maior)
    rodar_experimento(n=64, densidade=0.05, faixa_dinamica=2,
                      rotulo="faixa dinamica estreita (~10^2)")

    # Cenario 2: faixa dinamica AMPLA (favorece o Takum)
    rodar_experimento(n=64, densidade=0.05, faixa_dinamica=12,
                      rotulo="faixa dinamica ampla (~10^12)")

    # Cenario 3: faixa dinamica EXTREMA (onde o FP8 quebra)
    rodar_experimento(n=64, densidade=0.05, faixa_dinamica=30,
                      rotulo="faixa dinamica extrema (~10^30)")

    print()
    print("=" * 78)
    print("OBSERVACAO PARA O ARTIGO")
    print("=" * 78)
    print("""
  O resultado esperado e que o Takum NAO vence em todos os cenarios.
  Com faixa dinamica estreita, o IEEE754 tende a ganhar porque gasta
  menos bits com expoente e mais com mantissa. Conforme a faixa
  dinamica cresce, o FP8 comeca a estourar (overflow -> inf) enquanto
  o Takum continua representando os valores.

  Esse trade-off e exatamente o resultado interessante a discutir na
  secao "Results and Discussion" - um artigo que diz "ganhamos sempre"
  costuma ser menos convincente que um que caracteriza ONDE se ganha.
""")
