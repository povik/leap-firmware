import math
from functools import reduce

class Polynomial:
    def __init__(self, v=None, factorized=False):
        if type(v) is Polynomial:
            self.factorized = v.factorized
            self._coeffs = v._coeffs
            self._factors = v._factors
            return
        elif type(v) is None:
            self.factorized = False
            self._coeffs = []
            self._factors = []
        elif factorized:
            self.factorized = True
            self._factors = list(v)
            for f in self._factors:
                assert not f.factorized
            self._coeffs = []
        else:
            self.factorized = False
            self._factors = []
            self._coeffs = list(v)

    def __hash__(self):
        raise NotImplementedError()

    @classmethod
    def from_factors(self, factors):
        return Polynomial(factors, factorized=True)

    @classmethod
    def sum_coeffs(self, a, b):
        tl = max(len(a), len(b))
        a = a + [0.0] * (tl - len(a))
        b = b + [0.0] * (tl - len(b))
        return [ae + be for ae, be in zip(a, b)]

    @classmethod
    def mul_coeffs(self, a, b):
        return reduce(self.sum_coeffs, [
            ([0.0] * i) + [av * bv for av in a]
            for i, bv in enumerate(b)
        ])

    @classmethod
    def common_factors(self, a, b):
        a_factors = list(a.factors)
        b_factors = []
        common = []
        for f in list(b.factors):
            if f in a_factors:
                a_factors.remove(f)
                common.append(f)
            else:
                b_factors.append(f)
        return Polynomial.from_factors(common), Polynomial.from_factors(a_factors), \
                Polynomial.from_factors(b_factors)

    def __mul__(self, other):
        return Polynomial(self.factors + other.factors, factorized=True)

    def __add__(self, other):
        common, a, b = Polynomial.common_factors(self, other)
        return common * Polynomial(self.sum_coeffs(a.coeffs, b.coeffs))

    @property
    def factors(self):
        if not self.factorized:
            return [self]
        else:
            return self._factors

    def expand(self):
        assert self.factorized
        self._coeffs = reduce(self.mul_coeffs, [
            f.coeffs for f in self._factors
        ])
        self.factorized = False

    def factorize(self):
        assert not self.factorized
        raise NotImplementedError()

    def expanded(self):
        ret = Polynomial(self)
        ret.expand()
        return ret

    def factorized(self):
        ret = Polynomial(self)
        ret.factorize()
        return ret

    def __pow__(self, n):
        return Polynomial(self.factors * n, factorized=True)

    @property
    def coeffs(self):
        if self.factorized:
            return self.expanded()._coeffs
        else:
            return self._coeffs

    @property
    def zeroes(self):
        if self.factorized:
            return self._zeroes
        else:
            return self.factorized()._zeroes

    def __call__(self, x):
        return sum([
            coeff * x**power
            for power, coeff in reversed(list(enumerate(self.coeffs)))
        ])

    def __str__(self):
        terms = [
            f"{coeff:.4E}*x^{power}"
            for power, coeff in reversed(list(enumerate(self.coeffs)))
        ]
        if not len(terms):
            return "0"
        return " + ".join(terms)

    def __repr__(self):
        return str(self)

class Rational:
    def __init__(self, p=[], q=[]):
        if type(p) is Rational:
            p, q = p.p, p.q
        self.p, self.q = Polynomial(p), Polynomial(q)

    def __str__(self):
        p_str, q_str = str(self.p), str(self.q)
        divider = "-" * max(len(p_str), len(q_str))
        return f"{p_str.center(len(divider))}\n{divider}\n{q_str.center(len(divider))}"

    def __repr__(self):
        return str(self)

    def __pow__(self, n):
        return Rational(self.p**n, self.q**n)

    @classmethod
    def cast(self, val):
        if type(val) in [int, float, complex]:
            return Rational([val], [1.0])
        elif type(val) is Rational:
            return val
        else:
            raise NotImplementedError(type(val))

    def __add__(self, b):
        a, b = Rational(self), Rational(self.cast(b))
        common_p, a_p, b_p = Polynomial.common_factors(a.p, b.p)
        common_q, a_q, b_q = Polynomial.common_factors(a.q, b.q)
        return Rational(common_p * (a_p * b_q + b_p * a_q),
                        common_q * a_q * b_q)

    def __mul__(self, b):
        a, b = Rational(self), Rational(self.cast(b))
        _, a_p, b_q = Polynomial.common_factors(a.p, b.q)
        _, a_q, b_p = Polynomial.common_factors(a.q, b.p)
        return Rational(a_p * b_p, a_q * b_q)

    @property
    def inv(self):
        return Rational(self.q, self.p)

    def __truediv__(self, b):
        return self * self.cast(b).inv

    def __rtruediv__(self, b):
        return self.cast(b) * self.inv

    __rmul__ = __mul__
    __radd__ = __add__

    def __call__(self, x):
        return self.p(x) / self.q(x)

x = Rational([0.0, 1.0], [1.0])

def Bn(n):
    return Polynomial(
        [Polynomial([1, -2 * math.cos((2*k + n - 1)*math.pi / 2 / n), 1])
         for k in range(1, n // 2 + 1)] + ([Polynomial([1, 1])] if n % 2 == 1 else []),
        factorized=True,
    )

def butter(n):
    return Rational([1.0], Bn(n))
