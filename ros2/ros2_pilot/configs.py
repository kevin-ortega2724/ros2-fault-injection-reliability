"""Arquitecturas del piloto ROS 2 y lógica de función (fuente única para predicción y ejecución)."""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Comp:
    inputs: Tuple[str, ...]
    k: int = 1
    is_link: bool = False


SOURCE = 'src'
SINK = 'mon'


def _c(*inputs, k=1, link=False):
    return Comp(tuple(inputs), k, link)


CONFIGS: Dict[str, Dict[str, Comp]] = {
    'cen': {'s1': _c('src'), 's2': _c('src'), 'p': _c('s1', 's2'),
            'a1': _c('p'), 'a2': _c('p'), 'mon': _c('a1', 'a2')},
    'r2oo3': {'c1': _c('src'), 'c2': _c('src'), 'c3': _c('src'),
              'v': _c('c1', 'c2', 'c3', k=2), 'mon': _c('v')},
    'd_series': {'p1': _c('src'), 'l12': _c('p1', link=True),
                 'p2': _c('l12'), 'mon': _c('p2')},
    'd_parallel': {'p1': _c('src'), 'la': _c('p1', link=True), 'lb': _c('p1', link=True),
                   'p2': _c('la', 'lb'), 'mon': _c('p2')},
    'd_triangle': {'p1': _c('src'), 'l13': _c('p1', link=True), 'l12': _c('p1', link=True),
                   'p2': _c('l12'), 'l23': _c('p2', link=True),
                   'p3': _c('l13', 'l23'), 'mon': _c('p3')},
    'd_units': {'t': _c('src', link=True), 'p1': _c('t'), 'p2': _c('t'), 'p3': _c('t'),
                'mon': _c('p1', 'p2', 'p3')},
}


def failing(config: Dict[str, Comp]) -> List[str]:
    """Componentes que reciben fallas: todos menos fuente y monitor."""
    return [n for n in config if n != SINK]


def function_up(config: Dict[str, Comp], up: Dict[str, bool]) -> bool:
    """Propaga la señal desde la fuente; las entradas siempre preceden al nodo en el dict."""
    live = {SOURCE: True}
    for name, comp in config.items():
        n_live = sum(live.get(i, False) for i in comp.inputs)
        live[name] = up.get(name, True) and n_live >= comp.k
    return live[SINK]
