# Takum na Extensão Vetorial RISC-V (RVV): Zvtakum

Projeto Integrador de AOC – DELT/UFMG, semestre 2026/02.

## Integrantes

* André Nunes Fernandes
* Guilherme Gonçalves Rocha
* Márcio Arthur Machado de Oliveira

## O que é este projeto

O Takum é um formato numérico logarítmico de precisão cônica (Hunhold, 2024) que usa **uma única regra de decodificação para todas as larguras** (T8, T16, T32, T64) e tem só **dois valores especiais**: zero e NaR (*Not a Real*).

Aqui propomos e avaliamos o **Zvtakum**, uma extensão vetorial simplificada do RISC-V para Takum, com um **simulador funcional em Python** (não é RTL):

1. **Fase 1:** codec Takum (decodificação, codificação) e operações (add, sub, mul, div, fma, conversão).
2. **Fase 2:** extensão Zvtakum com 5 instruções, montador/desmontador e processador vetorial simulado.
3. **Fase 3:** avaliação experimental em SpMV (`y = A·x`) contra FP8/FP16/FP32, erro contra Float128, contagem de instruções e CSRs.

## Decisões de projeto

* **Formato:** takum logarítmico (Definição 2 de Hunhold, 2024): `valor = (−1)^S · √e^ℓ`, `ℓ = (−1)^S (c + m)`.
* **Layout:** `S | D | RRR | C (r bits) | M (p bits)`, com `p = n − r − 5`.
* **Aritmética:** modelo funcional: decodifica → opera em float64 → codifica com arredondamento. A tabela do logaritmo de Gauss (necessária para somar em hardware) **não** é implementada.
* **Arredondamento:** sobre o padrão de bits em complemento de dois (arredondar o padrão = arredondar o número); empates para cima; resultado não nulo nunca vira zero; overflow satura; NaR nunca é produzido por arredondamento.
* **Zvtakum:** opcode `custom-2` (`0x5B`), `funct3 = 0b100`; elementos de 8, 16 e 32 bits (como o SEW do RVV). Sem CSRs novos (0 bits), ao custo de saturação silenciosa.

### Instruções do Zvtakum

| Instrução | funct6 | Análogo no RVV | O que faz |
|---|---|---|---|
| `vtadd.vv`  | `000000` | `vfadd.vv`  | soma vetorial |
| `vtsub.vv`  | `000010` | `vfsub.vv`  | subtração vetorial |
| `vtmul.vv`  | `100100` | `vfmul.vv`  | multiplicação vetorial |
| `vtdot.vv`  | `111000` | `vfdot.*`   | produto escalar, acumulando em precisão 2n (T8→T16, T16→T32) |
| `vncvt.t.t` | `010010` | `vfncvt.*`  | conversão com redução de largura |

## Como rodar

Requisitos: Python 3.10+, `numpy`, `matplotlib` e `mpmath` (`pip install -r requirements.txt`). O `python-pptx` só é preciso para regenerar os slides.

```bash
# Tudo de uma vez (testes + demo + benchmarks). Sai com código 1 se algo falhar.
python3 executar_tudo.py

# Só os testes (rápido)
python3 executar_tudo.py --rapido

# Cada parte separada
python3 test_takum.py          # Fase 1: 123 testes
python3 test_zvtakum.py        # Fase 2: 68 testes
python3 test_analises.py       # Fase 3: 68 testes
python3 test_benchmark.py      # Fase 3: 22 testes (régua IEEE do benchmark)
python3 demo_zvtakum.py        # demonstração das 5 instruções
```

As saídas completas ficam em `resultados/`.

### Terminal interativo

Converte entre decimal e Takum (aceita `3.14`, `3,14`, `1/3`, `pi`, `1e-30`, `0x4D27`, `0b…`, contas como `1.5 * 2`):

```bash
python3 takum_terminal.py            # modo interativo (padrão T16)
python3 takum_terminal.py 3.14       # 3.14 em T16 = 0x4D27
python3 takum_terminal.py -n 8 3.14  # em T8
```

Comandos no modo interativo: `n 8` / `t16` (muda a largura), `faixa`, `tabela`, `ajuda`, `sair`.

### Avaliação (Fase 3)

```bash
python3 eval_spmv.py             # SpMV: erro e overflow, Takum vs IEEE 754
python3 eval_acumulador.py        # SpMV com acumulador largo (estilo vtdot.vv)
python3 analise_erro.py          # distribuição do erro vs Float128 (30 matrizes/cenário)
python3 contagem_instrucoes.py   # instruções: escalar vs RVV IEEE vs Zvtakum
python3 analise_csr.py           # classes especiais, padrões desperdiçados, eventos de exceção
python3 grafico_instrucoes.py    # figura de instruções
python3 gerar_slides.py          # slides (precisa de python-pptx)
```

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `takum.py` | codec Takum e operações (núcleo, Fase 1) |
| `test_takum.py` | 123 testes (inclui referência independente em mpmath e conferência com a libtakum oficial) |
| `zvtakum.py` | codificação das instruções, montador, desmontador, processador simulado (Fase 2) |
| `test_zvtakum.py` | 68 testes do simulador |
| `demo_zvtakum.py` | demonstração com 4 verificações |
| `takum_terminal.py` | conversor/calculadora interativo |
| `eval_spmv.py` | benchmark SpMV (Fase 3); FP8 conforme OFP8, erro contra referência exata |
| `eval_acumulador.py` | mesmo benchmark com acumulador ampliado |
| `test_benchmark.py` | 22 testes: FP16 vs numpy, FP8 vs tabela dos 256 padrões, estouro, erro relativo |
| `analise_erro.py` | distribuição do erro contra Float128 emulado |
| `contagem_instrucoes.py` | contagem de instruções no simulador |
| `analise_csr.py` | CSRs, exceções e simplicidade do formato |
| `grafico_instrucoes.py` | gráfico de instruções |
| `test_analises.py` | 68 testes das análises |
| `executar_tudo.py` | executa tudo e resume (script de teste automático) |
| `requirements.txt` | dependências |
| `artigo/` | artigo IEEE (`main.tex` em inglês, `main_pt.tex` em português, `figuras/`, `gerar_graficos.py`) |
| `Slides-Apresentacao-Takum.pptx` | slides |

