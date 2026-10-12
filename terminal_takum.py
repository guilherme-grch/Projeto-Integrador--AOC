"""
takum_terminal.py - Testa o Takum digitando no terminal.

Como rodar (modo interativo):
    python3 takum_terminal.py

Uso rapido, sem entrar no modo interativo:
    python3 takum_terminal.py 3.14
    python3 takum_terminal.py -n 8 3.14 0b01001101
    python3 takum_terminal.py 2.5 '*' 3

(takum.py precisa estar na mesma pasta)
"""

import ast
import math
import sys

import takum

OPERADORES = ["+", "-", "*", "/"]

AJUDA = """
COMO USAR  (largura atual: T{n})

  Digite um numero DECIMAL e eu mostro o Takum:
      3.14      -0.5      1e-30      1/3      pi      (virgula tambem vale: 3,14)

  Digite um numero em TAKUM (com 0b ou 0x na frente) e eu mostro o decimal:
      0b0100110100100111        0x4D27

  Faca uma conta em Takum (separe com espacos):
      2.5 * 3        0x4D27 + 1.5        10 / 4

COMANDOS
  n 8  (ou t8, t16, t32)   troca a largura do Takum (de 8 a 32 bits)
  faixa                    maior e menor valor da largura atual
  tabela                   (so para T8) lista os 256 padroes
  ajuda                    mostra esta mensagem
  sair                     fecha o programa
"""


# ---------------------------------------------------------------------------
# Ler numeros
# ---------------------------------------------------------------------------
def avaliar(no, constantes):
    """Calcula um no da arvore da expressao (so numeros e contas simples)."""
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return float(no.value)

    if isinstance(no, ast.Name) and no.id.lower() in constantes:
        return constantes[no.id.lower()]

    if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.UAdd, ast.USub)):
        valor = avaliar(no.operand, constantes)
        if isinstance(no.op, ast.USub):
            return -valor
        return valor

    if isinstance(no, ast.BinOp):
        a = avaliar(no.left, constantes)
        b = avaliar(no.right, constantes)
        if isinstance(no.op, ast.Add):
            return a + b
        if isinstance(no.op, ast.Sub):
            return a - b
        if isinstance(no.op, ast.Mult):
            return a * b
        if isinstance(no.op, ast.Div):
            if b == 0:
                raise ValueError("divisao por zero")
            return a / b
        if isinstance(no.op, ast.Pow):
            resultado = a ** b
            if isinstance(resultado, complex):
                raise ValueError("resultado complexo")
            return resultado

    raise ValueError("expressao nao entendida")


def ler_decimal(texto):
    """Transforma '3.14', '3,14', '1e-30', '1/3', 'pi' em float."""
    texto = texto.replace(",", ".")
    constantes = {"pi": math.pi, "e": math.e, "inf": math.inf, "nan": math.nan}
    try:
        arvore = ast.parse(texto, mode="eval")
        return avaliar(arvore.body, constantes)
    except (SyntaxError, OverflowError, ZeroDivisionError, ValueError) as erro:
        raise ValueError("nao entendi '%s' como numero (%s)" % (texto, erro))


def e_takum(token):
    """True se o token comeca com 0b (binario) ou 0x (hexadecimal)."""
    t = token.lower()
    return t.startswith("0b") or t.startswith("0x")


def ler_takum(token, n):
    """Transforma '0b0100...' ou '0x4D27' no inteiro do padrao de n bits."""
    t = token.lower().replace("_", "")
    try:
        if t.startswith("0b"):
            valor = int(t[2:], 2)
        else:
            valor = int(t[2:], 16)
    except ValueError:
        raise ValueError("'%s' nao e um binario/hexadecimal valido" % token)
    if valor >= (1 << n):
        raise ValueError("'%s' tem mais de %d bits (largura atual: T%d)" % (token, n, n))
    return valor


# ---------------------------------------------------------------------------
# Escrever numeros
# ---------------------------------------------------------------------------
def bits_com_espacos(b, n):
    """Escreve os n bits em grupos de 4: 0100 1101 0010 0111"""
    texto = format(b, "0%db" % n)
    sobra = (-n) % 4                      # zeros extras so para alinhar os grupos
    texto = "0" * sobra + texto
    grupos = []
    for i in range(0, len(texto), 4):
        grupos.append(texto[i:i + 4])
    grupos[0] = grupos[0][sobra:]
    return " ".join(grupos)


