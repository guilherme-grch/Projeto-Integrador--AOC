"""Confere a referencia contra GCC/libquadmath. Verificacao independente opcional.

Requer gcc e libquadmath; nao e dependencia do simulador no Windows.
Executar na raiz: python validar_quad_gcc.py
"""
from pathlib import Path
from fractions import Fraction as F
import hashlib,json,math,random,subprocess,tempfile
from referencia_binary128 import round_binary128 as q,spmv_binary128,MIN_NORMAL,MIN_SUBNORMAL,MAX_FINITE
import eval_spmv

def hex_exact(v):
    v=F(v);sign='-' if v<0 else '';v=abs(v)
    d=v.denominator
    assert d & (d-1)==0
    return f'{sign}0x{v.numerator:x}p-{d.bit_length()-1}'

def parse_hex(s):
    if 'inf' in s:return -math.inf if s.startswith('-') else math.inf
    sign=-1 if s.startswith('-') else 1;s=s.lstrip('+-')
    mant,exp=s.split('p');integer,fraction=mant[2:].split('.')
    return sign*F(int(integer+fraction,16),16**len(fraction))*F(2)**int(exp)

def main():
    root=Path(__file__).resolve().parent
    commands=['Q'];expected=[]
    boundary=[F(0),F(1),F(-1),MIN_SUBNORMAL/2,3*MIN_SUBNORMAL/2,MIN_SUBNORMAL,
              MIN_NORMAL-MIN_SUBNORMAL/2,MIN_NORMAL,MAX_FINITE,
              MAX_FINITE+F(2)**16269,MAX_FINITE+F(2)**16270,
              1+F(2)**-113,1+3*F(2)**-113]
    for value in boundary:
        for sign in (1,-1):
            commands.append('R '+hex_exact(sign*value));expected.append(q(sign*value))
    rng=random.Random(913)
    for _ in range(1000):
        a=F(rng.randrange(-(1<<112),1<<112))*F(2)**rng.randint(-16000,15000)
        b=F(rng.randrange(-(1<<112),1<<112))*F(2)**rng.randint(-16000,15000)
        for op,value in [('A',a+b),('M',a*b)]:
            commands.append(op+' '+hex_exact(a)+' '+hex_exact(b));expected.append(q(value))
    arithmetic=len(expected)
    for span in (2,12,30):
        for trial in range(30):
            seed=1000*span+trial;random.seed(seed);rng=random.Random(seed)
            entries=sorted(eval_spmv.gerar_matriz_esparsa(64,.05,span))
            x=[rng.choice([-1,1])*10**rng.uniform(-1,1) for _ in range(64)]
            commands.append(f'S 64 {len(entries)}')
            commands.append(' '.join(v.hex() for v in x))
            commands.extend(f'{i} {j} {v.hex()}' for i,j,v in entries)
            expected.extend(spmv_binary128(entries,x,64))
    with tempfile.TemporaryDirectory() as tmp:
        binary=str(Path(tmp)/'oracle')
        build=['gcc','-std=c11','-O0','-frounding-math','-ffp-contract=off',str(root/'validacao/oraculo_quad.c'),'-lquadmath','-lm','-o',binary]
        subprocess.run(build,check=True,capture_output=True,text=True)
        run=subprocess.run([binary],input='\n'.join(commands)+'\n',capture_output=True,text=True,check=True)
    lines=run.stdout.splitlines()
    assert lines[0]=='113 -16381 16384',lines[0]
    assert len(lines)-1==len(expected)
    for index,(actual,want) in enumerate(zip(lines[1:],expected)):
        assert parse_hex(actual)==want,f'divergencia no caso {index}'
    result={'status':'PASS','oracle':'GCC __float128 / libquadmath, FE_TONEAREST',
            'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],
            'arithmetic_boundary_cases':arithmetic,'matrices':90,'reference_components':5760,
            'comparison':'exact rational equality, zero sign ignored',
            'reference_sha256':hashlib.sha256((root/'referencia_binary128.py').read_bytes()).hexdigest()}
    (root/'resultados/validacao_quad_gcc.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
