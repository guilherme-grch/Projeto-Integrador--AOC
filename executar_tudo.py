"""Executor unico. Qualquer falha interrompe a aprovacao final (exit 1)."""
from pathlib import Path
import argparse,subprocess,sys,json,platform,hashlib,time,py_compile,os

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--rapido',action='store_true');parser.add_argument('--matrizes',type=int,default=30);parser.add_argument('--historico',action='store_true',help='inclui experimentos antigos auxiliares');a=parser.parse_args()
    if a.matrizes<1:parser.error('--matrizes deve ser positivo')
    root=Path(__file__).resolve().parent;out=root/'resultados';out.mkdir(exist_ok=True)
    for source in root.glob('*.py'): py_compile.compile(str(source), doraise=True)
    tests=['test_binary128.py','test_takum.py','test_zvtakum.py','test_analises.py','test_benchmark.py','test_paralelo.py']
    jobs=[[x] for x in tests]+[['demo_paralelo.py'],['demo_zvtakum.py'],['terminal_takum.py','3.14']]
    if not a.rapido:jobs += [['analise_csr.py'],['benchmark_integrado.py','--matrizes',str(a.matrizes)]]
    if a.historico and not a.rapido:jobs += [['eval_spmv.py'],['analise_erro.py',str(a.matrizes)],['eval_acumulador.py',str(a.matrizes)],['contagem_instrucoes.py']]
    results=[]
    for job in jobs:
        print('Executando',' '.join(job),flush=True);start=time.perf_counter()
        try:
            p=subprocess.run([sys.executable]+job,cwd=root,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},capture_output=True,timeout=900)
            code=p.returncode;text=p.stdout+p.stderr
        except subprocess.TimeoutExpired:
            code=1;text='Timeout (900 segundos)'
        (out/(job[0]+'.txt')).write_text(text,encoding='utf-8')
        results.append({'command':job,'exit_code':code,'seconds':round(time.perf_counter()-start,3)})
        print('OK' if code==0 else 'FALHA',flush=True)
    report={'python':sys.version,'platform':platform.platform(),'mode':'quick' if a.rapido else ('full_with_history' if a.historico else 'full'), 'syntax_compilation':'PASS','matrices_per_scenario':a.matrizes,'jobs':results,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))}}
    (out/('validacao_rapida.json' if a.rapido else ('validacao_historica.json' if a.historico else 'validacao_completa.json'))).write_text(json.dumps(report,indent=2))
    if any(r['exit_code'] for r in results):sys.exit(1)
    print('RESULTADO: todas as %d etapas passaram.'%len(results))
if __name__=='__main__':main()
