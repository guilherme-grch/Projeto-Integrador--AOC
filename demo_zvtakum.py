"""
demo_zvtakum.py - Demonstracao ponta a ponta da extensao Zvtakum (Fase 2).

Mostra o ciclo completo:
    assembly em texto -> palavra de 32 bits -> decodificacao -> execucao

Rodar com:  python3 demo_zvtakum.py
"""

import zvtakum
import takum

print("=" * 66)
print("DEMONSTRACAO DA EXTENSAO VETORIAL Zvtakum")
print("=" * 66)

# ---------------------------------------------------------------------------
print()
print("PASSO 1 - Montagem: assembly vira palavra de 32 bits")
print("-" * 66)
programa = [
    "vtadd.vv v3, v1, v2",
    "vtsub.vv v4, v1, v2",
    "vtmul.vv v5, v1, v2",
    "vtdot.vv v6, v1, v2",
]
palavras = []
for linha in programa:
    w = zvtakum.montar(linha)
    palavras.append(w)
    print(f"  {linha:<24} -> 0x{w:08X}  ({format(w, '032b')})")

# ---------------------------------------------------------------------------
print()
print("PASSO 2 - Decodificacao: o processador le os bits de volta")
print("-" * 66)
print(f"  {'palavra':<12} {'funct6':<9} {'vd':<5} {'vs1':<5} {'vs2':<5} instrucao")
for w in palavras:
    i = zvtakum.decode_instr(w)
    f6 = format((w >> 26) & 0b111111, "06b")
    print(f"  0x{w:08X}   {f6}    v{i['vd']:<4} v{i['vs1']:<4} v{i['vs2']:<4} "
          f"{zvtakum.desmontar(w)}")

# ---------------------------------------------------------------------------
print()
print("PASSO 3 - Execucao no processador simulado")
print("-" * 66)

cpu = zvtakum.ProcessadorZvtakum(vlen=128)

A = [1.5, 2.0, 3.5, 4.0]
B = [2.0, 0.5, 2.0, 3.0]

vl = cpu.vsetvli(len(A), sew=32)   # T32, 4 elementos
print(f"  vsetvli: VLEN=128 bits, SEW=32 (T32) -> VLMAX={128//32}, VL={vl}")

cpu.carregar(1, A)
cpu.carregar(2, B)
print(f"  v1 = {A}")
print(f"  v2 = {B}")
print()

esperados = {
    "vtadd.vv": [a + b for a, b in zip(A, B)],
    "vtsub.vv": [a - b for a, b in zip(A, B)],
    "vtmul.vv": [a * b for a, b in zip(A, B)],
    "vtdot.vv": [sum(a * b for a, b in zip(A, B))],
}

for linha, w in zip(programa, palavras):
    i = zvtakum.decode_instr(w)
    cpu.executar(w)
    sew_saida = 32 if i["nome"] != "vtdot.vv" else 32
    obtido = cpu.ler(i["vd"], sew_saida)
    esp = esperados[i["nome"]]
    ok = all(abs(o - e) <= 1e-6 * max(1.0, abs(e)) for o, e in zip(obtido, esp))
    marca = "OK" if ok else "DIVERGE"
    print(f"  {linha}")
    print(f"      resultado : {[round(x, 6) for x in obtido]}")
    print(f"      esperado  : {[round(x, 6) for x in esp]}   [{marca}]")

# ---------------------------------------------------------------------------
print()
print("PASSO 4 - Conversao de largura (vncvt.t.t): T32 -> T16")
print("-" * 66)
cpu.carregar(1, [3.14159265, 100.0, 0.001, 42.0])
w = zvtakum.montar("vncvt.t.t v7, v1")
print(f"  vncvt.t.t v7, v1        -> 0x{w:08X}")
cpu.executar(w, sew_destino=16)
antes = cpu.ler(1, 32)
depois = cpu.ler(7, 16)
print(f"  {'valor':>14}  {'T32':>14}  {'T16':>14}  {'erro rel':>10}")
for a, d in zip(antes, depois):
    err = abs((d - a) / a) if a != 0 else 0.0
    print(f"  {a:>14.6f}  {a:>14.6f}  {d:>14.6f}  {err:>10.2e}")

# ---------------------------------------------------------------------------
print()
print("PASSO 5 - Contagem de instrucoes (dado para a Fase 3)")
print("-" * 66)
print(f"  instrucoes executadas nesta demo: {cpu.contador_instr}")
print()
print("  Comparacao conceitual para o artigo:")
print("    - Sem extensao vetorial: seriam necessarias ~VL instrucoes")
print("      escalares por operacao (4 somas = 4 instrucoes).")
print("    - Com Zvtakum: 1 instrucao processa os 4 elementos de uma vez.")
print(f"    - Reducao neste exemplo: {vl}x por operacao aritmetica.")

print()
print("=" * 66)
print("FIM DA DEMONSTRACAO")
print("=" * 66)
