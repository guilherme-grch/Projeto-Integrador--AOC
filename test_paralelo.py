"""Testes de contrato, concorrencia, referencia independente e SpMV completa."""
import unittest
import math
import random
from fractions import Fraction
from modelo_paralelo import quad, MotorParalelo
from zvtakum import ProcessadorZvtakum, montar, encode_instr
import takum
import analise_erro

class TestParalelo(unittest.TestCase):
    def test_referencia_quad(self):
        # Resultados analiticos conhecidos, sem reutilizar o arredondador como oraculo.
        third = Fraction(2**114-1, 3*2**114)
        self.assertEqual(quad(Fraction(1,3)), third)
        self.assertEqual(quad(Fraction(-1,3)), -third)
        self.assertEqual(quad(2**200+2**87), 2**200)
        self.assertEqual(quad(2**200+3*2**87), 2**200+2**89)

    def test_validacao(self):
        for vl in [-1,1.5]:
            with self.assertRaises(ValueError): ProcessadorZvtakum().vsetvli(vl,32)
        with self.assertRaises(ValueError): ProcessadorZvtakum(0)
        with self.assertRaises(ValueError): MotorParalelo(0)
        for text in ['vtadd.vv','vtadd.vv v1,v2','vtadd.vv v1,v2,v3,v4','vtadd.vv x1,v2,v3']:
            with self.assertRaises(ValueError): montar(text)
        c=ProcessadorZvtakum();c.vsetvli(4,32);c.carregar(1,[1,2]);c.carregar(2,[1,2,3,4])
        with self.assertRaises(ValueError):c.executar(montar('vtadd.vv v3,v1,v2'))
        c.vsetvli(2,32)
        with self.assertRaises(ValueError):c.executar(encode_instr('vtadd.vv',3,1,2,vm=0))
        c.vsetvli(1,8);c.carregar(1,[1])
        with self.assertRaises(ValueError):c.executar(montar('vncvt.t.t v3,v1'))
        with self.assertRaises(ValueError):c.carregar(1,range(17))

    def test_commit_e_paralelismo(self):
        c=ProcessadorZvtakum(lanes=4);c.vsetvli(4,32);c.carregar(1,[1]*4);c.carregar(2,[1]*4)
        before=c.contador_instr;c.iniciar(montar('vtdot.vv v3,v1,v2'))
        with self.assertRaises(RuntimeError):c.vsetvli(1,32)
        with self.assertRaises(RuntimeError):c.iniciar(montar('vtadd.vv v4,v1,v2'))
        while c.motor.busy:
            self.assertEqual(c.vregs[3],[])
            e=c.tick()
            if e['stage']=='writeback':break
        self.assertEqual(c.contador_instr,before+1)
        self.assertEqual([e['stage'] for e in c.motor.trace],['issue','decode','multiply','reduce','reduce','encode','writeback'])
        self.assertEqual(max(len(e['operations']) for e in c.motor.trace),4)
        self.assertAlmostEqual(c.ler(3)[0],4,places=6)

    def test_lanes_invariantes(self):
        rng=random.Random(100)
        for sew in (8,16,32):
            for length in (0,1,3,4,5,17,31):
                A=[rng.uniform(-20,20) for _ in range(length)]
                B=[rng.uniform(-20,20) for _ in range(length)]
                values=[];cycles=[]
                for lanes in (1,2,4,8):
                    c=ProcessadorZvtakum(1024,lanes);c.vsetvli(length,sew);c.carregar(1,A);c.carregar(2,B)
                    values.append(c.executar(montar('vtdot.vv v3,v1,v2')))
                    cycles.append(len(c.motor.trace))
                    for e in c.motor.trace:
                        resources=[(o['bank'],o.get('lane',0)) for o in e['operations']]
                        self.assertEqual(len(resources),len(set(resources)))
                        self.assertLessEqual(len(resources),lanes*2)
                self.assertTrue(all(x==values[0] for x in values))
                self.assertEqual(cycles,sorted(cycles,reverse=True))

    def test_spmv_uma_instrucao(self):
        rng=random.Random(77)
        for sew in (8,16,32):
            n=12;x=[rng.uniform(-2,2) for _ in range(n)]
            entries=[(i,j,rng.uniform(-5,5)) for i in range(n-1) for j in range(n) if rng.random()<.5]
            c=ProcessadorZvtakum(1024,4,2);c.vsetvli(n,sew);c.carregar(1,x);c.carregar_matriz(2,entries,n,n)
            before=c.contador_instr
            result=c.executar(montar('vtspmv.v v3,v1,v2'))
            self.assertEqual(c.contador_instr,before+1)
            self.assertEqual(len(result),n)
            self.assertEqual(result[-1],0)
            # Reference: independent exact sum of decoded dyadic operands.
            ref=[Fraction(0) for _ in range(n)]
            for i,j,v in entries:
                a=Fraction(takum.decode(takum.encode(v,sew),sew));b=Fraction(takum.decode(takum.encode(x[j],sew),sew))
                ref[i]+=a*b
            self.assertEqual(result,[takum.encode(float(y),min(2*sew,32)) for y in ref])
            active=[e for e in c.motor.trace if e['stage']=='multiply']
            self.assertTrue(any(len(set(o['row'] for o in e['operations']))==2 for e in active))
            # Row scheduling does not alter numerical results.
            c2=ProcessadorZvtakum(1024,1,1);c2.vsetvli(n,sew);c2.carregar(1,x);c2.carregar_matriz(2,entries,n,n)
            self.assertEqual(result,c2.executar(montar('vtspmv.v v3,v1,v2')))

    def test_nar_zero_alias(self):
        for sew in (8,16,32):
            c=ProcessadorZvtakum();c.vsetvli(2,sew);c.carregar_bits(1,[takum.nar_pattern(sew),0]);c.carregar(2,[0,1])
            self.assertEqual(c.executar(montar('vtdot.vv v1,v1,v2')),[takum.nar_pattern(min(2*sew,32))])
            c.vsetvli(0,sew)
            self.assertEqual(c.executar(montar('vtdot.vv v3,v0,v0')),[0])
            c.vsetvli(2,sew);c.carregar(1,[1,-1]);c.carregar(2,[1,1])
            self.assertEqual(c.executar(montar('vtdot.vv v1,v1,v2')),[0])

    def test_matriz_invalida(self):
        c=ProcessadorZvtakum();c.vsetvli(2,32);c.carregar(1,[1,2])
        for entries in [[(0,2,1)],[(0,0,1),(0,0,2)]]:
            with self.assertRaises(ValueError):c.carregar_matriz(2,entries,2,2)
        with self.assertRaises(ValueError):c.executar(montar('vtspmv.v v3,v1,v2'))
        c.carregar_matriz(2,[],2,2);c.vsetvli(1,32)
        with self.assertRaises(ValueError):c.executar(montar('vtspmv.v v3,v1,v2'))

    def test_csr_layout_and_empty_rows(self):
        c = ProcessadorZvtakum(256)
        c.vsetvli(3,32)
        c.carregar(1,[1,2,3])
        c.carregar_matriz(2,[(2,1,5),(0,2,2),(0,0,1)],3,3)
        d=c.matrices[2]
        self.assertEqual(d['row_ptr'],[0,2,2,3])
        self.assertEqual(d['col_idx'],[0,2,1])
        c.executar(montar('vtspmv.v v3,v1,v2'))
        for got,want in zip(c.ler(3),[7,0,10]):self.assertAlmostEqual(got,want,places=5)

    def test_t32_sampled_roundtrip(self):
        rng=random.Random(32000)
        for _ in range(10000):
            bits=rng.randrange(1<<32)
            self.assertEqual(takum.encode(takum.decode(bits,32),32),bits)

    def test_roundtrip(self):
        for sew in (8,16):
            for b in range(1<<sew):
                self.assertEqual(takum.encode(takum.decode(b,sew),sew),b)

