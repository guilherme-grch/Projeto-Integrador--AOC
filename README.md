# Takum na Extensão Vetorial RISC-V (RVV)

Projeto Integrador de AOC – UFMG, semestre 2026/02.

## Integrantes
- André
- Arthur
- Caio
- Guilherme Gonçalves Rocha
- Julia

## O que há aqui
Simulador funcional em Python do formato aritmético Takum (T8, T16, T32):
decodificação, codificação e operações (add, sub, mul, div, fma, conversão).

## Decisões de projeto
- Formato: takum **logarítmico** (Definição 2 de Hunhold, 2024).
- Linguagem: Python 3, simulador funcional (não RTL).
- Aritmética: decodifica → opera em float64 → codifica com arredondamento.

## Como rodar
    python3 test_takum.py

## Estrutura
- `takum.py` – codec e operações
- `test_takum.py` – testes
- `docs/design_log.md` – registro do processo

## Referências
1. L. Hunhold, "Streamlining SIMD ISA extensions with takum arithmetic...", MOCAST 2025.
2. L. Hunhold, "Beating Posits at Their Own Game: Takum Arithmetic", 2024.
