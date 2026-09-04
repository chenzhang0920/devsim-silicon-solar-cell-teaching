"""One-dimensional silicon solar-cell simulation implemented with DEVSIM."""
from __future__ import annotations

import io
import importlib.util
import os
import sys
from contextlib import redirect_stdout

import numpy as np


def _setup_devsim_dll_path() -> None:
    """Register native-library directories before importing DEVSIM on Windows."""
    spec = importlib.util.find_spec("devsim")
    if spec is None or spec.origin is None:
        return
    pkg = os.path.dirname(os.path.abspath(spec.origin))
    env_root = os.path.dirname(os.path.dirname(os.path.dirname(pkg)))
    candidates = [
        os.path.join(pkg, "umfpack"),
        os.path.join(env_root, "Library", "bin"),
    ]
    for directory in candidates:
        if os.path.isdir(directory):
            if hasattr(os, "add_dll_directory"):
                _DLL_HANDLES.append(os.add_dll_directory(directory))
            if directory not in os.environ.get("PATH", ""):
                os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")


_DLL_HANDLES: list[object] = []
_setup_devsim_dll_path()

from devsim import (
    add_1d_contact,
    add_1d_mesh_line,
    add_1d_region,
    create_1d_mesh,
    create_device,
    finalize_mesh,
    get_contact_current,
    get_contact_list,
    get_edge_model_values,
    get_node_model_values,
    get_parameter,
    reset_devsim,
    set_node_values,
    set_parameter,
    solve,
)

from devsim.python_packages.model_create import (
    CreateNodeModel,
    CreateSolution,
)
from devsim.python_packages.simple_physics import (
    CreateSiliconDriftDiffusion,
    CreateSiliconDriftDiffusionAtContact,
    CreateSiliconPotentialOnly,
    CreateSiliconPotentialOnlyContact,
    GetContactBiasName,
    SetSiliconParameters,
    celec_model,
    chole_model,
)

from .parameters import SolarCellParams, check_params
from . import spectrum
from config import SIMULATION

_QUIET = SIMULATION.get("quiet", True)


def _quiet_sim(fn):
    """Suppress verbose native DEVSIM output when configured for classroom use."""
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _QUIET:
            captured = io.StringIO()
            try:
                with redirect_stdout(captured):
                    return fn(*args, **kwargs)
            except Exception:
                # Successful classroom runs stay concise, but a failed native
                # solve must retain the diagnostic that explains the failure.
                diagnostics = captured.getvalue()
                if diagnostics:
                    print(diagnostics, file=sys.stderr, end="")
                raise
        return fn(*args, **kwargs)

    return wrapper


_DEVICE = "cell"
_REGION = "bulk"
_MESH = "cell"
_TOP = "top"
_BOT = "bot"

_LIGHT_RAMP_STEPS = SIMULATION.get("light_ramp_steps", 8)
_BIAS_MAX_STEP = SIMULATION.get("bias_max_step", 0.05)
_DEAD_LAYER = SIMULATION.get("dead_layer", 2e-5)
_MESH_CFG = SIMULATION.get("mesh", {})

# DEVSIM's documented DC examples use a relative update tolerance of 1e-7.
# Tighter values can stall at backend-dependent floating-point noise on Linux
# without changing any classroom-scale observable.
_DC_RELATIVE_ERROR = 1e-7
_DC_MAXIMUM_ITERATIONS = 30


_CELE = celec_model
_CHOLE = chole_model

_WAVELENGTH_INDEX = None


def _restore_direct_solver_after_reset() -> None:
    """Restore DEVSIM's bundled UMFPACK callback when reset clears it."""
    if get_parameter(name="direct_solver") != "unknown":
        return

    # On installations without MKL, devsim.__init__ selects its bundled
    # UMFPACK adapter. DEVSIM 2.10.1 reset_devsim() clears that Python callback
    # even though the imported module remains cached, so register it again.
    try:
        from devsim.umfpack.umfshim import local_solver_callback
    except ImportError as exc:
        raise RuntimeError(
            "DEVSIM has no active direct solver and its bundled UMFPACK "
            "adapter could not be imported"
        ) from exc
    set_parameter(name="direct_solver", value="custom")
    set_parameter(name="solver_callback", value=local_solver_callback)


