"""Casos de fronteira da referencia e contratos de entrada adicionais."""
import math
import unittest
from fractions import Fraction as F
from referencia_binary128 import round_binary128 as q, MIN_NORMAL, MIN_SUBNORMAL, MAX_FINITE
from zvtakum import encode_instr
from benchmark_integrado import metrics

class TestBinary128(unittest.TestCase):
    def test_ties_normal(self):
        ulp = F(2)**-112
        for sign in (-1, 1):
            self.assertEqual(q(sign*(1+ulp/2)), sign)
            self.assertEqual(q(sign*(1+3*ulp/2)), sign*(1+2*ulp))

    def test_subnormal_and_underflow(self):
        u=MIN_SUBNORMAL
        for sign in (-1,1):
            self.assertEqual(q(sign*u/2),0)
            self.assertEqual(q(sign*3*u/2),sign*2*u)
            self.assertEqual(q(sign*u),sign*u)

    def test_normal_transition(self):
        self.assertEqual(q(MIN_NORMAL-MIN_SUBNORMAL), MIN_NORMAL-MIN_SUBNORMAL)
        self.assertEqual(q(MIN_NORMAL-MIN_SUBNORMAL/2), MIN_NORMAL)

    def test_overflow(self):
        half_ulp=F(2)**(16383-113)
        self.assertEqual(q(MAX_FINITE),MAX_FINITE)
        self.assertEqual(q(MAX_FINITE+half_ulp/2),MAX_FINITE)
        self.assertEqual(q(MAX_FINITE+half_ulp),math.inf)
        self.assertEqual(q(-MAX_FINITE-half_ulp),-math.inf)

    def test_exact_and_cancellation(self):
        for v in (0,1,-1,F(2)**-10000,F(2)**10000): self.assertEqual(q(v),v)
        self.assertEqual(q(q(F(1,3))-q(F(1,3))),0)

    def test_input_contract(self):
        for reg in (1.0,True,-1,32):
            with self.assertRaises(ValueError): encode_instr('vtadd.vv',reg,1,2)
        with self.assertRaises(ValueError): metrics([1],[])

if __name__=='__main__': unittest.main(verbosity=2)
