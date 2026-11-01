"""Predicciones CTMC exactas por enumeración de estados.

A: lógica estructural real del grafo.
B: regla usada en dataset_v2.0: cada enlace se trata como elemento en serie.
"""
import itertools
from typing import Dict

import numpy as np
from scipy.linalg import expm

from configs import Comp, failing, function_up


def _ok_fn(config, names, links_in_series):
    links = {n for n in names if config[n].is_link}

    def ok(state) -> bool:
        up = dict(zip(names, state))
        if links_in_series:
            if not all(up[n] for n in links):
                return False
            up = {n: True if n in links else v for n, v in up.items()}
        return function_up(config, up)
    return ok


def _rates(state, names, lam, mu, groups, beta):
    """Transiciones desde un estado; cada miembro operativo de un grupo dispara la causa común con tasa beta*lam."""
    member = {n: g for g in groups for n in g}
    out = []
    for j, n in enumerate(names):
        if not state[j]:
            out.append((state[:j] + (True,) + state[j + 1:], mu))
        elif n in member and beta:
            out.append((state[:j] + (False,) + state[j + 1:], (1 - beta) * lam))
            all_down = tuple(False if m in member[n] else s for m, s in zip(names, state))
            out.append((all_down, beta * lam))
        else:
            out.append((state[:j] + (False,) + state[j + 1:], lam))
    return out


def generator(config: Dict[str, Comp], lam: float, mu: float, links_in_series: bool = False, groups=(), beta: float = 0.0):
    """Generador entre estados operativos e índice del estado con todo operativo."""
    names = failing(config)
    ok = _ok_fn(config, names, links_in_series)
    transient = [s for s in itertools.product((True, False), repeat=len(names)) if ok(s)]
    index = {s: i for i, s in enumerate(transient)}
    Q = np.zeros((len(transient), len(transient)))
    for s, i in index.items():
        for t, rate in _rates(s, names, lam, mu, groups, beta):
            Q[i, i] -= rate
            if t in index:
                Q[i, index[t]] += rate
    return Q, index[tuple([True] * len(names))]


def availability(config: Dict[str, Comp], lam: float, mu: float, links_in_series: bool = False) -> float:
    """Fracción estacionaria del tiempo con la función disponible, con fallas y reparaciones continuas."""
    names = failing(config)
    ok = _ok_fn(config, names, links_in_series)
    p_up, total = mu / (lam + mu), 0.0
    for s in itertools.product((True, False), repeat=len(names)):
        if ok(s):
            total += np.prod([p_up if v else 1 - p_up for v in s])
    return float(total)


def mfpt(config: Dict[str, Comp], lam: float, mu: float, links_in_series: bool = False, groups=(), beta: float = 0.0) -> float:
    Q, start = generator(config, lam, mu, links_in_series, groups, beta)
    return float(np.linalg.solve(-Q, np.ones(len(Q)))[start])


def first_passage_cdf(config: Dict[str, Comp], lam: float, mu: float, times, links_in_series: bool = False):
    """Probabilidad de haber perdido la función en cada tiempo."""
    Q, start = generator(config, lam, mu, links_in_series)
    return np.array([1 - expm(Q * t)[start].sum() for t in times])
