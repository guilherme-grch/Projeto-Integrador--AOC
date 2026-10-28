"""
test_zvtakum.py - Testes da extensao Zvtakum (Fase 2).

Como rodar:   python3 test_zvtakum.py
(takum.py e zvtakum.py precisam estar na mesma pasta)
"""

import math
import takum
import zvtakum
from zvtakum import ProcessadorZvtakum, montar, desmontar, encode_instr, decode_instr

total = 0
falhas = []


def aprox(a, b, tolerancia):
    if a == b:
        return True
    if b == 0:
        return abs(a) < tolerancia
    return abs((a - b) / b) < tolerancia


def check(nome, condicao, extra=""):
    global total
    total = total + 1
    if condicao:
        print("  OK   " + nome)
    else:
        print("  FALHA " + nome + "  " + extra)
        falhas.append(nome)


def da_erro(funcao, *argumentos):
    """True se chamar funcao(*argumentos) levanta ValueError."""
    try:
        funcao(*argumentos)
    except ValueError:
        return True
    return False


def titulo(texto):
    print()
    print("=" * 62)
    print(texto)
    print("=" * 62)


# ---------------------------------------------------------------------------
titulo("1. PALAVRAS DE 32 BITS (valores documentados no HANDOFF)")
esperados = [
    ("vtadd.vv v3, v1, v2",  0x0220C1DB),
    ("vtsub.vv v4, v1, v2",  0x0A20C25B),
    ("vtmul.vv v5, v1, v2",  0x9220C2DB),
    ("vtdot.vv v6, v1, v2",  0xE220C35B),
    ("vncvt.t.t v7, v1",     0x4A00C3DB),
]
for texto, palavra_esperada in esperados:
    obtida = montar(texto)
    check("%-22s -> 0x%08X" % (texto, obtida), obtida == palavra_esperada,
          "esperado 0x%08X" % palavra_esperada)

# ---------------------------------------------------------------------------
titulo("2. CAMPOS DA INSTRUCAO (opcode, funct3, funct6)")
for nome in zvtakum.FUNCT6:
    p = encode_instr(nome, 1, 2, 3)
    opcode = p & 0b1111111
    funct3 = (p >> 12) & 0b111
    funct6 = (p >> 26) & 0b111111
    check("%-10s opcode=0x5B funct3=100 funct6=%s" % (nome, format(funct6, "06b")),
          opcode == 0x5B and funct3 == 0b100 and funct6 == zvtakum.FUNCT6[nome])
check("opcode Zvtakum (0x5B) diferente do OP-V do RVV oficial (0x57)",
      zvtakum.OPCODE_ZVTAKUM != 0x57)
check("todos os funct6 sao diferentes entre si",
      len(set(zvtakum.FUNCT6.values())) == len(zvtakum.FUNCT6))

# ---------------------------------------------------------------------------
titulo("3. IDA E VOLTA: montar -> decodificar (TODOS os registradores)")
erros_ida_volta = 0
combinacoes = 0
for nome in zvtakum.FUNCT6:
    for vd in range(32):
        for vs1 in range(32):
            for vs2 in range(32):
                combinacoes = combinacoes + 1
                d = decode_instr(encode_instr(nome, vd, vs1, vs2))
                if not (d["nome"] == nome and d["vd"] == vd and
                        d["vs1"] == vs1 and d["vs2"] == vs2):
                    erros_ida_volta = erros_ida_volta + 1
check("%d combinacoes (5 instrucoes x 32x32x32 registradores) sem erro" % combinacoes,
      erros_ida_volta == 0, "%d erros" % erros_ida_volta)

for texto in ["vtadd.vv v3, v1, v2", "vtsub.vv v31, v0, v15",
              "vtmul.vv v9, v9, v9", "vtdot.vv v6, v1, v2"]:
    check("montar/desmontar: " + texto, desmontar(montar(texto)) == texto)
check("montar/desmontar: vncvt.t.t v7, v1", desmontar(montar("vncvt.t.t v7, v1")) == "vncvt.t.t v7, v1")

# ---------------------------------------------------------------------------
titulo("4. ERROS QUE DEVEM SER DETECTADOS")
check("instrucao desconhecida da erro", da_erro(montar, "vxyz.vv v1, v2, v3"))
check("registrador v32 (fora de v0..v31) da erro", da_erro(encode_instr, "vtadd.vv", 32, 1, 2))
check("registrador negativo da erro", da_erro(encode_instr, "vtadd.vv", 1, -1, 2))
check("linha vazia da erro", da_erro(montar, "   "))
check("comentario sozinho da erro", da_erro(montar, "# so um comentario"))
# uma instrucao do RVV oficial (opcode 0x57) nao pode ser aceita como Zvtakum
check("palavra com opcode do RVV oficial (0x57) e rejeitada",
      da_erro(decode_instr, 0x0220C1D7))
