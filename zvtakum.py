"""
zvtakum.py - Simulador funcional da extensao vetorial Zvtakum (Fase 2).

Este arquivo faz o papel que, num projeto de hardware, seria feito pelo
VHDL/Verilog: ele define COMO as instrucoes sao codificadas em bits e
COMO o processador as executa.

Tres partes:

  1. ENCODING  - monta a palavra de 32 bits de cada instrucao
                 (o que um "assembler" faria)
  2. DECODING  - le a palavra de 32 bits e descobre qual instrucao e
                 (o que o decodificador do processador faz)
  3. EXECUCAO  - aplica a operacao nos registradores vetoriais
                 (o que a ALU faz)

Formato das instrucoes (R-type vetorial, igual ao RVV oficial):

    bits:  31..26 | 25 | 24..20 | 19..15 | 14..12 | 11..7 | 6..0
    campo: funct6 | vm |  vs2   |  vs1   | funct3 |  vd   | opcode
              6      1     5        5        3       5       7

  - opcode: escolhemos 0x5B (espaco "custom-2", livre na spec RISC-V)
            para nao colidir com o OP-V oficial do RVV (0x57)
  - funct3: 0b100 -> "OPTVV" (Takum vector-vector), nossa categoria nova
  - funct6: seleciona qual operacao Takum (add/sub/mul/dot/cvt)
  - vm:     bit de mascara (1 = sem mascara, comportamento padrao do RVV)
"""

import takum

# ---------------------------------------------------------------------------
# 1. DEFINICAO DO ENCODING
# ---------------------------------------------------------------------------

OPCODE_ZVTAKUM = 0b1011011   # 0x5B - espaco custom-2 do RISC-V
FUNCT3_OPTVV = 0b100         # nossa categoria "Takum vector-vector"

# funct6 de cada instrucao proposta (Tabela 1 do enunciado)
FUNCT6 = {
    "vtadd.vv":  0b000000,
    "vtsub.vv":  0b000010,
    "vtmul.vv":  0b100100,
    "vtdot.vv":  0b111000,
    "vncvt.t.t": 0b010010,
}

# Codificacao da largura de elemento Takum (equivalente ao SEW do RVV)
SEW_TAKUM = {8: 0b000, 16: 0b001, 32: 0b010}
SEW_DECODE = {v: k for k, v in SEW_TAKUM.items()}


def encode_instr(nome: str, vd: int, vs1: int, vs2: int, vm: int = 1) -> int:
    """Monta a palavra de 32 bits da instrucao (papel do assembler)."""
    if nome not in FUNCT6:
        raise ValueError(f"instrucao desconhecida: {nome}")
    for reg, rn in ((vd, "vd"), (vs1, "vs1"), (vs2, "vs2")):
        if not 0 <= reg < 32:
            raise ValueError(f"{rn}={reg} fora da faixa de registradores v0..v31")

    palavra = 0
    palavra |= (FUNCT6[nome] & 0b111111) << 26
    palavra |= (vm & 0b1) << 25
    palavra |= (vs2 & 0b11111) << 20
    palavra |= (vs1 & 0b11111) << 15
    palavra |= (FUNCT3_OPTVV & 0b111) << 12
    palavra |= (vd & 0b11111) << 7
    palavra |= OPCODE_ZVTAKUM & 0b1111111
    return palavra


def decode_instr(palavra: int) -> dict:
    """Le a palavra de 32 bits e identifica a instrucao (papel do decodificador)."""
    opcode = palavra & 0b1111111
    funct3 = (palavra >> 12) & 0b111
    funct6 = (palavra >> 26) & 0b111111

    if opcode != OPCODE_ZVTAKUM or funct3 != FUNCT3_OPTVV:
        raise ValueError(f"nao e uma instrucao Zvtakum: 0x{palavra:08x}")

    nome = None
    for k, v in FUNCT6.items():
        if v == funct6:
            nome = k
            break
    if nome is None:
        raise ValueError(f"funct6 desconhecido: {funct6:06b}")

    return {
        "nome": nome,
        "vd": (palavra >> 7) & 0b11111,
        "vs1": (palavra >> 15) & 0b11111,
        "vs2": (palavra >> 20) & 0b11111,
        "vm": (palavra >> 25) & 0b1,
        "palavra": palavra,
    }


# ---------------------------------------------------------------------------
# 2. ESTADO DO PROCESSADOR VETORIAL
# ---------------------------------------------------------------------------

