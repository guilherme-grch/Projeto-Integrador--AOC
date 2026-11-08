"""
eval_acumulador.py - SpMV com ACUMULADOR AMPLIADO (Fase 3).

Existem dois experimentos diferentes no projeto:

  A) eval_spmv.py / analise_erro.py: TODA operacao (entrada, produto e soma)
     e arredondada para a largura do formato. E o pior caso de precisao.

  B) ESTE ARQUIVO: as entradas e x ficam na largura n, mas o produto e a soma
     sao acumulados numa largura MAIOR e arredondados uma vez por passo,
     como faz o vtdot.vv (T8 -> T16, T16 -> T32, T32 -> T32).
     Para a comparacao ser justa, o IEEE754 tambem recebe acumulador largo,
     que e a pratica em aprendizado de maquina:
         FP8 E4M3 / E5M2 -> acumula em FP16
         FP16            -> acumula em FP32
         FP32            -> acumula em FP32

Referencia: aritmetica exata (Fractions), a mesma do eval_spmv.py.
Mesmas matrizes e sementes do analise_erro.py (1000*faixa + t).

Rodar:  python3 eval_acumulador.py          (30 matrizes por cenario)
        python3 eval_acumulador.py 100
"""

import random
import sys

import numpy as np

import eval_spmv
import takum

TAMANHO = 64
DENSIDADE = 0.05
FAIXAS = [2, 12, 30]

F = eval_spmv.FORMATOS      # arredondadores por formato (entrada ou acumulador)

# formato de entrada -> (arredondador da entrada, nome e arredondador do acumulador)
PARES = {
    "FP8 E4M3":  (F["FP8 E4M3"],  "FP16", F["FP16"]),
    "FP8 E5M2":  (F["FP8 E5M2"],  "FP16", F["FP16"]),
    "FP16":      (F["FP16"],      "FP32", F["FP32"]),
    "FP32":      (F["FP32"],      "FP32", F["FP32"]),
    "Takum T8":  (F["Takum T8"],  "T16",  F["Takum T16"]),
    "Takum T16": (F["Takum T16"], "T32",  F["Takum T32"]),
    "Takum T32": (F["Takum T32"], "T32",  F["Takum T32"]),
}


def spmv_acumulador_largo(entradas, x, n, arred_entrada, arred_acc):
    """y = A.x: entradas na largura n; produto exato (float64) somado ao
    acumulador e arredondado UMA vez por passo (como math.fma / vtdot.vv)."""
    y = [0.0] * n
    xr = [arred_entrada(v) for v in x]
    for i, j, v in entradas:
        vr = arred_entrada(v)
        y[i] = arred_acc(y[i] + vr * xr[j])
    return y


def rodar_cenario(faixa, tentativas):
    """Devolve {formato: (erros do experimento A, erros do experimento B)}."""
    erros = {}
    for nome in PARES:
        erros[nome] = ([], [])
    for t in range(tentativas):
        random.seed(1000 * faixa + t)
        entradas = eval_spmv.gerar_matriz_esparsa(TAMANHO, DENSIDADE, faixa)
        x = []
        for _ in range(TAMANHO):
            x.append(random.choice([-1.0, 1.0]) * 10.0 ** random.uniform(-1, 1))
        y_ref = eval_spmv.spmv_exato(entradas, x, TAMANHO)
        for nome, (arred_in, _, arred_acc) in PARES.items():
            y_a = eval_spmv.spmv_formato(entradas, x, TAMANHO, arred_in)
            y_b = spmv_acumulador_largo(entradas, x, TAMANHO, arred_in, arred_acc)
            erros[nome][0].extend(eval_spmv.erro_relativo(y_a, y_ref))
            erros[nome][1].extend(eval_spmv.erro_relativo(y_b, y_ref))
    return erros


def main():
    tentativas = 30
    if len(sys.argv) > 1:
        tentativas = int(sys.argv[1])

    print("EXPERIMENTO B - SpMV com acumulador ampliado (estilo vtdot.vv)")
    print("A = tudo arredondado na largura n   |   B = entradas em n, acumulador largo")
    print("%d matrizes %dx%d por cenario, densidade %.0f%%, sementes 1000*faixa+t" % (
        tentativas, TAMANHO, TAMANHO, 100 * DENSIDADE))

    with np.errstate(all="ignore"):
        for faixa in FAIXAS:
            erros = rodar_cenario(faixa, tentativas)
            print()
            print("=" * 78)
            print("CENARIO: faixa dinamica ~10^%d" % faixa)
            print("=" * 78)
            print("  %-10s %-6s | %9s %11s | %9s %11s | %8s" % (
                "formato", "acc", "A: estouro", "A: mediana", "B: estouro",
                "B: mediana", "B melhora"))
            print("  " + "-" * 74)
            for nome, (e_a, e_b) in erros.items():
                st_a = eval_spmv.estatisticas(e_a)
                st_b = eval_spmv.estatisticas(e_b)
                if st_b["mediana"] > 0 and st_a["mediana"] > 0:
                    ganho = "%7.1fx" % (st_a["mediana"] / st_b["mediana"])
                else:
                    ganho = "%8s" % "-"
                print("  %-10s %-6s | %8.1f%% %11.2e | %8.1f%% %11.2e | %s" % (
                    nome, PARES[nome][1], st_a["falhas_%"], st_a["mediana"],
                    st_b["falhas_%"], st_b["mediana"], ganho))
    print()
    print("""LEITURA:
  - Acumular mais largo ajuda os dois lados, mas NAO resolve o estouro das
    ENTRADAS: se o valor ja nao cabe em FP8/FP16 (ou em T8), o erro vem antes
    da soma.
  - Compare as linhas do MESMO acumulador: Takum T16 acumulando em T32 contra
    FP16 acumulando em FP32, e Takum T8 em T16 contra FP8 em FP16.
  - Os numeros dependem das matrizes sinteticas (valores com expoente
    uniforme); nao sao taxas de um programa real.""")
    print("OK: experimento B concluido")


if __name__ == "__main__":
    main()
