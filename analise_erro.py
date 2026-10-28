"""
analise_erro.py - Distribuicao do erro relativo contra Float128 (Fase 3).

O enunciado pede: "calcular a distribuicao do erro relativo acumulado em
relacao a precisao quadrupla (Float128)". Este script faz isso em 3 passos:

  1. REFERENCIA FLOAT128: o Python nao tem float128 de verdade (o
     np.longdouble tem so 64 bits de significando). Entao emulamos o
     binary128 do IEEE 754: 113 bits de significando, arredondando para o
     mais proximo (empate -> par) a CADA operacao da referencia.

  2. VALIDACAO: conferimos que essa referencia quadrupla praticamente
     coincide com a aritmetica EXATA (fracoes), que usamos no eval_spmv.py.

  3. DISTRIBUICAO: em vez de so a mediana, mostramos percentis (50, 90, 95,
     99, maximo) e um histograma do erro de TODOS os elementos de y, somando
     varias matrizes aleatorias por cenario (muito mais amostras).

Regra do erro (a mesma do eval_spmv.py, para nao haver vies de sobrevivencia):
  estouro (inf/NaN) conta como erro de 100%, e erros acima de 100% sao
  limitados a 100%.

Rodar:  python3 analise_erro.py          (30 matrizes por cenario)
        python3 analise_erro.py 100      (100 matrizes por cenario)
Gera tambem a figura  figuras/distribuicao_erro.png  (se tiver matplotlib).
"""

import math
import os
import random
import sys
from fractions import Fraction

import numpy as np

import eval_spmv

PRECISAO_QUAD = 113                  # bits de significando do binary128
FAIXAS = [2, 12, 30]                 # ordens de grandeza dos valores da matriz
TAMANHO = 64                         # matriz TAMANHO x TAMANHO
DENSIDADE = 0.05

LIMITES = [1e-7, 1e-5, 1e-3, 1e-2, 1e-1, 1.0]
ROTULOS = ["<1e-7", "1e-7..1e-5", "1e-5..1e-3", "1e-3..1e-2",
           "1e-2..1e-1", "1e-1..1", ">=1 (100%)"]


# ---------------------------------------------------------------------------
# Referencia Float128 (binary128 emulado com fracoes)
# ---------------------------------------------------------------------------
def arredonda_quad(f):
    """Arredonda uma Fraction para 113 bits de significando (empate -> par).

    Ignoramos a faixa de expoentes do binary128 (+-16383): os nossos
    valores ficam muito longe dela.
    """
    if f == 0:
        return Fraction(0)

    sinal = 1
    if f < 0:
        sinal = -1
    m = abs(f)

    # e = piso(log2(m)), calculado so com inteiros (sem erro de float)
    e = m.numerator.bit_length() - m.denominator.bit_length()
    if Fraction(2) ** e > m:
        e = e - 1

    # coloca m numa escala em que o significando e um inteiro de 113 bits
    passo = Fraction(2) ** (e - (PRECISAO_QUAD - 1))
    inteiro = round(m / passo)            # round() de Fraction: empate -> par
    return sinal * inteiro * passo


def spmv_quad(entradas, x, n):
    """y = A.x com TODA operacao arredondada para Float128."""
    y = [Fraction(0)] * n
    xf = [Fraction(v) for v in x]
    for i, j, v in entradas:
        produto = arredonda_quad(Fraction(v) * xf[j])
        y[i] = arredonda_quad(y[i] + produto)
    return y


def maior_diferenca_relativa(y_a, y_b):
    """Maior |a - b| / |b| entre dois vetores de Fractions (ignora b = 0)."""
    maior = 0.0
    for a, b in zip(y_a, y_b):
        if b != 0:
            d = float(abs((a - b) / b))
            if d > maior:
                maior = d
    return maior


# ---------------------------------------------------------------------------
# Estatisticas da distribuicao
# ---------------------------------------------------------------------------
def combinar(erros):
    """Estouro (inf/NaN) vira 100%; erros acima de 100% sao limitados a 100%."""
    saida = []
    for e in erros:
        if math.isfinite(e):
            saida.append(min(e, 1.0))
        else:
            saida.append(1.0)
    return saida


