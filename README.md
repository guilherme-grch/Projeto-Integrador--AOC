# Projeto Takum na Extensão Vetorial RISC-V (RVV)

**Projeto Integrador de Arquitetura e Organização de Computadores — UFMG, 2026/02**

## 1. Objetivo

Este projeto implementa e avalia, em Python, uma proposta de extensão vetorial para executar operações com o formato numérico Takum. O pacote contém o modelo funcional do formato Takum, a proposta de instruções Zvtakum, um simulador por instruções/ciclos, testes automatizados, demonstrações e experimentos de avaliação.

**Escopo importante:** trata-se de um simulador/modelo funcional em Python. Não é uma implementação RTL sintetizável, não é um núcleo RISC-V completo e não representa temporização física de hardware. Os ciclos apresentados são ciclos modelados pelo simulador.

## 2. Organização do trabalho

O projeto está organizado em três frentes, alinhadas às etapas do trabalho:

- **Fase 1 — Formato Takum:** codificação, decodificação, representação numérica e operações aritméticas nas larguras implementadas (T8, T16 e T32).
- **Fase 2 — Extensão vetorial Zvtakum:** codificação e decodificação de instruções, registradores vetoriais e execução no processador simulado.
- **Fase 3 — Avaliação:** experimentos com multiplicação de matriz esparsa por vetor (SpMV), comparação numérica com referências de maior precisão, contagem de instruções e análise de CSRs/estado.

## 3. Instruções modeladas

A proposta inclui as seguintes instruções vetoriais:

| Instrução | Operação |
|---|---|
| `vtadd.vv` | Soma elemento a elemento de dois vetores Takum. |
| `vtsub.vv` | Subtração elemento a elemento. |
| `vtmul.vv` | Multiplicação elemento a elemento. |
| `vtdot.vv` | Produto escalar de vetores, com acumulação conforme o modelo implementado. |
| `vncvt.t.t` | Conversão entre larguras Takum, com redução de largura. |
| `vtspmv.v` | Extensão adicional demonstrada para a operação SpMV no simulador. |

As instruções propostas usam o espaço de opcode customizado `custom-2` (`0x5B`) no modelo. Isso representa uma escolha de codificação da proposta, não uma extensão padronizada oficialmente pelo RISC-V International.

## 4. Requisitos

- Python **3.10 ou superior**.
- Dependências instaladas a partir de `requirements.txt`:
  - NumPy
  - mpmath
  - Matplotlib

Não é necessário instalar GCC para executar os testes e demonstrações principais. O script `validar_quad_gcc.py` é opcional e depende de GCC com suporte à biblioteca `libquadmath`.

## 5. Como executar

Abra um terminal na pasta `AOC_Takum_Final` (a pasta que contém este README e `executar_tudo.py`). Recomenda-se criar um ambiente virtual para manter as dependências isoladas.

### Linux / macOS

```bash
# 1. Criar o ambiente virtual
python3 -m venv .venv

# 2. Instalar as dependências
.venv/bin/python -m pip install -r requirements.txt

# 3. Executar a validação rápida (9 etapas)
.venv/bin/python executar_tudo.py --rapido

# 4. Executar as demonstrações separadamente
.venv/bin/python demo_paralelo.py
.venv/bin/python demo_zvtakum.py

# 5. Executar a validação completa (11 etapas)
.venv/bin/python executar_tudo.py
```

### Windows (PowerShell ou CMD)

```powershell
# 1. Criar o ambiente virtual
py -3 -m venv .venv

# 2. Instalar as dependências
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Executar a validação rápida (9 etapas)
.\.venv\Scripts\python.exe executar_tudo.py --rapido

# 4. Executar as demonstrações separadamente
.\.venv\Scripts\python.exe demo_paralelo.py
.\.venv\Scripts\python.exe demo_zvtakum.py

# 5. Executar a validação completa (11 etapas)
.\.venv\Scripts\python.exe executar_tudo.py
```

Se `py -3` não estiver disponível no Windows, mas `python --version` funcionar, use `python -m venv .venv` para criar o ambiente. Depois, mantenha os demais comandos.

### O que os validadores executam

- `executar_tudo.py --rapido`: compila os arquivos Python e executa seis módulos de teste, duas demonstrações e uma chamada de teste do terminal Takum — total de **9 etapas**.
- `executar_tudo.py`: executa as mesmas nove etapas e acrescenta a análise de CSRs e o benchmark integrado com 30 matrizes por cenário — total de **11 etapas**.

O processo grava os relatórios JSON e os logs de execução na pasta `resultados/`. A execução completa pode levar alguns minutos. O programa termina com código de erro se alguma etapa falhar.

