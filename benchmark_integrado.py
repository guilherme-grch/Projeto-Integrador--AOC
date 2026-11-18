"""Experimento C: executa ISA real do modelo, compara com binary128.
IEEE recebe a mesma acumulacao em arvore a 113 bits e saida ampliada.
"""
import argparse,csv,json,math,random,statistics
from pathlib import Path
from fractions import Fraction
import numpy as np
import takum,eval_spmv
from referencia_binary128 import spmv_binary128
from modelo_paralelo import quad
from zvtakum import ProcessadorZvtakum,montar

def reduce_values(vals):
    if not vals:return Fraction(0)
    while len(vals)>1:vals=[quad(vals[i]+vals[i+1]) if i+1<len(vals) else vals[i] for i in range(0,len(vals),2)]
    return vals[0]

def ieee_tree(entries,x,n,inround,outround):
    rows=[[] for _ in range(n)];xr=[inround(v) for v in x]
    for i,j,v in sorted(entries):
        a,b=inround(v),xr[j]
        rows[i].append(None if not math.isfinite(a) or not math.isfinite(b) else quad(Fraction(a)*Fraction(b)))
    return [math.nan if any(v is None for v in row) else outround(float(reduce_values(row))) for row in rows]

def metrics(y,ref):
    if len(y) != len(ref):
        raise ValueError("vetores de resultado e referencia com tamanhos diferentes")
    out=[]
    for a,b in zip(y,ref):
        bad=not math.isfinite(a)
        absolute=math.inf if bad else float(abs(Fraction(a)-b))
        relative=None if b==0 else (math.inf if bad else float(abs((Fraction(a)-b)/b)))
        out.append((absolute,relative,bad,int(b==0 and a!=0)))
    return out

def summary(items):
    rel=[x[1] for x in items if x[1] is not None and math.isfinite(x[1])]
    rel.sort()
    def q(p):return rel[int(p*(len(rel)-1))] if rel else None
    return {'samples':len(items),'relative_samples':len(rel),'nonfinite_pct':100*sum(x[2] for x in items)/len(items),'zero_mismatches':sum(x[3] for x in items),'p50_finite':q(.5),'p95_finite':q(.95),'max_finite':max(rel) if rel else None,'max_absolute_finite':max((x[0] for x in items if math.isfinite(x[0])),default=None)}

def run(trials=30):
    results={};raw=[];timing=[]
    for span in (2,12,30):
        data={name:[] for name in eval_spmv.FORMATOS}
        for t in range(trials):
            rng=random.Random(1000*span+t)
            random.seed(1000*span+t)
            entries=eval_spmv.gerar_matriz_esparsa(64,.05,span)
            x=[rng.choice([-1,1])*10**rng.uniform(-1,1) for _ in range(64)]
            ref=spmv_binary128(sorted(entries),x,64)
            for sew in (8,16,32):
                cpu=ProcessadorZvtakum(2048,4,2);cpu.vsetvli(64,sew);cpu.carregar(1,x);cpu.carregar_matriz(2,entries,64,64)
                count=cpu.contador_instr;bits=cpu.executar(montar('vtspmv.v v3,v1,v2'));assert cpu.contador_instr-count==1
                y=cpu.ler(3);name='Takum T%d'%sew
                m=metrics(y,ref);data[name].extend(m)
                for row,(ab,re,bad,zm) in enumerate(m):raw.append([span,t,name,row,ab,re,bad,zm])
                if t==0:
                    one=ProcessadorZvtakum(2048,1,1);one.vsetvli(64,sew);one.carregar(1,x);one.carregar_matriz(2,entries,64,64)
                    assert one.executar(montar('vtspmv.v v3,v1,v2'))==bits
                    counts=[0]*64
                    for i,j,v in entries:counts[i]+=1
                    chunks=sum((v+(2048//sew)-1)//(2048//sew) for v in counts)
                    chunks128=sum((v+(128//sew)-1)//(128//sew) for v in counts)
                    # Compare arithmetic dispatch only; memory and loop control are excluded.
                    timing.append({'span':span,'sew':sew,'nnz':len(entries),'scalar_arithmetic':2*len(entries),'rvv_mul_reduce_arithmetic':2*chunks,'rvv_vlen128_arithmetic_context':2*chunks128,'custom_arithmetic':1,'cycles_1x1':len(one.motor.trace),'cycles_2x4':len(cpu.motor.trace),'local_data_words':2*len(entries)+65+64+64,'local_data_bytes':(len(entries)+64)*(sew//8)+(len(entries)+65)*4+64*(min(2*sew,32)//8)})
            for name in ['FP8 E4M3','FP8 E5M2','FP16','FP32']:
                out='FP16' if name.startswith('FP8') else 'FP32'
                y=ieee_tree(entries,x,64,eval_spmv.FORMATOS[name],eval_spmv.FORMATOS[out])
                m=metrics(y,ref);data[name].extend(m)
                for row,(ab,re,bad,zm) in enumerate(m):raw.append([span,t,name,row,ab,re,bad,zm])
        results[str(span)]={name:summary(items) for name,items in data.items()}
        print('Cenario',span,results[str(span)],flush=True)
    p=Path('resultados');p.mkdir(exist_ok=True)
    (p/'benchmark_integrado.json').write_text(json.dumps({'trials':trials,'matrix_size':64,'density':.05,'results':results,'timing':timing},indent=2,allow_nan=False))
    with (p/'erros_integrados.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['span','trial','format','row','absolute_error','relative_error','nonfinite','zero_mismatch']);w.writerows(raw)
    with (p/'contagem_integrada.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timing[0]));w.writeheader();w.writerows(timing)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(10,3.5),sharey=True)
    for ax,span in zip(axes,(2,12,30)):
        for name in data:
            rows=[r for r in raw if r[0]==span and r[2]==name and r[5] is not None]
            vals=sorted(max(r[5],1e-16) for r in rows if math.isfinite(r[5]))
            ax.plot(vals,[(i+1)/len(rows) for i in range(len(vals))],label=name)
        ax.set(xscale='log',xlim=(1e-10,1e3),ylim=(0,1.02),title='Range $10^{%d}$'%span,xlabel='Raw relative error');ax.grid(alpha=.2)
    axes[0].set_ylabel('Fraction of nonzero-reference outputs')
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=4,loc='lower center',fontsize=8)
    fig.tight_layout(rect=[0,.14,1,1]);Path('figuras').mkdir(exist_ok=True);fig.savefig('figuras/erro_integrado.png',dpi=180);plt.close(fig)
    print('OK: benchmark integrado concluido')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--matrizes',type=int,default=30);args=a.parse_args()
    if args.matrizes<1:a.error('matrizes deve ser >=1')
    with np.errstate(all='ignore'):run(args.matrizes)
