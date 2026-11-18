"""Modelo por ciclos: lanes e bancos de linhas com barreiras por estagio.
Latencias sao HIPOTESES de microarquitetura, nao resultados de sintese.
Aritmetica interna binaria de 113 bits sobre entradas decodificadas em float64.
"""
from fractions import Fraction
import math
import takum


from referencia_binary128 import round_binary128 as quad


def decode_operand(bits, sew):
    v = takum.decode(bits, sew)
    return None if math.isnan(v) else Fraction(v)


def add_quad(a, b):
    return None if a is None or b is None else quad(a + b)


def mul_quad(a, b):
    return None if a is None or b is None else quad(a * b)


def encode_result(value, sew):
    return takum.nar_pattern(sew) if value is None else takum.encode(float(value), sew)


class MotorParalelo:
    """Um tick avanca um estagio. Destinos so mudam no writeback."""
    def __init__(self, lanes=4, row_units=2):
        if type(lanes) is not int or lanes < 1 or type(row_units) is not int or row_units < 1:
            raise ValueError('lanes e row_units devem ser inteiros positivos')
        self.lanes, self.row_units = lanes, row_units
        self.cycle = 0
        self.busy = False
        self.done = False
        self.trace = []
        self._program = None
        self._commit = None

    def start(self, program, commit, instruction):
        if self.busy:
            raise RuntimeError('unidade ocupada')
        self._program = iter(program)
        self._commit = commit
        self.instruction = instruction
        self.busy, self.done = True, False
        self.trace = []

    def tick(self):
        if not self.busy:
            raise RuntimeError('nenhuma instrucao em andamento')
        self.cycle += 1
        event = next(self._program)
        event = dict(event, cycle=self.cycle, instruction=self.instruction)
        if event['stage'] == 'writeback':
            self._commit(event['result'])
            self.busy, self.done = False, True
        self.trace.append(event)
        return event

    def run(self):
        while self.busy:
            self.tick()
        return self.trace

    def dot_rows(self, rows, sew, out_sew):
        """rows: listas de pares de bits; uma unica instrucao para todas."""
        yield {'stage': 'issue', 'operations': []}
        results = []
        for base in range(0, len(rows), self.row_units):
            group = rows[base:base+self.row_units]
            decoded = [[] for _ in group]
            products = [[] for _ in group]
            max_len = max(map(len, group), default=0)
            for offset in range(0, max_len, self.lanes):
                operations = []
                for bank, row in enumerate(group):
                    for lane, (a, b) in enumerate(row[offset:offset+self.lanes]):
                        decoded[bank].append((decode_operand(a, sew), decode_operand(b, sew)))
                        operations.append({'bank': bank, 'lane': lane, 'row': base+bank, 'element': offset+lane})
                yield {'stage': 'decode', 'operations': operations}
            for offset in range(0, max_len, self.lanes):
                operations = []
                for bank, row in enumerate(decoded):
                    for lane, (a, b) in enumerate(row[offset:offset+self.lanes]):
                        products[bank].append(mul_quad(a, b))
                        operations.append({'bank': bank, 'lane': lane, 'row': base+bank, 'element': offset+lane})
                yield {'stage': 'multiply', 'operations': operations}
            level = 0
            while any(len(row) > 1 for row in products):
                level += 1
                nxt = [[] for _ in products]
                max_pairs = max((len(row)+1)//2 for row in products)
                for offset in range(0, max_pairs, self.lanes):
                    operations = []
                    for bank, row in enumerate(products):
                        for lane in range(self.lanes):
                            i = 2*(offset+lane)
                            if i >= len(row):
                                continue
                            nxt[bank].append(add_quad(row[i], row[i+1]) if i+1 < len(row) else row[i])
                            operations.append({'bank':bank, 'lane':lane, 'row':base+bank, 'pair':i//2})
                    yield {'stage': 'reduce', 'level':level, 'operations':operations}
                products = nxt
            for row in products:
                results.append(encode_result(row[0] if row else Fraction(0), out_sew))
            yield {'stage':'encode', 'operations':[{'bank':b,'row':base+b} for b in range(len(group))]}
        yield {'stage':'writeback', 'operations':[], 'result':results}

    def elementwise(self, a, b, sew, name, out_sew):
        yield {'stage':'issue', 'operations':[]}
        result = []
        funcs = {'vtadd.vv':takum.add, 'vtsub.vv':takum.sub, 'vtmul.vv':takum.mul}
        for offset in range(0, len(a), self.lanes):
            ops = [{'bank':0,'lane':i,'element':offset+i} for i in range(min(self.lanes,len(a)-offset))]
            yield {'stage':'decode', 'operations':ops}
            for i in range(offset, min(len(a),offset+self.lanes)):
                result.append(takum.convert(a[i],sew,out_sew) if name == 'vncvt.t.t' else funcs[name](a[i],b[i],sew))
            yield {'stage':'execute', 'operations':ops}
            yield {'stage':'encode', 'operations':ops}
        yield {'stage':'writeback','operations':[],'result':result}