# funct6 que nao existe na tabela
palavra_ruim = (0b111111 << 26) | (0b100 << 12) | 0x5B
check("funct6 desconhecido e rejeitado", da_erro(decode_instr, palavra_ruim))
check("comentario no fim da linha e ignorado",
      montar("vtadd.vv v3, v1, v2   # soma") == montar("vtadd.vv v3, v1, v2"))

# ---------------------------------------------------------------------------
titulo("5. VSETVLI (configuracao de SEW e VL)")
cpu = ProcessadorZvtakum(vlen=128)
check("VLEN=128, SEW=32 -> VLMAX=4", cpu.vsetvli(4, 32) == 4)
check("pediu 10 elementos T32: limitado a 4", cpu.vsetvli(10, 32) == 4)
check("VLEN=128, SEW=16 -> VLMAX=8 (pediu 10)", cpu.vsetvli(10, 16) == 8)
check("VLEN=128, SEW=8  -> VLMAX=16 (pediu 100)", cpu.vsetvli(100, 8) == 16)
check("pediu 3 elementos: VL=3", cpu.vsetvli(3, 32) == 3)
check("SEW invalido (64) da erro", da_erro(cpu.vsetvli, 4, 64))
check("SEW invalido (7) da erro", da_erro(cpu.vsetvli, 4, 7))
cpu256 = ProcessadorZvtakum(vlen=256)
check("VLEN=256, SEW=32 -> VLMAX=8", cpu256.vsetvli(100, 32) == 8)

# ---------------------------------------------------------------------------
titulo("6. SOMA, SUBTRACAO E MULTIPLICACAO EM T8, T16 E T32")
# O resultado do processador tem que ser IGUAL ao de takum.add/sub/mul
# (mesmo padrao de bits), e proximo do valor real dentro da precisao do formato.
valores_a = [1.5, 2.0, 3.5, 4.0]
valores_b = [2.0, 0.5, 2.0, 3.0]
# T8 com M de 0 bits erra ate ~28% por operando; somando dois operandos
# e o resultado o erro pode chegar perto de 40% da escala.
tolerancia = {8: 0.40, 16: 2e-3, 32: 1e-6}   # precisao de cada largura

operacoes = [
    ("vtadd.vv", takum.add, lambda x, y: x + y),
    ("vtsub.vv", takum.sub, lambda x, y: x - y),
    ("vtmul.vv", takum.mul, lambda x, y: x * y),
]
for sew in (8, 16, 32):
    for nome, funcao_takum, funcao_real in operacoes:
        cpu = ProcessadorZvtakum(vlen=128)
        cpu.vsetvli(4, sew)
        cpu.carregar(1, valores_a)
        cpu.carregar(2, valores_b)
        cpu.executar(montar(nome + " v3, v1, v2"))

        # (a) bits identicos aos de takum.py?
        bits_esperados = [funcao_takum(x, y, sew)
                          for x, y in zip(cpu.vregs[1], cpu.vregs[2])]
        check("T%-2d %s: bits iguais aos de takum.py" % (sew, nome),
              cpu.vregs[3] == bits_esperados)

        # (b) valor proximo do real?
        # Erro medido em relacao a MAIOR grandeza envolvida (x, y ou o
        # resultado). Numa subtracao de numeros parecidos o resultado e
        # pequeno, entao o erro dos operandos pesa muito no erro relativo
        # do resultado; por isso usamos a escala dos operandos.
        obtido = cpu.ler(3)
        bom = True
        for x, y, o in zip(valores_a, valores_b, obtido):
            real = funcao_real(x, y)
            escala = max(abs(x), abs(y), abs(real))
            if abs(o - real) / escala > tolerancia[sew]:
                bom = False
        check("T%-2d %s: valores proximos do real %s" % (
            sew, nome, [round(v, 4) for v in obtido]), bom)

# ---------------------------------------------------------------------------
titulo("7. VL MENOR QUE O REGISTRADOR (so processa VL elementos)")
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(2, 32)            # so 2 dos 4 elementos
cpu.carregar(1, [1.0, 2.0, 3.0, 4.0])
cpu.carregar(2, [10.0, 20.0, 30.0, 40.0])
cpu.executar(montar("vtadd.vv v3, v1, v2"))
check("VL=2: resultado tem 2 elementos", len(cpu.vregs[3]) == 2)
r = cpu.ler(3)
check("VL=2: [11, 22] -> %s" % [round(v, 4) for v in r],
      aprox(r[0], 11.0, 1e-6) and aprox(r[1], 22.0, 1e-6))

# ---------------------------------------------------------------------------
titulo("8. PRODUTO ESCALAR (vtdot.vv)")
# T32: resultado esperado 1.5*2 + 2*0.5 + 3.5*2 + 4*3 = 23
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 32)
cpu.carregar(1, valores_a)
cpu.carregar(2, valores_b)
cpu.executar(montar("vtdot.vv v6, v1, v2"))
r = cpu.ler(6)
check("T32 vtdot: resultado tem 1 elemento (escalar)", len(r) == 1)
check("T32 vtdot: %.6f (esperado 23)" % r[0], aprox(r[0], 23.0, 1e-6))

