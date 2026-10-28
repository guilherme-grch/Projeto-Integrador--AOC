"""
analise_csr.py - Complexidade de excecoes e de CSRs: IEEE754 vs Takum (Fase 3).

O enunciado pede para "analisar a reducao na complexidade ... do registro de
controle e status (CSRs)". Esta analise tem 3 partes:

  PARTE 1 - CENSO DOS PADROES DE BITS (calculado, nao declarado):
            percorre TODOS os padroes de 8 e 16 bits de cada formato e conta
            quantos sao zero, subnormal, normal, infinito e NaN/NaR.
            Cada classe diferente de "normal" e um caminho extra no decodificador.

  PARTE 2 - CSRs QUE CADA FORMATO EXIGE (fatos do RISC-V + a nossa proposta).

  PARTE 3 - EVENTOS DE EXCECAO (calculado): em que fracao das contas o IEEE754
            levantaria as flags de overflow / underflow / invalido / divisao
            por zero, e o que o Takum faz nesses mesmos casos.
            Isto e a parte "honesta": tirar as flags NAO faz o evento sumir;
            o Takum so passa a trata-lo sem avisar (satura).

Formatos IEEE754 usados aqui seguem a especificacao real:
  OFP8 E4M3: sem infinito; so o padrao S.1111.111 e NaN; maximo 448.
  OFP8 E5M2: estilo IEEE (infinito e NaN com expoente todo 1); maximo 57344.
  FP16 e bfloat16: IEEE754 comuns.
(O benchmark eval_spmv.py emula o E4M3 de forma mais simples, com maximo ~240;
 a diferenca nao muda as conclusoes.)

Rodar:  python3 analise_csr.py
"""

import bisect
import math
import random
import sys

import takum

# (bits de expoente, bits de mantissa, estilo)
FORMATOS_IEEE = {
    "OFP8 E4M3": (4, 3, "e4m3"),
    "OFP8 E5M2": (5, 2, "ieee"),
    "FP16":      (5, 10, "ieee"),
    "bfloat16":  (8, 7, "ieee"),
}


# ---------------------------------------------------------------------------
# Decodificar um padrao de bits IEEE754 de baixa precisao
# ---------------------------------------------------------------------------
def decodificar_ieee(padrao, bits_exp, bits_mant, estilo):
    """Devolve (classe, valor). classe: zero, subnormal, normal, inf ou nan."""
    n = 1 + bits_exp + bits_mant
    sinal = padrao >> (n - 1)
    expoente = (padrao >> bits_mant) & ((1 << bits_exp) - 1)
    mantissa = padrao & ((1 << bits_mant) - 1)
    vies = (1 << (bits_exp - 1)) - 1
    expoente_todo_1 = (1 << bits_exp) - 1

    s = 1.0
    if sinal == 1:
        s = -1.0

    if expoente == 0:
        if mantissa == 0:
            return "zero", s * 0.0
        return "subnormal", s * mantissa * 2.0 ** (1 - vies - bits_mant)

    if expoente == expoente_todo_1:
        if estilo == "e4m3":
            if mantissa == (1 << bits_mant) - 1:
                return "nan", math.nan
            # nos outros casos o E4M3 usa o expoente todo 1 como numero normal
        else:
            if mantissa == 0:
                return "inf", s * math.inf
            return "nan", math.nan

    valor = s * (1.0 + mantissa / (1 << bits_mant)) * 2.0 ** (expoente - vies)
    return "normal", valor


def decodificar_takum(padrao, n):
    """Devolve (classe, valor) para um padrao Takum de n bits."""
    valor = takum.decode(padrao, n)
    if math.isnan(valor):
        return "nar", valor
    if valor == 0.0:
        return "zero", valor
    return "normal", valor


def tabela_do_formato(nome):
    """Lista [(classe, valor)] de TODOS os padroes do formato (8 ou 16 bits)."""
    if nome.startswith("Takum"):
        n = int(nome.split()[1][1:])        # "Takum T8" -> 8
        return [decodificar_takum(p, n) for p in range(1 << n)]
    bits_exp, bits_mant, estilo = FORMATOS_IEEE[nome]
    n = 1 + bits_exp + bits_mant
    return [decodificar_ieee(p, bits_exp, bits_mant, estilo) for p in range(1 << n)]