class TestRegressoes(unittest.TestCase):
    def test_empates_exatos(self):
        for n in (8,16,32):
            for b in (1,2,3,(1<<(n-2))-2,(1<<(n-2))-1,1<<(n-2),(1<<(n-1))-2):
                middle=(takum.log_value(b,n)+takum.log_value(b+1,n))/2
                expected=b if b%2==0 else b+1
                self.assertEqual(takum.encode_log(middle,n),expected)
                self.assertEqual(takum.encode_log(middle,n,True),(-expected)% (1<<n))
                eps=Fraction(1,2**100)
                self.assertEqual(takum.encode_log(middle-eps,n),b)
                self.assertEqual(takum.encode_log(middle+eps,n),b+1)

    def test_benchmark_zeros_e_largo(self):
        import eval_spmv,eval_acumulador
        self.assertEqual(eval_spmv.erro_relativo([0,1],[0,0]),[0.0,math.inf])
        with self.assertRaises(ValueError):eval_spmv.erro_relativo([1],[])
        with self.assertRaises(ValueError):eval_spmv.gerar_matriz_esparsa(2,2,1)
        self.assertEqual(eval_spmv.gerar_matriz_esparsa(2,0,1),[])
        entries=[(0,0,1.1),(0,1,-.9)];x=[1.2,.8]
        for name,(ri,_,ra) in eval_acumulador.PARES.items():
            result=eval_acumulador.spmv_acumulador_largo(entries,x,1,ri,ra)
            expected=ra(ra(ri(1.1)*ri(1.2))+ri(-.9)*ri(.8))
            self.assertEqual(result,[expected])

    def test_oraculo_operacoes(self):
        # Decode independently at high precision, compare operation rounded in log.
        import mpmath as mp
        mp.mp.dps=70
        def decode(b,n):
            if b==0:return mp.mpf(0)
            if b==1<<(n-1):return mp.nan
            t=format(b,'0%db'%n)+'0'*max(0,12-n)
            S,D,R=int(t[0]),int(t[1]),int(t[2:5],2);r=R if D else 7-R
            c=(2**r-1 if D else -2**(r+1)+1)+(int(t[5:5+r],2) if r else 0)
            rest=t[5+r:];m=mp.mpf(int(rest,2))/2**len(rest) if rest else 0
            return (-1 if S else 1)*mp.exp(((-1 if S else 1)*(c+m))/2)
        table=[(decode(b,8),b) for b in range(1,128)]
        def encode(v):
            if v==0:return 0
            if mp.isnan(v):return 128
            best=min(table,key=lambda p:(abs(mp.log(abs(v))-mp.log(p[0])),p[1]%2))[1]
            return best if v>0 else (-best)%256
        rng=random.Random(811)
        # Random non-boundary cases: float64 may place exact theoretical ties
        # on either side, so exact log ties are checked separately above.
        cases=0
        for _ in range(300):
            a,b=rng.randrange(256),rng.randrange(256)
            av,bv=decode(a,8),decode(b,8)
            for op,ref in [(takum.add,av+bv),(takum.sub,av-bv),(takum.mul,av*bv)]:
                if mp.isfinite(ref) and ref!=0:
                    distances=sorted(abs(mp.log(abs(ref))-mp.log(v)) for v,_ in table)
                    if abs(distances[0]-distances[1])<mp.mpf('1e-13'):continue
                self.assertEqual(op(a,b,8),encode(ref))
                cases+=1
        self.assertGreater(cases,600)

if __name__=='__main__':unittest.main(verbosity=2)
