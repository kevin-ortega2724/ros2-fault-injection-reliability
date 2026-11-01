import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configs import CONFIGS, function_up
from predict import mfpt

LAM, MU = 1 / 60, 1 / 5


def test_series_is_inverse_sum():
    assert mfpt(CONFIGS['d_series'], LAM, MU) == pytest.approx(1 / (3 * LAM))


def test_two_out_of_three_closed_form():
    # 3 canales + votador; sin votador: (5λ+μ)/(6λ²). Se verifica con votador casi perfecto.
    from configs import Comp
    cfg = {'c1': Comp(('src',)), 'c2': Comp(('src',)), 'c3': Comp(('src',)),
           'mon': Comp(('c1', 'c2', 'c3'), k=2)}
    assert mfpt(cfg, LAM, MU) == pytest.approx((5 * LAM + MU) / (6 * LAM ** 2))


def test_voter_tolerates_one_channel_only():
    cfg = CONFIGS['r2oo3']
    assert function_up(cfg, {'c1': False})
    assert not function_up(cfg, {'c1': False, 'c2': False})
    assert not function_up(cfg, {'v': False})


def test_triangle_uses_alternate_path():
    cfg = CONFIGS['d_triangle']
    assert function_up(cfg, {'l13': False})
    assert not function_up(cfg, {'l13': False, 'l23': False})


def test_extra_link_helps_structurally_but_hurts_under_series_rule():
    a_s, a_p = (mfpt(CONFIGS[c], LAM, MU) for c in ('d_series', 'd_parallel'))
    b_s, b_p = (mfpt(CONFIGS[c], LAM, MU, links_in_series=True) for c in ('d_series', 'd_parallel'))
    assert a_p > a_s
    assert b_p < b_s


def test_availability_series_is_product():
    from configs import CONFIGS
    from predict import availability
    p = 0.2 / (0.1 + 0.2)
    assert abs(availability(CONFIGS['d_series'], 0.1, 0.2) - p ** 3) < 1e-12


def test_common_cause_reduces_to_independent_and_lowers_time():
    from configs import CONFIGS
    from predict import mfpt
    g = (('la', 'lb'),)
    cfg = CONFIGS['d_parallel']
    assert abs(mfpt(cfg, 0.1, 0.5, groups=g, beta=0.0) - mfpt(cfg, 0.1, 0.5)) < 1e-9
    assert mfpt(cfg, 0.1, 0.5, groups=g, beta=0.3) < mfpt(cfg, 0.1, 0.5)