# ---------------------------------------------------------------------------
# PARTE 1 - censo
# ---------------------------------------------------------------------------
def censo(tabela):
    """Conta quantos padroes ha em cada classe."""
    contagem = {"zero": 0, "subnormal": 0, "normal": 0, "inf": 0, "nan": 0, "nar": 0}
    for classe, valor in tabela:
        contagem[classe] = contagem[classe] + 1
    return contagem


def valores_distintos(c):
    """Quantos valores finitos diferentes o formato representa.
    (-0 e +0 sao o mesmo valor, entao o zero duplicado nao conta.)"""
    total = c["zero"] + c["subnormal"] + c["normal"] + c["inf"] + c["nan"] + c["nar"]
    duplicado = max(c["zero"] - 1, 0)
    return total - c["inf"] - c["nan"] - c["nar"] - duplicado


def classes_especiais(c):
    """Quantas classes alem de 'normal' o decodificador precisa tratar."""
    quantas = 0
    for classe in ("zero", "subnormal", "inf", "nan", "nar"):
        if c[classe] > 0:
            quantas = quantas + 1
    return quantas


def parte1():
    print("=" * 78)
    print("PARTE 1 - CENSO DE TODOS OS PADROES DE BITS")
    print("=" * 78)
    resultados = {}
    for nome in ["OFP8 E4M3", "OFP8 E5M2", "Takum T8",
                 "FP16", "bfloat16", "Takum T16"]:
        resultados[nome] = censo(tabela_do_formato(nome))

    print("  %-10s %6s %5s %9s %7s %5s %8s | %9s %9s %8s" % (
        "formato", "bits", "zero", "subnormal", "normal", "inf", "NaN/NaR",
        "distintos", "% perdido", "classes"))
    print("  " + "-" * 92)
    for nome, c in resultados.items():
        total = c["zero"] + c["subnormal"] + c["normal"] + c["inf"] + c["nan"] + c["nar"]
        distintos = valores_distintos(c)
        bits = int(math.log2(total))
        print("  %-10s %6d %5d %9d %7d %5d %8d | %9d %8.2f%% %8d" % (
            nome, bits, c["zero"], c["subnormal"], c["normal"], c["inf"],
            c["nan"] + c["nar"], distintos, 100.0 * (total - distintos) / total,
            classes_especiais(c)))
    print()
    print("  distintos  = valores finitos diferentes que o formato consegue guardar")
    print("  % perdido  = padroes que NAO guardam um valor finito novo (NaN, infinito, zero repetido)")
    print("  classes    = classes especiais que o decodificador precisa tratar")
    print("               (zero, subnormal, infinito, NaN/NaR)")
    return resultados


# ---------------------------------------------------------------------------
# PARTE 2 - CSRs
# ---------------------------------------------------------------------------
def parte2():
    print()
    print("=" * 78)
    print("PARTE 2 - ESTADO DE CONTROLE (CSRs) QUE CADA FORMATO EXIGE")
    print("=" * 78)
    print("""
  RISC-V com ponto flutuante IEEE754 (extensoes F/D/Zfh):
    fcsr = frm (3 bits)    modo de arredondamento: RNE, RTZ, RDN, RUP, RMM
         + fflags (5 bits) flags acumuladas: NX, UF, OF, DZ, NV
    => 8 bits de estado, lidos/escritos por csrr/csrw (frm, fflags, fcsr)
       e que toda instrucao FP precisa respeitar ou atualizar.

  Proposta Zvtakum (decisao NOSSA de projeto, nao imposicao do formato):
    frm      nao usado: o simulador implementa um unico arredondamento
             (para o mais proximo; empate para cima).
    OF, UF   nao existem: o resultado satura no maior valor e um numero
             diferente de zero nunca vira zero (ver PARTE 3 para o custo disso).
    NV, DZ   viram NaR no proprio dado, que se propaga sozinho pelas contas;
             nao precisa de flag.
    NX       opcional (nao implementado).
    vtype    reaproveitado: SEW = 8/16/32 (codigos 000/001/010) escolhe T8/T16/T32.
    => 0 bits de CSR novos e nenhum bit de fcsr tocado.
""")


