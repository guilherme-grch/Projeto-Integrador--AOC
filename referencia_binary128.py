"""Referencia finita binary128: RNE, 113 bits e underflow gradual.

Fractions preservam exatamente cada operacao antes do arredondamento.
O benchmark usa entradas finitas. Overflow devolve +/-inf; zero e
representado por Fraction(0), sem preservar o sinal de zero IEEE.
Nao implementa flags, payloads NaN ou modos de arredondamento alternativos.
"""
from fractions import Fraction
import math

PRECISION = 113
EMIN = -16382
EMAX = 16383
MIN_SUBNORMAL = Fraction(2) ** (EMIN - PRECISION + 1)
MIN_NORMAL = Fraction(2) ** EMIN
MAX_FINITE = (2 - Fraction(2) ** (1 - PRECISION)) * Fraction(2) ** EMAX


def round_binary128(value):
    """Arredonda um racional exato para o conjunto finito binary128 (RNE)."""
    f = Fraction(value)
    if not f:
        return Fraction(0)
    magnitude = abs(f)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length()
    if Fraction(2) ** exponent > magnitude:
        exponent -= 1
    # Subnormais compartilham o passo minimo; normais tem 113 bits.
    step = Fraction(2) ** max(exponent - PRECISION + 1, EMIN - PRECISION + 1)
    rounded = round(f / step) * step
    if abs(rounded) > MAX_FINITE:
        return -math.inf if f < 0 else math.inf
    return rounded


def spmv_binary128(entries, x, nrows):
    """Produto separado e soma sequencial, ambos RNE; entradas finitas."""
    y = [Fraction(0) for _ in range(nrows)]
    vector = [Fraction(v) for v in x]
    for i, j, value in entries:
        product = round_binary128(Fraction(value) * vector[j])
        if not isinstance(product, Fraction):
            raise OverflowError('produto fora da faixa finita binary128')
        total = round_binary128(y[i] + product)
        if not isinstance(total, Fraction):
            raise OverflowError('soma fora da faixa finita binary128')
        y[i] = total
    return y
