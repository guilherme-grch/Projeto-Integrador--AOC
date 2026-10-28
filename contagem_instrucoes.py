"""
contagem_instrucoes.py - Contagem de instrucoes do SpMV (Fase 3).

O enunciado pede para "analisar a reducao na complexidade de instrucoes".
Aqui o SpMV (y = A.x, matriz no formato CSR) e EXECUTADO de verdade no
simulador Zvtakum (zvtakum.py), e as instrucoes sao contadas por ele.

Tres programas sao comparados, para a mesma matriz:

  1. ESCALAR  (sem extensao vetorial), por nao-zero:
        lw valor, lw coluna, lw x[coluna], mul, add      = 5 instrucoes
     por linha: zerar acumulador + guardar y[i]          = 2 instrucoes

  2. RVV IEEE754 (vetorial padrao do RVV 1.0), por pedaco de ate VLMAX nao-zeros:
        vsetvli, vle (valores), vle (colunas), vluxei (gather de x),
        vfmul.vv, vfredusum.vs                           = 6 instrucoes
     por linha: vfmv.s.f (acumulador inicial) + guardar y[i] = 2 instrucoes

  3. Zvtakum, por pedaco:
        vsetvli, vle, vle, vluxei, vtdot.vv              = 5 instrucoes
     (o vtdot.vv faz multiplicacao + reducao numa instrucao so)
     por linha: guardar y[i]                             = 1 instrucao
     Se a linha tem mais de um pedaco, o vtdot nao recebe acumulador
     (diferente do vfredusum), entao cada pedaco extra custa mais
     2 instrucoes: vsetvli + vtadd.vv para somar os parciais.

IMPORTANTE - o que e medido e o que e modelo:
  - As instrucoes do Zvtakum (vsetvli, vtdot, vtadd) sao contadas pelo
    simulador (cpu.contador_instr), executadas de verdade.
  - As cargas/gravacoes (vle, vluxei, guardar y) NAO fazem parte do
    Zvtakum: sao instrucoes RVV comuns, que movem bits sem olhar o formato.
    Elas sao contadas aqui por modelo (3 por pedaco + 1 por linha).
  - Ignoramos aritmetica de enderecos e controle de laco: sao iguais
    nos tres programas e nao dependem do formato numerico.
  - Para SEW=8 o RVV 1.0 base nao tem aritmetica FP: a coluna IEEE754
    vale "como se existisse" (extensoes OFP8 propostas).

Rodar:  python3 contagem_instrucoes.py
"""

import random
import sys

import eval_spmv
import takum
import zvtakum

TAMANHO = 64
VLENS = [128, 256, 512]
LARGURAS = [8, 16, 32]


# ---------------------------------------------------------------------------
# Preparar os dados na "memoria" (listas em formato CSR)
# ---------------------------------------------------------------------------
def montar_linhas(entradas, n, sew):
    """Devolve linhas[i] = lista de (coluna, bits Takum do valor), em CSR."""
    linhas = []
    for _ in range(n):
        linhas.append([])
    for i, j, v in entradas:
        linhas[i].append((j, takum.encode(v, sew)))
    for linha in linhas:
        linha.sort()                      # CSR guarda cada linha por coluna
    return linhas


# ---------------------------------------------------------------------------
# O programa Zvtakum: roda no simulador
# ---------------------------------------------------------------------------
def spmv_zvtakum(cpu, linhas, x_bits, sew):
    """Executa y = A.x com vtdot.vv no simulador.

    Devolve (y_bits, largura de y em bits, instrucoes de memoria do modelo).
    """
    vlmax = cpu.vlen // sew
    n_acc = min(2 * sew, 32)              # o vtdot acumula em precisao ampliada
    y_bits = []
    memoria = 0

    for linha in linhas:
        acc = None
        for inicio in range(0, len(linha), vlmax):
            pedaco = linha[inicio:inicio + vlmax]

            cpu.vsetvli(len(pedaco), sew)                      # conta no simulador
            cpu.vregs[1] = [b for (c, b) in pedaco]            # vle valores
            cpu.vregs[2] = [x_bits[c] for (c, b) in pedaco]    # vle colunas + vluxei x
            memoria = memoria + 3

            cpu.executar(zvtakum.montar("vtdot.vv v3, v1, v2"))
            parcial = cpu.vregs[3][0]

            if acc is None:
                acc = parcial
            else:
                # pedaco extra: soma o parcial no acumulador (largura n_acc)
                cpu.vsetvli(1, n_acc)
                cpu.vregs[4] = [acc]
                cpu.vregs[5] = [parcial]
                cpu.executar(zvtakum.montar("vtadd.vv v4, v4, v5"))
                acc = cpu.vregs[4][0]

        if acc is None:
            acc = 0                       # linha vazia: y[i] = 0
        memoria = memoria + 1             # guardar y[i]
        y_bits.append(acc)

    return y_bits, n_acc, memoria