# ---------------------------------------------------------------------------
# PARTE 3 - eventos de excecao
# ---------------------------------------------------------------------------
def operar(op, a, b):
    """Conta exata em float64. Divisao por zero devolve NaN (0/0) ou infinito."""
    if op == "add":
        return a + b
    if op == "mul":
        return a * b
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def preparar_ieee(tabela):
    """Valores que decidem as flags: maior valor, limite de overflow,
    menor normal e o conjunto de valores representaveis."""
    finitos = []
    menor_normal = math.inf
    for classe, valor in tabela:
        if classe in ("zero", "subnormal", "normal"):
            finitos.append(valor)
        if classe == "normal" and abs(valor) < menor_normal:
            menor_normal = abs(valor)
    positivos = sorted(set([v for v in finitos if v > 0]))
    maximo = positivos[-1]
    passo_topo = maximo - positivos[-2]
    return {
        "maximo": maximo,
        # a partir do ponto medio entre o maior valor e o "proximo" o
        # arredondamento para o mais proximo da infinito
        "limite_overflow": maximo + passo_topo / 2.0,
        "menor_normal": menor_normal,
        "conjunto": set(finitos),
    }


def eventos_ieee(par_a, par_b, op, info):
    """Flags IEEE que a conta levantaria. Devolve None se algum operando e NaN
    (NaN so propaga, nao levanta flag nesta analise)."""
    ca, va = par_a
    cb, vb = par_b
    if ca == "nan" or cb == "nan":
        return None

    r = operar(op, va, vb)
    achados = []
    if op == "div" and vb == 0.0 and va != 0.0 and ca != "inf":
        achados.append("DZ")
    elif math.isnan(r):
        achados.append("NV")
    elif math.isinf(r):
        if ca != "inf" and cb != "inf":
            achados.append("OF")
    elif r != 0.0:
        if abs(r) >= info["limite_overflow"]:
            achados.append("OF")
        elif abs(r) < info["menor_normal"] and r not in info["conjunto"]:
            achados.append("UF")      # minusculo E inexato
    return achados


def preparar_takum(n):
    """Limites em ell (log na base raiz de e) alem dos quais o Takum satura."""
    maior = takum.decode((1 << (n - 1)) - 1, n)
    anterior = takum.decode((1 << (n - 1)) - 2, n)
    menor = takum.decode(1, n)
    seguinte = takum.decode(2, n)
    ell_maior = 2.0 * math.log(maior)
    ell_menor = 2.0 * math.log(menor)
    passo_topo = ell_maior - 2.0 * math.log(anterior)
    passo_base = 2.0 * math.log(seguinte) - ell_menor
    return {
        "limite_sat": ell_maior + passo_topo / 2.0,
        "limite_clamp": ell_menor - passo_base / 2.0,
    }


def eventos_takum(par_a, par_b, op, info):
    """O que acontece no Takum. Devolve None se algum operando e NaR."""
    ca, va = par_a
    cb, vb = par_b
    if ca == "nar" or cb == "nar":
        return None

    if op == "div" and vb == 0.0:
        return ["NaR"]                # 0/0 e x/0 viram NaR
    r = operar(op, va, vb)
    if r == 0.0:
        return []                     # cancelamento exato: sem evento
    ell = 2.0 * math.log(abs(r))
    if ell >= info["limite_sat"]:
        return ["SAT"]                # saturou no maior valor, sem aviso
    if ell <= info["limite_clamp"]:
        return ["CLAMP"]              # subiu para o menor positivo, sem aviso
    return []


def contar_eventos(tabela, info, funcao_eventos, pares):
    """Para cada operacao, conta quantos pares geram cada evento."""
    resultado = {}
    for op in ("add", "mul", "div"):
        contagem = {}
        validos = 0
        for i, j in pares:
            achados = funcao_eventos(tabela[i], tabela[j], op, info)
            if achados is None:
                continue
            validos = validos + 1
            for e in achados:
                contagem[e] = contagem.get(e, 0) + 1
        resultado[op] = (validos, contagem)
    return resultado


def pares_exaustivos(n):
    pares = []
    for i in range(1 << n):
        for j in range(1 << n):
            pares.append((i, j))
    return pares