def percentil(lista_ordenada, q):
    """Percentil por posicao (mesma regra do eval_spmv.py)."""
    if len(lista_ordenada) == 0:
        return float("nan")
    posicao = int(q * (len(lista_ordenada) - 1))
    return lista_ordenada[posicao]


def histograma(combinados):
    """Quantos elementos caem em cada faixa de erro (ver ROTULOS)."""
    contagem = [0] * len(ROTULOS)
    for e in combinados:
        k = 0
        while k < len(LIMITES) and e >= LIMITES[k]:
            k = k + 1
        contagem[k] = contagem[k] + 1
    return contagem


def resumo(erros):
    """Dicionario com overflow, percentis e histograma de uma lista de erros."""
    combinados = sorted(combinar(erros))
    n_estouro = 0
    for e in erros:
        if not math.isfinite(e):
            n_estouro = n_estouro + 1
    total = len(erros)
    return {
        "amostras": total,
        "overflow_%": 100.0 * n_estouro / total,
        "p50": percentil(combinados, 0.50),
        "p90": percentil(combinados, 0.90),
        "p95": percentil(combinados, 0.95),
        "p99": percentil(combinados, 0.99),
        "max": combinados[-1],
        "hist": histograma(combinados),
        "ordenados": combinados,
    }


# ---------------------------------------------------------------------------
# Um cenario = varias matrizes aleatorias com a mesma faixa dinamica
# ---------------------------------------------------------------------------
def rodar_cenario(faixa, tentativas):
    """Devolve (erros por formato, maior diferenca quad-vs-exato)."""
    erros = {}
    for nome in eval_spmv.FORMATOS:
        erros[nome] = []
    diferenca = 0.0

    for t in range(tentativas):
        random.seed(1000 * faixa + t)     # reprodutivel
        entradas = eval_spmv.gerar_matriz_esparsa(TAMANHO, DENSIDADE, faixa)
        x = []
        for _ in range(TAMANHO):
            x.append(random.choice([-1.0, 1.0]) * 10.0 ** random.uniform(-1, 1))

        y_quad = spmv_quad(entradas, x, TAMANHO)
        y_exato = eval_spmv.spmv_exato(entradas, x, TAMANHO)
        d = maior_diferenca_relativa(y_quad, y_exato)
        if d > diferenca:
            diferenca = d

        for nome, arredonda in eval_spmv.FORMATOS.items():
            y = eval_spmv.spmv_formato(entradas, x, TAMANHO, arredonda)
            erros[nome] = erros[nome] + eval_spmv.erro_relativo(y, y_quad)

    return erros, diferenca


def imprimir_cenario(faixa, resumos):
    print()
    print("=" * 78)
    print("CENARIO: faixa dinamica ~10^%d  (%d elementos de y por formato)" % (
        faixa, resumos["Takum T8"]["amostras"]))
    print("=" * 78)
    print("  %-10s %9s %9s %9s %9s %9s %9s" % (
        "formato", "overflow", "p50", "p90", "p95", "p99", "max"))
    print("  " + "-" * 70)
    for nome, r in resumos.items():
        print("  %-10s %8.1f%% %9.2e %9.2e %9.2e %9.2e %9.2e" % (
            nome, r["overflow_%"], r["p50"], r["p90"], r["p95"], r["p99"], r["max"]))

    print()
    print("  Histograma: porcentagem dos elementos de y em cada faixa de erro relativo")
    cabecalho = "  %-10s" % "formato"
    for rotulo in ROTULOS:
        cabecalho = cabecalho + " %11s" % rotulo
    print(cabecalho)
    print("  " + "-" * (10 + 12 * len(ROTULOS)))
    for nome, r in resumos.items():
        linha = "  %-10s" % nome
        for contagem in r["hist"]:
            linha = linha + " %10.1f%%" % (100.0 * contagem / r["amostras"])
        print(linha)