def _validated_steps(value, name: str) -> int:
    """Validate a positive integer continuation-step count."""
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1; received {value!r}")
    return int(value)


def _validate_voltages(voltages) -> np.ndarray:
    """Validate voltages for stable ascending continuation."""
    values = np.asarray(voltages, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("voltages must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(values)):
        raise ValueError("voltages must contain only finite values")
    if np.any(np.diff(values) < 0):
        raise ValueError("DEVSIM voltage sweeps must be sorted in ascending order for stable continuation")
    return values


def _bias_continuation_points(start: float, stop: float) -> np.ndarray:
    """Return hidden bias substeps ending exactly at ``stop``.

    Caller-requested output points are unchanged; the added points only keep
    nonlinear continuation reliable for sparse or student-defined grids.
    """
    max_step = float(_BIAS_MAX_STEP)
    if not np.isfinite(max_step) or max_step <= 0:
        raise ValueError("SIMULATION.bias_max_step must be finite and > 0")
    if not np.all(np.isfinite([start, stop])):
        raise ValueError("bias continuation endpoints must be finite")
    delta = float(stop - start)
    if delta == 0:
        return np.empty(0, dtype=float)
    intervals = max(1, int(np.ceil(abs(delta) / max_step)))
    return np.linspace(start, stop, intervals + 1, dtype=float)[1:]


def _build_mesh(p: SolarCellParams) -> None:
    """Build a single-region 1D mesh refined at both surfaces and the junction."""
    create_1d_mesh(mesh=_MESH)

    add_1d_mesh_line(mesh=_MESH, pos=0.0, ps=_MESH_CFG.get("top", 1e-6), tag="top")
    add_1d_mesh_line(mesh=_MESH, pos=p.emitter_depth, ps=_MESH_CFG.get("junction", 1e-6), tag="mid")
    add_1d_mesh_line(mesh=_MESH, pos=p.thickness * 0.5, ps=_MESH_CFG.get("bulk", 1e-4), tag="bulk_mid")
    add_1d_mesh_line(mesh=_MESH, pos=p.thickness - 2 * _DEAD_LAYER, ps=_MESH_CFG.get("surface", 1e-6), tag="back_dead")
    add_1d_mesh_line(mesh=_MESH, pos=p.thickness, ps=_MESH_CFG.get("surface", 1e-6), tag="bot")
    add_1d_contact(mesh=_MESH, name=_TOP, tag="top", material="metal")
    add_1d_contact(mesh=_MESH, name=_BOT, tag="bot", material="metal")
    add_1d_region(mesh=_MESH, material="Si", region=_REGION, tag1="top", tag2="bot")
    finalize_mesh(mesh=_MESH)
    create_device(mesh=_MESH, device=_DEVICE)


def _set_parameters(p: SolarCellParams) -> None:
    """Install 300 K silicon and configurable transport parameters."""
    SetSiliconParameters(_DEVICE, _REGION, p.temperature)
    set_parameter(device=_DEVICE, region=_REGION, name="mu_n", value=p.electron_mobility)
    set_parameter(device=_DEVICE, region=_REGION, name="mu_p", value=p.hole_mobility)
    set_parameter(device=_DEVICE, region=_REGION, name="taun", value=p.electron_lifetime)
    set_parameter(device=_DEVICE, region=_REGION, name="taup", value=p.hole_lifetime)

    set_parameter(device=_DEVICE, region=_REGION, name="PhotonFlux", value=0.0)


def _set_doping(p: SolarCellParams) -> None:
    """Define complementary abrupt doping: front p+ emitter and rear n base."""

    emitter = f"step({p.emitter_depth}-x)"
    CreateNodeModel(_DEVICE, _REGION, "Donors",
                    f"{p.base_doping}*(1-({emitter}))")
    CreateNodeModel(_DEVICE, _REGION, "Acceptors",
                    f"{p.emitter_doping}*({emitter})")
    CreateNodeModel(_DEVICE, _REGION, "NetDoping", "Donors-Acceptors")


def _set_top_bias(v: float) -> None:
    """Set terminal voltage as top p-contact potential relative to grounded n contact."""
    set_parameter(device=_DEVICE, name=GetContactBiasName(_TOP), value=float(v))


def _output_current_density() -> float:
    """Return generation-positive current density at the top contact."""
    jn = get_contact_current(device=_DEVICE, contact=_TOP,
                             equation="ElectronContinuityEquation")
    jp = get_contact_current(device=_DEVICE, contact=_TOP,
                             equation="HoleContinuityEquation")
    return float(-(jn + jp))


def _solve_dc(absolute_error: float) -> None:
    """Run one DC continuation step with cross-platform numerical tolerances."""
    result = solve(
        type="dc",
        absolute_error=absolute_error,
        relative_error=_DC_RELATIVE_ERROR,
        maximum_iterations=_DC_MAXIMUM_ITERATIONS,
        info=True,
    )
    if result["converged"]:
        return

    iterations = result.get("iterations", ())
    if not iterations:
        raise RuntimeError("DEVSIM DC solve did not converge and returned no iteration data")

    final = iterations[-1]
    details = []
    for device_info in final.get("devices", ()):
        for region_info in device_info.get("regions", ()):
            for equation in region_info.get("equations", ()):
                details.append(
                    f"{equation['name']}: rel={equation['relative_error']:.3e}, "
                    f"abs={equation['absolute_error']:.3e}"
                )
    summary = "; ".join(details) or "no equation residuals returned"
    raise RuntimeError(
        f"DEVSIM DC solve did not converge after {len(iterations)} iterations; {summary}"
    )


def _solve_equilibrium() -> None:
    """Solve the equilibrium Poisson problem with both contacts grounded."""
    CreateSolution(_DEVICE, _REGION, "Potential")

    # Start Newton's method from the local charge-neutral potential to reduce
    # the initial carrier-charge imbalance across the abrupt junction.  These
    # are the same statistics used by DEVSIM's ohmic-contact model.
    CreateNodeModel(
        _DEVICE,
        _REGION,
        "EquilibriumPotentialGuess",
        f"ifelse(NetDoping > 0, V_t*log({_CELE}/n_i), -V_t*log({_CHOLE}/n_i))",
    )
    set_node_values(
        device=_DEVICE,
        region=_REGION,
        name="Potential",
        init_from="EquilibriumPotentialGuess",
    )

    CreateSiliconPotentialOnly(_DEVICE, _REGION)
    for c in get_contact_list(device=_DEVICE):
        set_parameter(device=_DEVICE, name=GetContactBiasName(c), value=0.0)
        CreateSiliconPotentialOnlyContact(_DEVICE, _REGION, c)
    _solve_dc(absolute_error=1.0)


def _setup_dark_dd() -> None:
    """Initialize and solve the dark drift-diffusion equations."""
    CreateSolution(_DEVICE, _REGION, "Electrons")
    CreateSolution(_DEVICE, _REGION, "Holes")
    set_node_values(device=_DEVICE, region=_REGION, name="Electrons",
                    init_from="IntrinsicElectrons")
    set_node_values(device=_DEVICE, region=_REGION, name="Holes",
                    init_from="IntrinsicHoles")

    CreateSiliconDriftDiffusion(_DEVICE, _REGION)
    for c in get_contact_list(device=_DEVICE):
        CreateSiliconDriftDiffusionAtContact(_DEVICE, _REGION, c)

    _solve_dc(absolute_error=1e10)


def _setup_device(p: SolarCellParams) -> None:
    """Validate, build, and solve the intrinsic device in the dark."""
    p = check_params(vars(p))
    _check_resistances(p)
    _validated_steps(_LIGHT_RAMP_STEPS, "SIMULATION['light_ramp_steps']")
    mesh_defaults = {"top": 1e-6, "junction": 1e-6,
                     "bulk": 1e-4, "surface": 1e-6}
    for name, default in mesh_defaults.items():
        spacing = _MESH_CFG.get(name, default)
        try:
            valid = not isinstance(spacing, bool) and np.isfinite(float(spacing)) \
                and float(spacing) > 0
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                f"SIMULATION['mesh']['{name}'] must be a positive finite value; received {spacing!r}")
    if not (0.0 < _DEAD_LAYER < p.thickness / 2):
        raise ValueError(
            f"SIMULATION['dead_layer'] must lie in (0, thickness/2); received {_DEAD_LAYER}")
    if _DEAD_LAYER > p.emitter_depth:
        raise ValueError(
            "SIMULATION['dead_layer'] must be <= emitter_depth so the front "
            "minority-carrier loss region remains inside the p+ emitter")
    if p.emitter_depth >= p.thickness - 2 * _DEAD_LAYER:
        raise ValueError("emitter_depth must lie before the rear-surface dead layer")
    reset_devsim()
    _restore_direct_solver_after_reset()
    _build_mesh(p)
    _set_parameters(p)
    _set_doping(p)
    _solve_equilibrium()
    _setup_dark_dd()


def _add_generation(p: SolarCellParams) -> None:
    """Add optical generation, bulk recombination, and near-contact loss layers."""
    usrh = "(Electrons*Holes - n_i^2)/(taup*(Electrons + n1) + taun*(Holes + p1))"

    uauger = (f"({p.auger_n}*Electrons + {p.auger_p}*Holes)"
              f"*(Electrons*Holes - n_i^2)")

    if _WAVELENGTH_INDEX is None:
        _sum = " + ".join(f"{c}*exp(-{a}*x)" for c, a in spectrum.generation_terms())
    else:
        c, a = spectrum.monochromatic_terms(_WAVELENGTH_INDEX)
        _sum = f"{c}*exp(-{a}*x)"
    opt_gen = f"PhotonFlux*({1.0 - p.front_reflectance})*({_sum})"

    front = (f"{p.front_srv}*(Electrons - n_i^2/({_CHOLE}))"
             f"*step({_DEAD_LAYER} - x)/{_DEAD_LAYER}")
    back = (f"{p.back_srv}*(Holes - n_i^2/({_CELE}))"
            f"*step(x - ({p.thickness} - {_DEAD_LAYER}))/{_DEAD_LAYER}")

    gen_e = f"ElectronCharge*({opt_gen} - ({usrh}) - ({uauger}) - ({front}) - ({back}))"
    gen_h = f"ElectronCharge*(({usrh}) + ({uauger}) + ({front}) + ({back}) - ({opt_gen}))"

    CreateNodeModel(_DEVICE, _REGION, "OpticalGeneration", opt_gen)
    CreateNodeModel(_DEVICE, _REGION, "ElectronGeneration", gen_e)
    CreateNodeModel(_DEVICE, _REGION, "HoleGeneration", gen_h)

    # Register recombination-source Jacobians for Newton convergence:
    # d(ElectronGeneration)/dv = -q·dR/dv and d(HoleGeneration)/dv = +q·dR/dv.

    srh_den = "(taup*(Electrons + n1) + taun*(Holes + p1))"
    dU_dn = (f"(Holes*{srh_den} - (Electrons*Holes - n_i^2)*taup)"
             f"/{srh_den}^2")
    dU_dp = (f"(Electrons*{srh_den} - (Electrons*Holes - n_i^2)*taun)"
             f"/{srh_den}^2")                     # ∂USRH/∂p
    dUa_dn = (f"{p.auger_n}*(Electrons*Holes - n_i^2)"
              f" + ({p.auger_n}*Electrons + {p.auger_p}*Holes)*Holes")       # ∂U_Auger/∂n
    dUa_dp = (f"{p.auger_p}*(Electrons*Holes - n_i^2)"
              f" + ({p.auger_n}*Electrons + {p.auger_p}*Holes)*Electrons")   # ∂U_Auger/∂p

    dfront_dn = f"{p.front_srv}*step({_DEAD_LAYER} - x)/{_DEAD_LAYER}"
    dback_dp = f"{p.back_srv}*step(x - ({p.thickness} - {_DEAD_LAYER}))/{_DEAD_LAYER}"

    dR_dn = f"({dU_dn}) + ({dUa_dn}) + ({dfront_dn})"
    dR_dp = f"({dU_dp}) + ({dUa_dp}) + ({dback_dp})"

    CreateNodeModel(_DEVICE, _REGION, "ElectronGeneration:Electrons",
                    f"-ElectronCharge*({dR_dn})")
    CreateNodeModel(_DEVICE, _REGION, "ElectronGeneration:Holes",
                    f"-ElectronCharge*({dR_dp})")
    CreateNodeModel(_DEVICE, _REGION, "HoleGeneration:Electrons",
                    f"ElectronCharge*({dR_dn})")
    CreateNodeModel(_DEVICE, _REGION, "HoleGeneration:Holes",
                    f"ElectronCharge*({dR_dp})")


def _full_flux(p: SolarCellParams) -> float:
    """Return all-bin or selected-bin photon flux in cm⁻² s⁻¹."""
    if _WAVELENGTH_INDEX is None:
        return float(p.photon_flux * spectrum.total_photon_flux())
    return float(p.photon_flux * spectrum.bin_photon_flux(_WAVELENGTH_INDEX))


def _ramp_light(p: SolarCellParams) -> None:
    """Ramp photon flux from dark to the configured illumination level."""
    full_flux = _full_flux(p)
    n_steps = _validated_steps(_LIGHT_RAMP_STEPS, "SIMULATION['light_ramp_steps']")
    for flux in np.linspace(0.0, full_flux, n_steps + 1)[1:]:
        set_parameter(device=_DEVICE, region=_REGION, name="PhotonFlux", value=float(flux))
        _solve_dc(absolute_error=1e10)


def _illuminate(p: SolarCellParams) -> None:
    """Install generation/recombination models and ramp to full illumination."""
    _add_generation(p)
    _ramp_light(p)


def _ramp_bias(bias: float) -> None:
    """Continue the illuminated solution from zero to a target forward bias."""
    for b in np.linspace(0.0, bias, _LIGHT_RAMP_STEPS + 1)[1:]:
        _set_top_bias(b)
        _solve_dc(absolute_error=1e10)


def _grab(*names: str) -> dict:
    """Read selected node models into NumPy arrays."""
    return {n: np.asarray(
                get_node_model_values(device=_DEVICE, region=_REGION, name=n),
                dtype=float)
            for n in names}


def _grab_edges(*names: str) -> dict:
    """Read selected edge models into NumPy arrays."""
    return {n: np.asarray(
                get_edge_model_values(device=_DEVICE, region=_REGION, name=n),
                dtype=float)
            for n in names}


@_quiet_sim
def sweep_light(p: SolarCellParams, n_steps: int | None = None) -> list[dict]:
    """Return physical-profile frames while illumination ramps from dark to full."""
    n = _validated_steps(
        n_steps if n_steps is not None else _LIGHT_RAMP_STEPS, "n_steps")
    _setup_device(p)
    _add_generation(p)

    frames: list[dict] = []

    def push(flux_frac: float) -> None:
        g = _grab("x", "Potential", "Electrons", "Holes", "OpticalGeneration")
        frames.append({
            "flux": float(flux_frac),
            "x": g["x"],
            "potential": g["Potential"],
            "electrons": g["Electrons"],
            "holes": g["Holes"],
            "generation": g["OpticalGeneration"],
        })

    push(0.0)
    full = _full_flux(p)
    if full == 0.0:
        return frames
    for flux in np.linspace(0.0, full, n + 1)[1:]:
        set_parameter(device=_DEVICE, region=_REGION, name="PhotonFlux", value=float(flux))
        _solve_dc(absolute_error=1e10)
        push(float(flux / full))
    return frames


@_quiet_sim
def sweep_bias(p: SolarCellParams, v_max: float,
               n_steps: int | None = None) -> list[dict]:
    """Return physical-profile frames over an illuminated forward-bias ramp."""
    if not np.isfinite(v_max):
        raise ValueError(f"v_max must be finite; received {v_max!r}")
    n = _validated_steps(
        n_steps if n_steps is not None else _LIGHT_RAMP_STEPS, "n_steps")
    _setup_device(p)
    _illuminate(p)

    frames: list[dict] = []

    def push(bias: float) -> None:
        g = _grab("x", "Potential", "Electrons", "Holes")
        frames.append({
            "bias": float(bias),
            "x": g["x"],
            "potential": g["Potential"],
            "electrons": g["Electrons"],
            "holes": g["Holes"],
        })

    push(0.0)
    for b in np.linspace(0.0, v_max, n + 1)[1:]:
        _set_top_bias(b)
        _solve_dc(absolute_error=1e10)
        push(b)
    return frames


def _check_resistances(p: SolarCellParams) -> None:
    """Reject terminal parasitics at the intrinsic-device API boundary."""
    if p.series_resistance > 0 or p.shunt_resistance > 0:
        raise ValueError(
            "device.simulate solves only the intrinsic device, so parasitic resistances must be 0.\n"
            "Use model.terminal_iv for terminal J-V curves; calibration uses "
            "model.run_simulation_terminal."
        )


@_quiet_sim
def simulate(p: SolarCellParams,
             voltages: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run the illuminated intrinsic-device voltage sweep and return ``(V, J)``."""
    voltages = _validate_voltages(voltages)
    _setup_device(p)
    _illuminate(p)

    currents = []
    current_bias = 0.0
    for v in voltages:
        for continuation_bias in _bias_continuation_points(current_bias, float(v)):
            _set_top_bias(continuation_bias)
            _solve_dc(absolute_error=1e10)
        currents.append(_output_current_density())
        current_bias = float(v)

    return np.asarray(voltages, dtype=float), np.asarray(currents, dtype=float)


@_quiet_sim
def simulate_eqe(p: SolarCellParams, wavelength_index: int) -> float:
    """Return monochromatic short-circuit current density for one EQE wavelength bin."""
    if isinstance(wavelength_index, bool) or not isinstance(
            wavelength_index, (int, np.integer)):
        raise ValueError("wavelength_index must be an integer")
    index = int(wavelength_index)
    if not 0 <= index < len(spectrum.wavelengths_nm()):
        raise ValueError(
            f"wavelength_index out of range: {index}; "
            f"expected 0..{len(spectrum.wavelengths_nm()) - 1}")
    global _WAVELENGTH_INDEX
    _WAVELENGTH_INDEX = index
    try:
        _setup_device(p)
        _illuminate(p)
        _set_top_bias(0.0)
        _solve_dc(absolute_error=1e10)
        return _output_current_density()
    finally:
        _WAVELENGTH_INDEX = None


@_quiet_sim
def profiles(p: SolarCellParams, bias: float = 0.0) -> dict:
    """Return equilibrium and illuminated internal profiles at a selected bias."""
    if not np.isfinite(bias):
        raise ValueError(f"bias must be finite; received {bias!r}")
    _setup_device(p)

    eq = _grab("x", "Potential", "Electrons", "Holes",
               "NetDoping", "Donors", "Acceptors")
    eq_edges = _grab_edges("ElectricField")

    _illuminate(p)
    if bias:
        _ramp_bias(bias)
    ill = _grab("Potential", "Electrons", "Holes", "OpticalGeneration")
    ill_edges = _grab_edges("ElectricField")

    return {
        "x": eq["x"],
        "potential": eq["Potential"],
        "electrons": eq["Electrons"],
        "holes": eq["Holes"],
        "net_doping": eq["NetDoping"],
        "donors": eq["Donors"],
        "acceptors": eq["Acceptors"],
        "field_x": 0.5 * (eq["x"][:-1] + eq["x"][1:]),
        "electric_field": eq_edges["ElectricField"],
        "ill_potential": ill["Potential"],
        "ill_electrons": ill["Electrons"],
        "ill_holes": ill["Holes"],
        "ill_electric_field": ill_edges["ElectricField"],
        "generation": ill["OpticalGeneration"],
    }