## Resultados principais

* **Faixa dinâmica:** T8 cobre 104 ordens de grandeza e T16/T32 cobrem 111, contra ~5 (FP8 E4M3), ~10 (E5M2), ~12 (FP16) e ~83 (FP32).
* **Faixa estreita (10²):** o IEEE 754 é mais preciso em 8 e 16 bits (E4M3 ≈ 1,9× melhor que T8; FP16 ≈ 1,6× melhor que T16). Em 32 bits o T32 é ≈ 6,7× melhor.
* **Faixa larga (10¹² a 10³⁰):** o Takum tem **0% de overflow**; FP8/FP16 estouram em até 78% das saídas. Em 10³⁰, T16 tem erro mediano de ≈ 0,17%, cerca de 590× menor que o FP16 (saturado em 100%).
* **Instruções (SpMV 64×64):** de 2,5× a 8,3× menos que o laço escalar; só 1,2–1,3× menos que RVV IEEE de mesma largura, e na matriz densa com 32 bits o Zvtakum é ≈ 7% pior, porque `vtdot.vv` não recebe acumulador (recomendação: somar `vs1[0]`).
* **Acumulador largo (`vtdot.vv`):** acumular em 2n melhora todos os formatos só 1,0–1,7× e não elimina o estouro das entradas (em 10¹², E4M3 ainda estoura em 61,8% e FP16 em 27,5%; Takum 0%).
* **CSRs:** o IEEE usa 8 bits de `fcsr` (modo de arredondamento + 5 flags); o Zvtakum usa 0 bits, ao custo de saturação silenciosa.

O Takum **não vence sempre**: em faixa dinâmica estreita e com 8/16 bits, o IEEE 754 tem erro menor.

## Validação

* **123 + 68 + 68 + 22 testes automáticos**, incluindo enumeração exaustiva dos 256 padrões de T8 e a conferência com as propriedades do artigo original (layout, extensão com zeros, negação, zero único, decodificação nos 12 bits mais significativos), decodificador independente em mpmath e NaR/zero em todas as operações. O benchmark também é testado: FP16 emulado = `np.float16`, FP8 = tabela dos 256 padrões.
* **Conferência com a implementação de referência (libtakum, C):** o codificador coincide em 302.510 valores por largura (T8, T16, T32); o decodificador coincide bit a bit em T8 e T32 (T16 difere ≤ 7,4e‑15, e o nosso é mais próximo do valor exato).
* **Referência Float128:** o Python não tem binary128; emulamos com 113 bits de significando (`fractions.Fraction`), diferindo do resultado exato em ≤ 9,1e‑34.
* **Métrica sem viés de sobrevivência:** overflow conta como 100% de erro.

### Bugs encontrados e corrigidos

1. Largura de campo negativa na codificação em T8 → montagem em largura maior `W`.
2. Arredondamento duplo em T8 (~3% das entradas escolhiam o vizinho mais distante) → `W = 52` (depois 128, ver 3).
3. Resquício do arredondamento duplo em T32 (1 em 302.510 valores), achado ao comparar com a libtakum → `W = 128`.

## Limitações

* Modelo funcional, não RTL; sem a tabela do logaritmo de Gauss.
* Matrizes esparsas sintéticas (faixa dinâmica controlada), não da SuiteSparse.
* Razões em faixa estreita variam ~10% conforme a regra de desempate (o artigo original não define uma).
* As porcentagens de eventos de exceção usam operandos sorteados uniformemente sobre os padrões de bits; comparam formatos entre si e não são taxas de um programa real.
* Contagem de instruções simplificada (sem aritmética de endereços e controle de laço).

## Referências

1. L. Hunhold, "Beating Posits at Their Own Game: Takum Arithmetic," in *Next Generation Arithmetic*, Springer, 2024, pp. 1–51. DOI: [10.1007/978-3-031-72709-2_1](https://doi.org/10.1007/978-3-031-72709-2_1). Preprint: [arXiv:2404.18603](https://arxiv.org/abs/2404.18603).
2. L. Hunhold, "Streamlining SIMD ISA Extensions with Takum Arithmetic: A Case Study on Intel AVX10.2," *2025 14th International Conference on Modern Circuits and Systems Technologies (MOCAST)*, 2025, pp. 1–6. Preprint: [arXiv:2503.14067](https://arxiv.org/abs/2503.14067).
3. "Design and Implementation of a Takum Arithmetic Hardware Codec," [arXiv:2408.10594](https://arxiv.org/abs/2408.10594).
4. libtakum, implementação de referência de takum em ISO C99: <https://github.com/takum-arithmetic/libtakum>.
5. RISC-V International, "RISC-V 'V' Vector Extension Specification": <https://github.com/riscv/riscv-v-spec>.
6. Diretrizes do Projeto Integrador de AOC, DELT/UFMG, 2026/02.