def pares_sorteados(n, quantidade):
    random.seed(11)
    pares = []
    for _ in range(quantidade):
        pares.append((random.getrandbits(n), random.getrandbits(n)))
    return pares


def imprimir_eventos(titulo, linhas_ieee, linhas_takum):
    print()
    print("  " + titulo)
    print("  %-10s %-4s | %9s %9s %9s %9s" % ("formato", "op", "OF/SAT", "UF/CLAMP", "NV/NaR", "DZ"))
    print("  " + "-" * 62)
    for nome, resultado in linhas_ieee + linhas_takum:
        for op in ("add", "mul", "div"):
            validos, c = resultado[op]
            if nome.startswith("Takum"):
                colunas = [c.get("SAT", 0), c.get("CLAMP", 0), c.get("NaR", 0), None]
            else:
                colunas = [c.get("OF", 0), c.get("UF", 0), c.get("NV", 0), c.get("DZ", 0)]
            texto = ""
            for k in colunas:
                if k is None:
                    texto = texto + " %9s" % "-"
                else:
                    texto = texto + " %8.2f%%" % (100.0 * k / validos)
            print("  %-10s %-4s |%s" % (nome, op, texto))


def parte3():
    print()
    print("=" * 78)
    print("PARTE 3 - EM QUE FRACAO DAS CONTAS CADA FORMATO TERIA UM EVENTO DE EXCECAO")
    print("=" * 78)
    print("""
  Pares de operandos: TODOS os padroes de 8 bits (65536 pares) e 20000 pares
  sorteados de 16 bits. Pares com NaN/NaR de entrada nao contam.
  IEEE754: OF/UF/NV/DZ sao as flags do fflags.   Takum (mesma conta):
    SAT   = resultado maior que o maior valor: satura, SEM aviso
    CLAMP = resultado menor que o menor positivo: sobe para ele, SEM aviso
    NaR   = 0/0 ou x/0: vira NaR (cobre NV e DZ), que se propaga no dado
""")

    pares8 = pares_exaustivos(8)
    linhas_ieee = []
    for nome in ("OFP8 E4M3", "OFP8 E5M2"):
        tabela = tabela_do_formato(nome)
        linhas_ieee.append((nome, contar_eventos(
            tabela, preparar_ieee(tabela), eventos_ieee, pares8)))
    tabela = tabela_do_formato("Takum T8")
    linhas_takum = [("Takum T8", contar_eventos(
        tabela, preparar_takum(8), eventos_takum, pares8))]
    imprimir_eventos("8 bits (exaustivo)", linhas_ieee, linhas_takum)

    pares16 = pares_sorteados(16, 20000)
    tabela = tabela_do_formato("FP16")
    linhas_ieee = [("FP16", contar_eventos(
        tabela, preparar_ieee(tabela), eventos_ieee, pares16))]
    tabela = tabela_do_formato("Takum T16")
    linhas_takum = [("Takum T16", contar_eventos(
        tabela, preparar_takum(16), eventos_takum, pares16))]
    imprimir_eventos("16 bits (20000 pares sorteados)", linhas_ieee, linhas_takum)

    print("""
  LEITURA: o Takum satura/clampa bem menos que o IEEE estoura/subflui, porque
  cobre uma faixa muito maior. Mas onde isso acontece NAO ha flag: o programa
  nao fica sabendo. Dispensar o fflags simplifica o hardware, e o custo e
  perder o aviso (em T8 esses eventos silenciosos nao sao despreziveis).

  CUIDADO: os operandos foram sorteados uniformemente entre os PADROES de
  bits, o que espalha os valores por toda a faixa de cada formato. Nao e uma
  carga de trabalho real: use as porcentagens para comparar os formatos entre
  si, nao como taxa de evento de um programa de verdade.
""")


def main():
    resultados = parte1()
    parte2()
    parte3()

    # conferencia interna: cada censo tem que somar o total de padroes
    for nome, c in resultados.items():
        total = c["zero"] + c["subnormal"] + c["normal"] + c["inf"] + c["nan"] + c["nar"]
        bits = round(math.log2(total))
        if total != 1 << bits:
            print("FALHA: censo de %s nao soma uma potencia de 2" % nome)
            sys.exit(1)
    print("OK: censos consistentes")


if __name__ == "__main__":
    main()
