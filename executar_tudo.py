"""
executar_tudo.py - Roda TODOS os testes e scripts do projeto e mostra um resumo.

E o "script de teste automatico" pedido no enunciado (entregavel 1).
Cada etapa roda num processo separado; a saida completa de cada uma
fica guardada em  resultados/<nome>.txt .

Rodar:  python3 executar_tudo.py            (tudo, leva cerca de 1 minuto)
        python3 executar_tudo.py --rapido   (so os testes, sem os benchmarks)

Codigo de saida: 0 se tudo passou, 1 se alguma etapa falhou (serve para CI).
"""

import os
import subprocess
import sys
import time

PASTA = os.path.dirname(os.path.abspath(__file__))

# (descricao, arquivo, argumentos, texto que precisa aparecer na saida, e_teste)
ETAPAS = [
    ("Fase 1 - testes do takum.py",          "test_takum.py",          [], "todos os", True),
    ("Fase 2 - testes do zvtakum.py",        "test_zvtakum.py",        [], "todos os", True),
    ("Fase 3 - testes das analises",         "test_analises.py",       [], "todos os", True),
    ("Terminal - 3.14 em T16 = 0x4D27",      "takum_terminal.py",      ["3.14"], "0x4D27", True),
    ("Fase 2 - demonstracao do Zvtakum",     "demo_zvtakum.py",        [], "FIM DA DEMONSTRACAO", False),
    ("Fase 3 - benchmark SpMV",              "eval_spmv.py",           [], "OBSERVACAO PARA O ARTIGO", False),
    ("Fase 3 - distribuicao do erro",        "analise_erro.py",        [], "OK:", False),
    ("Fase 3 - contagem de instrucoes",      "contagem_instrucoes.py", [], "OK:", False),
    ("Fase 3 - CSRs e excecoes",             "analise_csr.py",         [], "OK:", False),
    ("Fase 3 - grafico de instrucoes",       "grafico_instrucoes.py",  [], "OK:", False),
]


def resumo_da_saida(saida):
    """Uma linha curta que descreve o resultado (a linha RESULTADO ou OK)."""
    ultima = ""
    for linha in saida.splitlines():
        limpa = linha.strip()
        if limpa.startswith("RESULTADO:") or limpa.startswith("OK:"):
            ultima = limpa
    if ultima == "":
        marcadas = saida.count("[OK]")
        if marcadas > 0:
            ultima = "%d verificacoes [OK]" % marcadas
    return ultima


def rodar(arquivo, argumentos):
    """Roda um script. Devolve (codigo de saida, texto de saida, segundos)."""
    inicio = time.time()
    try:
        r = subprocess.run([sys.executable, arquivo] + argumentos, cwd=PASTA,
                           capture_output=True, text=True, timeout=900)
        codigo = r.returncode
        saida = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        codigo = 1
        saida = "TEMPO ESGOTADO (mais de 15 minutos)"
    return codigo, saida, time.time() - inicio


def main():
    so_testes = "--rapido" in sys.argv

    pasta_saida = os.path.join(PASTA, "resultados")
    if not os.path.isdir(pasta_saida):
        os.makedirs(pasta_saida)

    print("=" * 78)
    print("EXECUTANDO O PROJETO TAKUM-RVV")
    print("=" * 78)

    falhas = []
    linhas = []
    for descricao, arquivo, argumentos, esperado, e_teste in ETAPAS:
        if so_testes and not e_teste:
            continue
        print("  rodando %-28s ..." % arquivo, flush=True)
        codigo, saida, segundos = rodar(arquivo, argumentos)

        nome = arquivo.replace(".py", "") + ".txt"
        with open(os.path.join(pasta_saida, nome), "w") as f:
            f.write(saida)

        passou = (codigo == 0) and (esperado in saida)
        if not passou:
            falhas.append(descricao)
        linhas.append((descricao, passou, segundos, resumo_da_saida(saida), codigo))

    print()
    print("=" * 78)
    print("RESUMO")
    print("=" * 78)
    for descricao, passou, segundos, detalhe, codigo in linhas:
        marca = "OK   "
        if not passou:
            marca = "FALHA"
        print("  %s %-40s %5.1fs  %s" % (marca, descricao, segundos, detalhe))
        if not passou:
            print("        (codigo de saida %d; veja resultados/ para a saida completa)" % codigo)

    print()
    if len(falhas) > 0:
        print("RESULTADO: %d etapa(s) falharam:" % len(falhas))
        for descricao in falhas:
            print("   - " + descricao)
        sys.exit(1)
    print("RESULTADO: todas as %d etapas passaram." % len(linhas))
    print("Saidas completas em: resultados/")


if __name__ == "__main__":
    main()
