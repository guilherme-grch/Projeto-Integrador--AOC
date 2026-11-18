"""Demo central: instrucao unica, ciclos e paralelismo. Gera JSON/CSV/VCD/PNG."""
from pathlib import Path
import json,csv,math
from zvtakum import ProcessadorZvtakum,montar

def main():
    A=[(0,0,1),(0,1,2),(0,2,3),(0,3,4),(1,0,-1),(1,1,2),(1,2,-3),(1,3,4),(2,2,5)]
    x=[1,1,1,1];expected=[10,2,5,0]
    c=ProcessadorZvtakum(128,4,2);c.vsetvli(4,32);c.carregar(1,x);c.carregar_matriz(2,A,4,4)
    word=montar('vtspmv.v v3,v1,v2');before=c.contador_instr
    c.iniciar(word)
    print('vtspmv.v v3,v1,v2 = 0x%08X'%word)
    while c.motor.busy:
        e=c.tick();print('ciclo %2d %-10s operacoes paralelas=%d'%(e['cycle'],e['stage'],len(e['operations'])))
    result=c.ler(3)
    assert len(result)==len(expected) and all(abs(a-b)<1e-5 for a,b in zip(result,expected))
    assert c.contador_instr-before==1
    print('Resultado:',result,'Esperado:',expected)
    print('Instrucoes aritmeticas: 1; ciclos modelados:',len(c.motor.trace))
    p=Path('resultados');p.mkdir(exist_ok=True)
    (p/'trace_spmv.json').write_text(json.dumps(c.motor.trace,indent=2))
    with (p/'trace_spmv.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['cycle','stage','bank','lane','row','element_or_pair'])
        for e in c.motor.trace:
            for o in e['operations'] or [{}]:w.writerow([e['cycle'],e['stage'],o.get('bank',''),o.get('lane',''),o.get('row',''),o.get('element',o.get('pair',''))])
    stages={s:i for i,s in enumerate(['issue','decode','multiply','reduce','encode','writeback'])}
    vcd=['$timescale 1ns $end','$scope module simulated_architecture $end','$var wire 1 ! busy $end','$var wire 1 " done $end','$var wire 3 # stage $end','$var wire 8 $ active_units $end','$upscope $end','$enddefinitions $end','#0','0!','0"','b000 #','b00000000 $']
    for e in c.motor.trace:
        vcd += ['#%d'%(e['cycle']*10),('0!' if e['stage']=='writeback' else '1!'),('1"' if e['stage']=='writeback' else '0"'),'b%03d #'%int(format(stages[e['stage']],'03b')),'b%s $'%format(len(e['operations']),'08b')]
    (p/'trace_spmv.vcd').write_text('\n'.join(vcd)+'\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,3.4))
    colors={'decode':'#1f77b4','multiply':'#d95f02','reduce':'#2ca02c','encode':'#9467bd'}
    for stage,color in colors.items():
        xs=[];ys=[]
        for e in c.motor.trace:
            if e['stage']==stage:
                for o in e['operations']:xs.append(e['cycle']);ys.append(o['bank']*4+o.get('lane',0))
        ax.scatter(xs,ys,label=stage,c=color,s=110,marker='s')
    ax.set(xlabel='Model cycle (not physical timing)',ylabel='Resource: bank x 4 + lane',yticks=range(8),xticks=range(1,len(c.motor.trace)+1))
    ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.22));ax.grid(alpha=.2)
    fig.tight_layout();Path('figuras').mkdir(exist_ok=True);fig.savefig('figuras/trace_paralelo.png',dpi=170);plt.close(fig)
    print('OK: demo paralela, CSV, JSON, VCD e figura gerados')
if __name__=='__main__':main()