def em_hexa(b, n):
    return "0x" + format(b, "0%dX" % ((n + 3) // 4))


def fmt(x):
    """Escreve um float com ate 15 algarismos significativos."""
    if math.isnan(x):
        return "NaN"
    return "%.15g" % x


def mostrar_takum(b, n):
    """Linhas que descrevem um padrao Takum (bits, campos, valor)."""
    info = takum.inspect(b, n)
    linhas = []
    linhas.append("  Takum T%d (bits)  : %s" % (n, bits_com_espacos(b, n)))
    linhas.append("  Takum T%d (hexa)  : %s" % (n, em_hexa(b, n)))

    if "especial" in info:
        if info["especial"] == "zero":
            linhas.append("  Significado       : zero")
        else:
            linhas.append("  Significado       : NaR (Not a Real, o 'NaN' do Takum)")
        return linhas

    linhas.append("  Campos S|D|R|C|M  : " + info["campos"])
    linhas.append("  Detalhe           : S=%d  D=%d  R=%d  r=%d  c=%d  p=%d  m=%s  ell=%s" % (
        info["S"], info["D"], info["R"], info["r (tamanho de C)"],
        info["c (parte inteira)"], info["p (tamanho de M)"],
        info["m (parte fracionaria)"], info["ell"]))
    linhas.append("  Valor em decimal  : " + fmt(info["valor"]))
    return linhas


# ---------------------------------------------------------------------------
# As tres funcoes principais: decimal -> takum, takum -> decimal, conta
# ---------------------------------------------------------------------------
def mostrar_decimal(x, n):
    """Decimal digitado -> Takum mais proximo."""
    b = takum.encode(x, n)
    v = takum.decode(b, n)
    maior = takum.decode((1 << (n - 1)) - 1, n)
    menor = takum.decode(1, n)

    linhas = []
    linhas.append("  Decimal digitado  : " + fmt(x))
    linhas = linhas + mostrar_takum(b, n)

    if math.isnan(x):
        linhas.append("  Aviso             : NaN vira NaR no Takum")
        return linhas
    if math.isinf(x):
        linhas.append("  Aviso             : Takum nao tem infinito, o valor satura no maior numero")
    elif abs(x) > maior:
        linhas.append("  Aviso             : maior que o maior valor de T%d (%s): satura" % (n, fmt(maior)))
    elif x != 0 and abs(x) < menor:
        linhas.append("  Aviso             : menor que o menor positivo de T%d (%s): Takum nao vira zero, usa o menor valor" % (n, fmt(menor)))

    if x != 0 and math.isfinite(x) and abs(x) <= maior and abs(x) >= menor:
        erro = abs(v - x) / abs(x)
        linhas.append("  Erro relativo     : %.3e  (%.4f%%)" % (erro, erro * 100))

    # vizinhos: o padrao anterior e o seguinte (nunca atravessa o NaR)
    nar = takum.nar_pattern(n)
    mascara = (1 << n) - 1
    anterior = (b - 1) & mascara
    seguinte = (b + 1) & mascara
    texto_vizinhos = ""
    if anterior != nar and b != nar:
        texto_vizinhos = "anterior = " + fmt(takum.decode(anterior, n))
    if seguinte != nar and b != nar:
        if texto_vizinhos != "":
            texto_vizinhos = texto_vizinhos + "   "
        texto_vizinhos = texto_vizinhos + "seguinte = " + fmt(takum.decode(seguinte, n))
    if texto_vizinhos != "":
        linhas.append("  Vizinhos          : " + texto_vizinhos)
    return linhas


def mostrar_bits(b, n):
    """Takum digitado -> decimal."""
    return mostrar_takum(b, n)


def pegar_operando(token, n):
    """Devolve (bits do Takum, valor decimal digitado, descricao)."""
    if e_takum(token):
        b = ler_takum(token, n)
        valor = takum.decode(b, n)
        return b, valor
    x = ler_decimal(token)
    return takum.encode(x, n), x


def mostrar_conta(token_a, operador, token_b, n):
    """Faz a conta A operador B em aritmetica Takum."""
    bits_a, digitado_a = pegar_operando(token_a, n)
    bits_b, digitado_b = pegar_operando(token_b, n)

    if operador == "+":
        bits_r = takum.add(bits_a, bits_b, n)
    elif operador == "-":
        bits_r = takum.sub(bits_a, bits_b, n)
    elif operador == "*":
        bits_r = takum.mul(bits_a, bits_b, n)
    else:
        bits_r = takum.div(bits_a, bits_b, n)

    va = takum.decode(bits_a, n)
    vb = takum.decode(bits_b, n)
    vr = takum.decode(bits_r, n)

    # resultado "de verdade" com os numeros que a pessoa digitou
    if math.isnan(digitado_a) or math.isnan(digitado_b):
        exato = math.nan
    elif operador == "+":
        exato = digitado_a + digitado_b
    elif operador == "-":
        exato = digitado_a - digitado_b
    elif operador == "*":
        exato = digitado_a * digitado_b
    elif digitado_b == 0:
        exato = math.nan
    else:
        exato = digitado_a / digitado_b

    linhas = []
    linhas.append("  A = %s  ->  %s  (%s)  vale %s" % (
        token_a, bits_com_espacos(bits_a, n), em_hexa(bits_a, n), fmt(va)))
    linhas.append("  B = %s  ->  %s  (%s)  vale %s" % (
        token_b, bits_com_espacos(bits_b, n), em_hexa(bits_b, n), fmt(vb)))
    linhas.append("  Conta             : A %s B em Takum T%d" % (operador, n))
    linhas = linhas + mostrar_takum(bits_r, n)
    linhas.append("  Resultado exato   : " + fmt(exato) + "  (com os numeros que voce digitou)")
    if math.isfinite(exato) and exato != 0 and math.isfinite(vr):
        erro = abs(vr - exato) / abs(exato)
        linhas.append("  Erro relativo     : %.3e  (%.4f%%)" % (erro, erro * 100))
    return linhas


# ---------------------------------------------------------------------------
# Comandos extras
# ---------------------------------------------------------------------------
def comando_faixa(n):
    maior = takum.decode((1 << (n - 1)) - 1, n)
    menor = takum.decode(1, n)
    linhas = []
    linhas.append("  Largura           : T%d" % n)
    linhas.append("  Maior valor       : %s   (%s)" % (fmt(maior), bits_com_espacos((1 << (n - 1)) - 1, n)))
    linhas.append("  Menor positivo    : %s   (%s)" % (fmt(menor), bits_com_espacos(1, n)))
    linhas.append("  Faixa dinamica    : %.1f ordens de grandeza" % math.log10(maior / menor))
    linhas.append("  Zero              : %s" % bits_com_espacos(0, n))
    linhas.append("  NaR               : %s" % bits_com_espacos(takum.nar_pattern(n), n))
    return linhas


def comando_tabela(n):
    if n != 8:
        return ["  'tabela' so funciona em T8 (digite: n 8). Em T%d teria %d linhas." % (n, 1 << n)]
    linhas = ["  padrao (bits)  hexa   valor"]
    for b in range(256):
        linhas.append("  %s   0x%02X   %s" % (bits_com_espacos(b, 8), b, fmt(takum.decode(b, 8))))
    return linhas


# ---------------------------------------------------------------------------
# Entender uma linha digitada
# ---------------------------------------------------------------------------
def processar_linha(linha, estado):
    """Recebe o que a pessoa digitou e devolve (texto, continuar)."""
    linha = linha.strip()
    n = estado["n"]
    if linha == "":
        return "", True

    minuscula = linha.lower()
    if minuscula in ("sair", "q", "quit", "exit"):
        return "Ate mais!", False
    if minuscula in ("ajuda", "help", "?", "h"):
        return AJUDA.format(n=n), True
    if minuscula == "faixa":
        return "\n".join(comando_faixa(n)), True
    if minuscula == "tabela":
        return "\n".join(comando_tabela(n)), True

    # troca de largura: "n 8", "t8", "t16", "t32"
    nova = None
    partes = minuscula.split()
    if len(partes) == 2 and partes[0] == "n" and partes[1].isdigit():
        nova = int(partes[1])
    elif minuscula in ("t8", "t16", "t32"):
        nova = int(minuscula[1:])
    if nova is not None:
        if nova < 8 or nova > 32:
            return "  Largura precisa estar entre 8 e 32 bits.", True
        estado["n"] = nova
        return "  Agora usando Takum T%d." % nova, True

    # numero ou conta
    try:
        pedacos = linha.split()

        # permite binario escrito em grupos: 0b0100 1101 0010 0111
        if e_takum(pedacos[0]) and len(pedacos) > 1:
            so_binario = True
            for p in pedacos[1:]:
                if p.replace("1", "").replace("0", "") != "":
                    so_binario = False
            if pedacos[0].lower().startswith("0b") and so_binario:
                pedacos = ["".join(pedacos)]

        if len(pedacos) == 1:
            if e_takum(pedacos[0]):
                return "\n".join(mostrar_bits(ler_takum(pedacos[0], n), n)), True
            return "\n".join(mostrar_decimal(ler_decimal(pedacos[0]), n)), True

        if len(pedacos) == 3 and pedacos[1] in OPERADORES:
            return "\n".join(mostrar_conta(pedacos[0], pedacos[1], pedacos[2], n)), True

        return "  Nao entendi. Para uma conta use espacos: 2.5 * 3   (digite 'ajuda').", True
    except ValueError as erro:
        return "  Erro: %s   (digite 'ajuda')" % erro, True


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    estado = {"n": 16}
    argumentos = sys.argv[1:]

    # opcao -n 8 no comeco
    if len(argumentos) >= 2 and argumentos[0] == "-n" and argumentos[1].isdigit():
        estado["n"] = int(argumentos[1])
        argumentos = argumentos[2:]

    # modo rapido: processa o que veio na linha de comando e sai
    if len(argumentos) > 0:
        if len(argumentos) == 3 and argumentos[1] in OPERADORES:
            linhas = [" ".join(argumentos)]
        else:
            linhas = argumentos
        for linha in linhas:
            texto, _ = processar_linha(linha, estado)
            print(texto)
        return

    # modo interativo
    print("=" * 62)
    print(" Teste do Takum pelo terminal")
    print(" Digite 'ajuda' para ver como usar, 'sair' para fechar.")
    print("=" * 62)
    continuar = True
    while continuar:
        try:
            linha = input("takum T%d> " % estado["n"])
        except (EOFError, KeyboardInterrupt):
            print()
            break
        texto, continuar = processar_linha(linha, estado)
        if texto != "":
            print(texto)


if __name__ == "__main__":
    main()
