"""
zvtakum.py - Simulador funcional da extensao vetorial Zvtakum (Fase 2).

Este modelo de arquitetura nao e RTL sintetizavel. Ele define COMO as instrucoes sao codificadas em bits e
COMO o processador as executa.

Tres partes:

  1. ENCODING  - monta a palavra de 32 bits de cada instrucao
                 (o que um "assembler" faria)
  2. DECODING  - le a palavra de 32 bits e descobre qual instrucao e
                 (o que o decodificador do processador faz)
  3. EXECUCAO  - aplica a operacao nos registradores vetoriais
                 (o que a ALU faz)

Formato das instrucoes (R-type vetorial, com campos inspirados no RVV):

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

# 1. DEFINICAO DO ENCODING

OPCODE_ZVTAKUM = 0b1011011   # 0x5B - espaco custom-2 do RISC-V
FUNCT3_OPTVV = 0b100         # nossa categoria "Takum vector-vector"

# funct6 de cada instrucao proposta (Tabela 1 do enunciado)
FUNCT6 = {
    "vtadd.vv":  0b000000,
    "vtsub.vv":  0b000010,
    "vtmul.vv":  0b100100,
    "vtdot.vv":  0b111000,
    "vncvt.t.t": 0b010010,
    "vtspmv.v": 0b111001,  # extensao adicional: matriz CSR completa
}

# Codificacao da largura de elemento Takum (equivalente ao SEW do RVV)
SEW_TAKUM = {8: 0b000, 16: 0b001, 32: 0b010}
SEW_DECODE = {v: k for k, v in SEW_TAKUM.items()}


def encode_instr(nome: str, vd: int, vs1: int, vs2: int, vm: int = 1) -> int:
    """Monta a palavra de 32 bits da instrucao (papel do assembler)."""
    if nome not in FUNCT6:
        raise ValueError(f"instrucao desconhecida: {nome}")
    for reg, rn in ((vd, "vd"), (vs1, "vs1"), (vs2, "vs2")):
        if type(reg) is not int or not 0 <= reg < 32:
            raise ValueError(f"{rn}={reg} fora da faixa de registradores v0..v31")

    if type(vm) is not int or vm not in (0,1):
        raise ValueError("vm invalido")
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
    if type(palavra) is not int or not 0 <= palavra < (1 << 32):
        raise ValueError("instrucao deve ter 32 bits")
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


# 2. ESTADO DO PROCESSADOR VETORIAL

class ProcessadorZvtakum:
    """Subconjunto custom, LMUL=1, vm=1; execucao por ciclos com writeback atomico."""
    NUM_VREGS = 32

    def __init__(self, vlen=128, lanes=4, row_units=2):
        from modelo_paralelo import MotorParalelo
        if type(vlen) is not int or vlen < 32 or vlen % 32:
            raise ValueError('VLEN deve ser multiplo de 32 e >=32')
        self.vlen = vlen
        self.vregs = [[] for _ in range(32)]
        self.widths = [None]*32
        self.matrices = {}
        self.sew, self.vl, self.contador_instr = 32, 0, 0
        self.motor = MotorParalelo(lanes, row_units)

    def _idle(self):
        if self.motor.busy:
            raise RuntimeError('instrucao em andamento')

    @staticmethod
    def _reg(reg):
        if type(reg) is not int or not 0 <= reg < 32:
            raise ValueError('registrador deve estar em v0..v31')

    def vsetvli(self, n_elementos, sew):
        self._idle()
        if sew not in SEW_TAKUM or type(n_elementos) is not int or n_elementos < 0:
            raise ValueError('SEW ou VL invalido')
        self.sew, self.vl = sew, min(n_elementos,self.vlen//sew)
        self.contador_instr += 1
        return self.vl

    def carregar(self, vreg, valores, sew=None):
        self._idle(); self._reg(vreg)
        sew = self.sew if sew is None else sew
        valores = list(valores)
        if sew not in SEW_TAKUM or len(valores)*sew > self.vlen:
            raise ValueError('largura ou capacidade invalida')
        self.vregs[vreg] = [takum.encode(v,sew) for v in valores]
        self.widths[vreg] = sew

    def carregar_bits(self,vreg,bits,sew=None):
        self._idle(); self._reg(vreg)
        sew = self.sew if sew is None else sew
        bits = list(bits)
        if sew not in SEW_TAKUM or len(bits)*sew > self.vlen or any(type(b) is not int or not 0<=b<1<<sew for b in bits):
            raise ValueError('bits ou capacidade invalidos')
        self.vregs[vreg], self.widths[vreg] = bits,sew

    def ler(self,vreg,sew=None):
        self._reg(vreg)
        sew = sew if sew is not None else (self.widths[vreg] or self.sew)
        if sew not in SEW_TAKUM:
            raise ValueError('SEW invalido')
        return [takum.decode(b,sew) for b in self.vregs[vreg]]

    def carregar_matriz(self,descriptor,entradas,nrows,ncols,sew=None):
        """Prepara memoria CSR local. Nao e instrucao RVV de carga."""
        self._idle(); self._reg(descriptor)
        sew = self.sew if sew is None else sew
        if sew not in SEW_TAKUM or type(nrows) is not int or type(ncols) is not int or min(nrows,ncols)<1:
            raise ValueError('dimensoes invalidas')
        out = min(2*sew,32)
        if ncols*sew>self.vlen or nrows*out>self.vlen:
            raise ValueError('matriz excede capacidade do vetor de entrada/saida')
        rows=[[] for _ in range(nrows)]; seen=set()
        for i,j,v in entradas:
            if type(i) is not int or type(j) is not int or not 0<=i<nrows or not 0<=j<ncols or (i,j) in seen:
                raise ValueError('indice invalido ou duplicado')
            seen.add((i,j)); rows[i].append((j,takum.encode(v,sew)))
        for row in rows: row.sort()
        row_ptr = [0]
        col_idx, values = [], []
        for row in rows:
            for column, value in row:
                col_idx.append(column)
                values.append(value)
            row_ptr.append(len(values))
        self.matrices[descriptor] = {
            'row_ptr': row_ptr, 'col_idx': col_idx, 'values': values,
            'ncols': ncols, 'sew': sew,
        }

    def _source(self,reg,count,sew):
        a=self.vregs[reg]
        if self.widths[reg] not in (None,sew) or len(a)<count or len(a)*sew>self.vlen:
            raise ValueError('fonte curta, largura ou capacidade inconsistente')
        if any(type(b) is not int or not 0<=b<1<<sew for b in a):
            raise ValueError('padrao invalido')
        return a[:count].copy()

    def iniciar(self,palavra,sew_destino=None):
        self._idle()
        i=decode_instr(palavra); nome=i['nome']; n=self.sew
        if i['vm'] != 1: raise ValueError('mascara nao implementada: use vm=1')
        vd,vs1,vs2=i['vd'],i['vs1'],i['vs2']
        out=n
        if nome=='vtspmv.v':
            if sew_destino is not None: raise ValueError('largura destino deriva da instrucao')
            if vs2 not in self.matrices: raise ValueError('descritor CSR inexistente')
            matrix = self.matrices[vs2]
            ncols = matrix['ncols']
            if matrix['sew'] != n or self.vl != ncols:
                raise ValueError('VL/SEW diverge da matriz')
            x = self._source(vs1, ncols, n)
            ptr, columns, values = matrix['row_ptr'], matrix['col_idx'], matrix['values']
            pairs = [[(values[k], x[columns[k]]) for k in range(ptr[row], ptr[row+1])]
                     for row in range(len(ptr)-1)]
            out=min(2*n,32)
            program=self.motor.dot_rows(pairs,n,out)
        else:
            a=self._source(vs1,self.vl,n)
            b=[] if nome=='vncvt.t.t' else self._source(vs2,self.vl,n)
            if nome=='vncvt.t.t':
                out=n//2
                if out not in (8,16) or (sew_destino is not None and sew_destino!=out):
                    raise ValueError('conversao permitida: T32->T16 ou T16->T8')
                if vs2!=0: raise ValueError('vs2 reservado deve ser zero')
            elif sew_destino is not None:
                raise ValueError('largura destino deriva da instrucao')
            if nome=='vtdot.vv':
                out=min(2*n,32)
                program=self.motor.dot_rows([list(zip(a,b))],n,out)
            else:
                program=self.motor.elementwise(a,b,n,nome,out)
        def commit(result):
            self.vregs[vd]=result
            self.widths[vd]=out
            self.contador_instr+=1
        self.motor.start(program,commit,nome)

    def tick(self):
        return self.motor.tick()

    def executar(self,palavra,sew_destino=None):
        self.iniciar(palavra,sew_destino)
        self.motor.run()
        return self.vregs[decode_instr(palavra)['vd']]


# 3. "ASSEMBLER" MINIMO - texto para palavra de 32 bits

def montar(linha: str) -> int:
    """Converte uma linha de assembly Zvtakum em palavra de 32 bits.

    Exemplo:  montar("vtadd.vv v3, v1, v2")  ->  0x0208C1DB
    """
    linha = linha.split("#")[0].strip()        # remove comentarios
    if not linha:
        raise ValueError("linha vazia")
    partes = linha.replace(",", " ").split()
    nome = partes[0]
    expected = 2 if nome == 'vncvt.t.t' else 3
    import re
    if len(partes) != expected+1 or any(not re.fullmatch(r'[vV]\d+', p) for p in partes[1:]):
        raise ValueError('operandos invalidos')
    regs = [int(p[1:]) for p in partes[1:]]
    if expected == 2: regs.append(0)
    vd, vs1, vs2 = regs
    return encode_instr(nome, vd, vs1, vs2)


def desmontar(palavra: int) -> str:
    """Converte a palavra de 32 bits de volta em texto (papel do disassembler)."""
    i = decode_instr(palavra)
    if i["nome"] == "vncvt.t.t":
        return f"{i['nome']} v{i['vd']}, v{i['vs1']}"
    return f"{i['nome']} v{i['vd']}, v{i['vs1']}, v{i['vs2']}"