# ---------------------------------------------------------------------------
# Formulas (o modelo escrito em conta, para conferir com o simulador)
# ---------------------------------------------------------------------------
def pedacos_da_matriz(linhas, vlmax):
    """(total de pedacos, linhas nao vazias) para um dado VLMAX."""
    total = 0
    nao_vazias = 0
    for linha in linhas:
        if len(linha) > 0:
            nao_vazias = nao_vazias + 1
            total = total + (len(linha) + vlmax - 1) // vlmax     # teto
    return total, nao_vazias


def contagem_escalar(linhas):
    nnz = 0
    for linha in linhas:
        nnz = nnz + len(linha)
    return 5 * nnz + 2 * len(linhas)


def contagem_rvv_ieee(linhas, vlmax):
    pedacos, nao_vazias = pedacos_da_matriz(linhas, vlmax)
    # por pedaco: 6.  Por linha nao vazia: vfmv.s.f.  Por linha: guardar y.
    return 6 * pedacos + nao_vazias + len(linhas)


def contagem_zvtakum(linhas, vlmax):
    pedacos, nao_vazias = pedacos_da_matriz(linhas, vlmax)
    extras = pedacos - nao_vazias         # pedacos alem do primeiro de cada linha
    return 5 * pedacos + 2 * extras + len(linhas)


# ---------------------------------------------------------------------------
# Medir no simulador
# ---------------------------------------------------------------------------
def medir(entradas, x, n, sew, vlen):
    """Roda o SpMV no simulador. Devolve um dicionario com tudo que importa."""
    linhas = montar_linhas(entradas, n, sew)
    x_bits = [takum.encode(v, sew) for v in x]

    cpu = zvtakum.ProcessadorZvtakum(vlen=vlen)
    y_bits, n_acc, memoria = spmv_zvtakum(cpu, linhas, x_bits, sew)

    vlmax = vlen // sew
    pedacos, nao_vazias = pedacos_da_matriz(linhas, vlmax)
    return {
        "linhas": linhas,
        "vlmax": vlmax,
        "pedacos": pedacos,
        "y_bits": y_bits,
        "n_acc": n_acc,
        "no_simulador": cpu.contador_instr,
        "memoria": memoria,
        "total_medido": cpu.contador_instr + memoria,
        "total_formula": contagem_zvtakum(linhas, vlmax),
        "escalar": contagem_escalar(linhas),
        "rvv_ieee": contagem_rvv_ieee(linhas, vlmax),
    }


def gerar_dados(densidade, faixa, semente):
    random.seed(semente)
    entradas = eval_spmv.gerar_matriz_esparsa(TAMANHO, densidade, faixa)
    x = []
    for _ in range(TAMANHO):
        x.append(random.choice([-1.0, 1.0]) * 10.0 ** random.uniform(-1, 1))
    return entradas, x