class ProcessadorZvtakum:
    """Simula o estado vetorial de um processador RISC-V com a extensao Zvtakum.

    VLEN = quantos BITS cabem em cada registrador vetorial (fixo no hardware).
    SEW  = largura de cada ELEMENTO (8, 16 ou 32 -> T8, T16, T32).
    VL   = quantos elementos serao efetivamente processados.

    Ex.: VLEN=128 e SEW=32 -> cabem 4 elementos T32 por registrador.
    """

    NUM_VREGS = 32

    def __init__(self, vlen: int = 128):
        self.vlen = vlen
        # cada registrador vetorial guarda uma lista de padroes de bits
        self.vregs = [[] for _ in range(self.NUM_VREGS)]
        self.sew = 32          # largura de elemento atual
        self.vl = 0            # comprimento vetorial atual
        self.contador_instr = 0

    # --- configuracao (equivalente a instrucao vsetvli) -------------------
    def vsetvli(self, n_elementos: int, sew: int) -> int:
        """Configura largura de elemento e comprimento vetorial.

        Devolve o VL efetivo (pode ser menor que o pedido, se nao couber
        no registrador - exatamente como o vsetvli real do RVV).
        """
        if sew not in SEW_TAKUM:
            raise ValueError(f"SEW invalido: {sew} (use 8, 16 ou 32)")
        vlmax = self.vlen // sew
        self.sew = sew
        self.vl = min(n_elementos, vlmax)
        self.contador_instr += 1
        return self.vl

    # --- carga/leitura de dados -----------------------------------------
    def carregar(self, vreg: int, valores, sew: int = None):
        """Carrega uma lista de numeros reais num registrador vetorial,
        convertendo cada um para o formato Takum."""
        sew = sew or self.sew
        self.vregs[vreg] = [takum.encode(v, sew) for v in valores]

    def ler(self, vreg: int, sew: int = None):
        """Le um registrador vetorial de volta como numeros reais."""
        sew = sew or self.sew
        return [takum.decode(b, sew) for b in self.vregs[vreg]]

    # --- execucao --------------------------------------------------------
    def executar(self, palavra: int, sew_destino: int = None):
        """Decodifica e executa uma instrucao de 32 bits."""
        instr = decode_instr(palavra)
        nome = instr["nome"]
        vd, vs1, vs2 = instr["vd"], instr["vs1"], instr["vs2"]
        n = self.sew

        a = self.vregs[vs1]
        b = self.vregs[vs2]

        if nome == "vtadd.vv":
            self.vregs[vd] = [takum.add(x, y, n)
                              for x, y in zip(a[:self.vl], b[:self.vl])]

        elif nome == "vtsub.vv":
            self.vregs[vd] = [takum.sub(x, y, n)
                              for x, y in zip(a[:self.vl], b[:self.vl])]

        elif nome == "vtmul.vv":
            self.vregs[vd] = [takum.mul(x, y, n)
                              for x, y in zip(a[:self.vl], b[:self.vl])]

        elif nome == "vtdot.vv":
            # Produto escalar com acumulo em precisao AMPLIADA.
            # Entradas em T{n}, acumulador em T{2n} (limitado a 32).
            n_acc = min(2 * n, 32)
            acc = takum.encode(0.0, n_acc)
            for x, y in zip(a[:self.vl], b[:self.vl]):
                acc = takum.fma(x, y, acc, n, n_out=n_acc)
            self.vregs[vd] = [acc]   # resultado escalar, no elemento 0

        elif nome == "vncvt.t.t":
            # Conversao com REDUCAO de largura (ex.: T16 -> T8)
            destino = sew_destino or (n // 2)
            self.vregs[vd] = [takum.convert(x, n, destino)
                              for x in a[:self.vl]]

        self.contador_instr += 1
        return self.vregs[vd]


# ---------------------------------------------------------------------------
# 3. "ASSEMBLER" MINIMO - texto para palavra de 32 bits
# ---------------------------------------------------------------------------

def montar(linha: str) -> int:
    """Converte uma linha de assembly Zvtakum em palavra de 32 bits.

    Exemplo:  montar("vtadd.vv v3, v1, v2")  ->  0x0208C1DB
    """
    linha = linha.split("#")[0].strip()        # remove comentarios
    if not linha:
        raise ValueError("linha vazia")
    partes = linha.replace(",", " ").split()
    nome = partes[0]
    regs = [int(p.lstrip("vV")) for p in partes[1:]]
    while len(regs) < 3:
        regs.append(0)
    vd, vs1, vs2 = regs[0], regs[1], regs[2]
    return encode_instr(nome, vd, vs1, vs2)


def desmontar(palavra: int) -> str:
    """Converte a palavra de 32 bits de volta em texto (papel do disassembler)."""
    i = decode_instr(palavra)
    if i["nome"] == "vncvt.t.t":
        return f"{i['nome']} v{i['vd']}, v{i['vs1']}"
    return f"{i['nome']} v{i['vd']}, v{i['vs1']}, v{i['vs2']}"