# ---------------------------------------------------------------------------
# Figura: distribuicao acumulada (CDF) do erro, uma por cenario
# ---------------------------------------------------------------------------
def gerar_figura(todos, caminho):
    """Desenha a CDF do erro combinado. Devolve True se conseguiu."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    # mesmas cores dos outros graficos do artigo (cor segue o formato)
    cores = {"FP8 E4M3": "#d62728", "FP8 E5M2": "#ff7f0e", "FP16": "#bcbd22",
             "FP32": "#7f7f7f", "Takum T8": "#1f77b4", "Takum T16": "#2ca02c",
             "Takum T32": "#17becf"}

    plt.rcParams.update({"font.size": 8, "font.family": "serif",
                         "axes.grid": True, "grid.alpha": 0.3})
    fig, eixos = plt.subplots(1, len(todos), figsize=(7.2, 3.3), sharey=True)

    for eixo, (faixa, resumos) in zip(eixos, todos.items()):
        for nome, r in resumos.items():
            valores = r["ordenados"]
            # erro 0 nao aparece em escala log: desenha em 1e-12
            xs = [max(v, 1e-12) for v in valores]
            ys = [(i + 1) / len(valores) for i in range(len(valores))]
            estilo = "-"
            if not nome.startswith("Takum"):
                estilo = "--"
            eixo.plot(xs, ys, estilo, color=cores[nome], linewidth=1.3, label=nome)
        eixo.set_xscale("log")
        eixo.set_xlim(1e-10, 1.5)
        eixo.set_ylim(0, 1.02)
        eixo.set_title("range $10^{%d}$" % faixa)
        eixo.set_xlabel("relative error (overflow = 1)")
    eixos[0].set_ylabel("fraction of outputs with error $\\leq x$")
    # legenda unica embaixo (no canto do grafico ela esconderia as curvas)
    handles, rotulos = eixos[0].get_legend_handles_labels()
    fig.legend(handles, rotulos, loc="lower center", ncol=7, fontsize=6.5,
               frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))

    pasta = os.path.dirname(caminho)
    if pasta != "" and not os.path.isdir(pasta):
        os.makedirs(pasta)
    fig.savefig(caminho, dpi=200)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    tentativas = 30
    if len(sys.argv) > 1:
        tentativas = int(sys.argv[1])

    print("DISTRIBUICAO DO ERRO RELATIVO - Takum vs IEEE754 em SpMV (y = A.x)")
    print("Referencia: Float128 emulado (binary128, %d bits de significando)" % PRECISAO_QUAD)
    print("%d matrizes %dx%d por cenario, densidade %.0f%%" % (
        tentativas, TAMANHO, TAMANHO, 100 * DENSIDADE))

    todos = {}
    maior_dif = 0.0
    with np.errstate(all="ignore"):           # FP16 estoura de proposito
        for faixa in FAIXAS:
            erros, dif = rodar_cenario(faixa, tentativas)
            if dif > maior_dif:
                maior_dif = dif
            resumos = {}
            for nome in erros:
                resumos[nome] = resumo(erros[nome])
            todos[faixa] = resumos
            imprimir_cenario(faixa, resumos)

    print()
    print("=" * 78)
    print("VALIDACAO DA REFERENCIA")
    print("=" * 78)
    limite = 1e-30
    print("  maior |Float128 - exato| / |exato| em todos os elementos: %.2e" % maior_dif)
    print("  (1 unidade do binary128 vale ~%.1e; o limite aceito aqui e %.0e)" % (
        2.0 ** -112, limite))

    figura = "figuras/distribuicao_erro.png"
    if gerar_figura(todos, figura):
        print("  figura gerada: " + figura)
    else:
        print("  matplotlib nao encontrado: figura nao gerada")

    if maior_dif > limite:
        print("  FALHA: a referencia quadrupla nao bate com a exata")
        sys.exit(1)
    print("  OK: usar a referencia exata (eval_spmv.py) ou Float128 da o mesmo resultado")


if __name__ == "__main__":
    main()