# ---------------------------------------------------------------------------
# Apresentacao
# ---------------------------------------------------------------------------
def tabela(densidade, rotulo):
    entradas, x = gerar_dados(densidade, 12, 7)
    print()
    print("=" * 78)
    print("MATRIZ %s: %dx%d, densidade %.0f%%, %d nao-zeros (%.1f por linha)" % (
        rotulo, TAMANHO, TAMANHO, 100 * densidade, len(entradas),
        len(entradas) / TAMANHO))
    print("=" * 78)
    print("  %5s %4s %5s %7s | %8s %9s %9s | %9s %9s" % (
        "VLEN", "SEW", "VLMAX", "pedacos", "escalar", "RVV IEEE", "Zvtakum",
        "esc/Zv", "IEEE/Zv"))
    print("  " + "-" * 74)

    divergencias = 0
    for vlen in VLENS:
        for sew in LARGURAS:
            r = medir(entradas, x, TAMANHO, sew, vlen)
            if r["total_medido"] != r["total_formula"]:
                divergencias = divergencias + 1
            print("  %5d  T%-2d %5d %7d | %8d %9d %9d | %8.2fx %8.2fx" % (
                vlen, sew, r["vlmax"], r["pedacos"], r["escalar"], r["rvv_ieee"],
                r["total_medido"], r["escalar"] / r["total_medido"],
                r["rvv_ieee"] / r["total_medido"]))
    return divergencias


def precisao_do_programa():
    """Erro do SpMV executado no simulador (vtdot com acumulador ampliado)
    comparado com o SpMV do benchmark (cada operacao arredondada para n bits)."""
    entradas, x = gerar_dados(0.05, 12, 7)
    y_ref = eval_spmv.spmv_exato(entradas, x, TAMANHO)

    print()
    print("=" * 78)
    print("PRECISAO DO PROGRAMA EXECUTADO NO SIMULADOR (faixa ~10^12, mediana do erro)")
    print("=" * 78)
    print("  %-6s %-30s %-30s" % ("Takum", "vtdot (acumula em precisao 2n)",
                                  "benchmark (tudo em n bits)"))
    print("  " + "-" * 68)
    for sew in LARGURAS:
        r = medir(entradas, x, TAMANHO, sew, 128)
        y_dec = [takum.decode(b, r["n_acc"]) for b in r["y_bits"]]
        e_vtdot = eval_spmv.estatisticas(eval_spmv.erro_relativo(y_dec, y_ref))["mediana"]

        arredonda = eval_spmv.FORMATOS["Takum T%d" % sew]
        y_bench = eval_spmv.spmv_formato(entradas, x, TAMANHO, arredonda)
        e_bench = eval_spmv.estatisticas(eval_spmv.erro_relativo(y_bench, y_ref))["mediana"]

        print("  T%-5d %-30s %-30s" % (
            sew, "%.2e (acumulador T%d)" % (e_vtdot, r["n_acc"]),
            "%.2e" % e_bench))


def main():
    print("CONTAGEM DE INSTRUCOES - SpMV executado no simulador Zvtakum")
    print("(instrucoes de carga/gravacao: modelo; vsetvli/vtdot/vtadd: medidas)")

    divergencias = tabela(0.05, "ESPARSA")
    divergencias = divergencias + tabela(0.30, "MAIS DENSA")
    precisao_do_programa()

    print()
    print("=" * 78)
    print("LEITURA DOS RESULTADOS")
    print("=" * 78)
    print("""
  1. Contra o programa ESCALAR a reducao e grande, e cresce com VLMAX
     (VLEN maior ou SEW menor): menos pedacos por linha. Na matriz esparsa
     (3 nao-zeros por linha) quase toda linha cabe num pedaco, entao o VLMAX
     quase nao muda nada; o efeito aparece na matriz mais densa.
  2. Contra o RVV IEEE754 de MESMA largura, o Zvtakum ganha pouco: o
     vtdot.vv junta vfmul + vfredusum numa instrucao e dispensa o
     acumulador inicial. Em linhas de mais de um pedaco o ganho some,
     porque o vtdot nao recebe acumulador (custa vsetvli + vtadd por pedaco
     extra). SUGESTAO DE PROJETO: fazer o vtdot.vv somar vs1[0] ao
     resultado, como o vfredusum.vs faz.
  3. O ganho principal vem da LARGURA: o mesmo VLEN comporta 4x mais
     elementos em T8 do que em T32, e o Takum de 8/16 bits nao estoura
     onde o FP8/FP16 estouram (ver analise_erro.py).
  4. Carga e gravacao nao mudam: o Takum nao precisa de vle/vse novos.
""")

    if divergencias > 0:
        print("FALHA: o simulador e a formula divergem em %d casos" % divergencias)
        sys.exit(1)
    print("OK: contagem do simulador == formula do modelo em todos os casos")


if __name__ == "__main__":
    main()