## 6. Demonstrações

### Demonstração das instruções Zvtakum

```bash
.venv/bin/python demo_zvtakum.py   # Linux/macOS
```

No Windows, use o interpretador do ambiente virtual conforme os comandos da seção anterior. A demonstração apresenta montagem de instruções em palavras de 32 bits, decodificação, execução de operações vetoriais e conversão de largura T32 para T16.

### Demonstração paralela / SpMV

```bash
.venv/bin/python demo_paralelo.py  # Linux/macOS
```

A demonstração executa a instrução modelada `vtspmv.v`, apresenta os estágios/ciclos simulados e verifica o resultado calculado. Também gera rastros em CSV, JSON e VCD e uma figura em `figuras/trace_paralelo.png`. Esses ciclos são do modelo, não medições de temporização física.

## 7. Arquivos do projeto

| Arquivo/pasta | Finalidade |
|---|---|
| `takum.py` | Núcleo do formato Takum: representação, codificação, decodificação e operações. |
| `zvtakum.py` | Codificação/decodificação das instruções e processador vetorial simulado. |
| `zvtakum_legacy.py` | Implementação legada mantida como referência auxiliar. |
| `modelo_paralelo.py` | Modelo de execução paralela usado nas demonstrações/avaliações. |
| `referencia_binary128.py` | Rotinas de referência de maior precisão usadas na avaliação. |
| `benchmark_integrado.py` | Benchmark integrado e comparação de resultados. |
| `analise_csr.py` | Análise relacionada a CSRs, estado e eventos especiais. |
| `eval_spmv.py` | Rotinas auxiliares de avaliação SpMV. |
| `eval_acumulador.py` | Experimento auxiliar com acumulador ampliado. |
| `analise_erro.py` | Análise da distribuição de erros. |
| `contagem_instrucoes.py` | Comparação/contagem de instruções. |
| `demo_zvtakum.py` | Demonstração das instruções Zvtakum. |
| `demo_paralelo.py` | Demonstração paralela e geração dos rastros. |
| `terminal_takum.py` | Terminal interativo para conversão/consulta de valores Takum. |
| `executar_tudo.py` | Executor das validações rápida e completa. |
| `test_*.py` | Módulos de testes automatizados. |
| `requirements.txt` | Dependências Python do projeto. |
| `resultados/` | Relatórios e rastros de execução incluídos/gerados. |
| `figuras/` | Figuras geradas pelas demonstrações. |
| `validacao/` | Código C opcional para validação com `libquadmath`. |

## 8. Resultados de validação desta entrega

Durante o teste de execução desta versão no ambiente Linux com Python 3.10.12, foram observados os seguintes resultados:

- A validação rápida terminou com a mensagem **“todas as 9 etapas passaram”**.
- `demo_paralelo.py` concluiu com sucesso, confirmou o vetor de saída esperado `[10, 2, 5, 0]` dentro da tolerância usada pelo próprio script e gerou os rastros CSV, JSON e VCD e a figura.
- `demo_zvtakum.py` executou as demonstrações de soma, subtração, multiplicação, produto escalar e conversão de largura; as quatro operações aritméticas exibidas coincidiram com os valores esperados.
- A validação completa terminou com a mensagem **“todas as 11 etapas passaram”**.

Esses resultados documentam a execução observada no ambiente de teste. A execução em outro computador pode variar conforme o sistema operacional e as versões das dependências.

## 9. Limitações e interpretação dos resultados

- O projeto é um simulador funcional em Python, não RTL sintetizável nem hardware físico.
- Os ciclos e o paralelismo apresentados são abstrações do modelo; não devem ser interpretados como frequência, latência física ou desempenho medido em silício.
- Os benchmarks dependem dos cenários, matrizes, parâmetros e formatos definidos nos scripts. As conclusões devem ser lidas dentro dessas condições experimentais.
- A proposta de instruções e o uso de opcode customizado são parte do projeto acadêmico; não significam que as instruções façam parte da especificação oficial do RVV.
- A análise de CSRs descreve as escolhas e simplificações adotadas pelo modelo Zvtakum. A ausência de um mecanismo de estado/flags no modelo não significa que eventos numéricos como overflow deixem de ocorrer; é necessário considerar a política de tratamento descrita na implementação.

## 10. Observação sobre os arquivos de resultados

Os arquivos em `resultados/` podem ser atualizados quando os scripts são executados. Para reproduzir os experimentos, execute os comandos a partir da pasta do projeto. A pasta `.venv/` é criada localmente e não precisa ser incluída na entrega.

---

**Projeto Integrador de AOC — UFMG — 2026/02**
