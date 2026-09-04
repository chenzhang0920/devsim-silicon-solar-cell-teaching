'Utilities for tests/test_device_validation.py.'
import sys
import types

import numpy as np
import pytest

from model import SolarCellParams
import model.device as device
from model.device import simulate, simulate_eqe, sweep_bias, sweep_light, profiles


def test_unknown_direct_solver_restores_bundled_umfpack(monkeypatch):
    callback = object()
    shim = types.ModuleType("devsim.umfpack.umfshim")
    shim.local_solver_callback = callback
    calls = []

    monkeypatch.setitem(sys.modules, "devsim.umfpack.umfshim", shim)
    monkeypatch.setattr(device, "get_parameter", lambda **_: "unknown")
    monkeypatch.setattr(device, "set_parameter", lambda **kwargs: calls.append(kwargs))

    device._restore_direct_solver_after_reset()

    assert calls == [
        {"name": "direct_solver", "value": "custom"},
        {"name": "solver_callback", "value": callback},
    ]


def test_simulate_rejects_unsorted_voltage_before_solver():
    with pytest.raises(ValueError, match="ascending order"):
        simulate(SolarCellParams(), np.array([0.2, 0.1]))


@pytest.mark.parametrize("func,args", [
    (sweep_light, {"n_steps": 0}),
    (sweep_bias, {"v_max": 0.6, "n_steps": 0}),
])
def test_sweeps_reject_invalid_step_count(func, args):
    with pytest.raises(ValueError, match=">= 1"):
        func(SolarCellParams(), **args)


@pytest.mark.parametrize("index", [-1, 16, 1.5, True])
def test_simulate_eqe_rejects_invalid_wavelength_index(index):
    with pytest.raises(ValueError, match="wavelength_index"):
        simulate_eqe(SolarCellParams(), index)


def test_profiles_rejects_nonfinite_bias_before_solver():
    with pytest.raises(ValueError, match="bias"):
        profiles(SolarCellParams(), bias=np.nan)


def test_front_dead_layer_must_remain_inside_emitter(monkeypatch):
    monkeypatch.setattr(device, "_DEAD_LAYER", 0.6e-4)
    with pytest.raises(ValueError, match="must be <= emitter_depth"):
        device._setup_device(SolarCellParams())


def test_direct_device_api_enforces_p_plus_doping_contrast():
    p = SolarCellParams(emitter_doping=5e17, base_doping=1e17)
    with pytest.raises(ValueError, match=r"emitter_doping >= 10\*base_doping"):
        simulate(p, np.array([0.0]))