# T16: acumulador e T32 (precisao ampliada) -> ler o resultado com sew=32
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 16)
cpu.carregar(1, valores_a)
cpu.carregar(2, valores_b)
cpu.executar(montar("vtdot.vv v6, v1, v2"))
r = cpu.ler(6, sew=32)
check("T16 vtdot (acumula em T32): %.6f (esperado 23)" % r[0], aprox(r[0], 23.0, 2e-3))

# T8: acumulador e T16
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 8)
cpu.carregar(1, valores_a)
cpu.carregar(2, valores_b)
cpu.executar(montar("vtdot.vv v6, v1, v2"))
r = cpu.ler(6, sew=16)
check("T8 vtdot (acumula em T16): %.4f (esperado ~23)" % r[0], aprox(r[0], 23.0, 0.3))

# dot product com VL=1 e vetores de zeros
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 32)
cpu.carregar(1, [0.0, 0.0, 0.0, 0.0])
cpu.carregar(2, [5.0, 6.0, 7.0, 8.0])
cpu.executar(montar("vtdot.vv v6, v1, v2"))
check("vtdot com vetor de zeros da 0", cpu.ler(6)[0] == 0.0)

# ---------------------------------------------------------------------------
titulo("9. CONVERSAO DE LARGURA (vncvt.t.t)")
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 32)
entrada = [3.14159, 100.0, 0.001, 42.0]
cpu.carregar(1, entrada)
cpu.executar(montar("vncvt.t.t v7, v1"))          # T32 -> T16 (padrao: metade)
r = cpu.ler(7, sew=16)
bom = True
for x, o in zip(entrada, r):
    if not aprox(o, x, 2e-3):
        bom = False
check("T32 -> T16: %s" % [round(v, 4) for v in r], bom)
check("T32 -> T16: bits iguais aos de takum.convert",
      cpu.vregs[7] == [takum.convert(b, 32, 16) for b in cpu.vregs[1]])

cpu.executar(encode_instr("vncvt.t.t", 8, 1, 0), sew_destino=8)   # T32 -> T8
r = cpu.ler(8, sew=8)
bom = True
for x, o in zip(entrada, r):
    if not aprox(o, x, 0.285):   # T8: erro maximo ~28.4% quando M tem 0 bits
        bom = False
check("T32 -> T8 (sew_destino=8): %s" % [round(v, 3) for v in r], bom)

cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 16)
cpu.carregar(1, entrada)
cpu.executar(montar("vncvt.t.t v7, v1"))          # T16 -> T8
r = cpu.ler(7, sew=8)
bom = True
for x, o in zip(entrada, r):
    if not aprox(o, x, 0.285):   # T8: erro maximo ~28.4% quando M tem 0 bits
        bom = False
check("T16 -> T8: %s" % [round(v, 3) for v in r], bom)

# ---------------------------------------------------------------------------
titulo("10. NaR E ZERO PASSANDO PELAS INSTRUCOES")
for sew in (8, 16, 32):
    cpu = ProcessadorZvtakum(vlen=128)
    cpu.vsetvli(2, sew)
    cpu.vregs[1] = [takum.nar_pattern(sew), takum.encode(2.0, sew)]
    cpu.vregs[2] = [takum.encode(3.0, sew), takum.encode(3.0, sew)]
    cpu.executar(montar("vtadd.vv v3, v1, v2"))
    r = cpu.ler(3)
    check("T%-2d NaR + 3 = NaR, 2 + 3 continua normal" % sew,
          math.isnan(r[0]) and not math.isnan(r[1]))

cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(2, 32)
cpu.carregar(1, [0.0, 5.0])
cpu.carregar(2, [7.0, 0.0])
cpu.executar(montar("vtmul.vv v3, v1, v2"))
check("0 * 7 = 0 e 5 * 0 = 0", cpu.ler(3) == [0.0, 0.0])

# ---------------------------------------------------------------------------
titulo("11. CONTADOR DE INSTRUCOES (dado da Fase 3)")
cpu = ProcessadorZvtakum(vlen=128)
cpu.vsetvli(4, 32)                       # conta 1
cpu.carregar(1, valores_a)               # carregar NAO conta (e preparacao)
cpu.carregar(2, valores_b)
cpu.executar(montar("vtadd.vv v3, v1, v2"))   # conta 1
cpu.executar(montar("vtmul.vv v4, v1, v2"))   # conta 1
check("vsetvli + 2 instrucoes = 3 no contador (obtido %d)" % cpu.contador_instr,
      cpu.contador_instr == 3)

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
    import sys
    sys.exit(1)
