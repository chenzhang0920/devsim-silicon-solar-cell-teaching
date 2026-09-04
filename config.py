"""Central configuration for the device model, simulation, and calibration.

Students should normally edit this file rather than changing model internals. Units
match :class:`model.parameters.SolarCellParams` unless stated otherwise. Measurement
metadata such as illuminated area and irradiance are passed explicitly to data-preparation
commands because they describe an experiment, not the simulated 1D material stack.
"""

# Illustrative total incident power at ``photon_flux = 1``. It includes spectral
# power outside the finite generation bins and is not an experimental irradiance.
MODELED_INPUT_POWER_W_CM2 = 0.1

# This is a teaching baseline, not a fabrication-calibrated process card.
MODEL_PARAMS = {
    # Geometry
    "thickness": 250e-4,          # total thickness (cm): 250 µm
    "emitter_depth": 0.5e-4,      # p+ emitter depth (cm): 0.5 µm

    # Abrupt p+-on-n doping profile
    "emitter_doping": 1e19,       # p+ emitter acceptor concentration (cm⁻³)
    "base_doping": 1e17,          # n-type base donor concentration (cm⁻³)

    # Constant low-field transport parameters (a deliberate teaching approximation)
    "electron_mobility": 1417.0,  # cm²/(V·s)
    "hole_mobility": 471.0,       # cm²/(V·s)
    "electron_lifetime": 1e-5,    # s
    "hole_lifetime": 1e-5,        # s

    # Auger coefficients (cm⁶/s)
    "auger_n": 2.8e-31,
    "auger_p": 9.9e-32,

    # Effective near-contact loss velocities (cm/s), implemented as dead layers.
    # These are teaching proxies, not Robin-boundary surface-recombination parameters.
    "front_srv": 1e4,
    "back_srv": 1e6,

    # Illumination and optics
    "photon_flux": 1.0,           # dimensionless scale on the baseline teaching spectrum
    "front_reflectance": 0.0,     # 0 is ideal antireflection, not bare silicon
    "temperature": 300.0,         # K; the current teaching model supports 300 K only

    # Terminal parasitics (Ω·cm²). Zero means ideal; Rs/Rsh are added after DEVSIM.
    "series_resistance": 0.0,
    "shunt_resistance": 0.0,      # 0 represents infinite shunt resistance
}


SIMULATION = {
    "quiet": True,                # set False to inspect native Newton iterations

    # Junction-voltage continuation grid. Stop just beyond the baseline Voc while
    # avoiding the uninformative high-current branch.
    "voltages": {"start": 0.0, "stop": 0.64, "step": 0.02},
    "light_ramp_steps": 8,        # larger values improve continuation but cost time
    "bias_max_step": 0.05,        # maximum hidden continuation step for sparse input grids (V)
    "dead_layer": 2e-5,           # effective near-contact loss-layer thickness (cm)

    # Fine spacing resolves surfaces and the narrow p+ junction; the base can be coarser.
    "mesh": {
        "top": 2e-7,              # 2 nm resolves the shortest-wavelength absorption depth
        "junction": 2e-7,         # 2 nm
        "bulk": 1e-4,
        "surface": 1e-6,
    },
}


CALIBRATION = {
    # The bundled default is synthetic data for a hardware-free smoke test.
    # For an experimental cell, point this to a standardized table in
    # data/processed/, for example data/processed/light_iv_sample3.csv.
    "data_file": "data/synthetic/iv.csv",
    "method": "least_squares",

    # DEVSIM current noise makes SciPy's much smaller default finite-difference step unstable.
    "diff_step": 1e-3,
    "residual_mode": "absolute",  # choices: absolute or relative

    # A single sparse J-V curve cannot separate lifetime and near-contact loss effects, so those
    # parameters remain fixed. Light level and effective series resistance are the
    # two intentionally fitted, comparatively identifiable quantities.
    "params": {
        "electron_lifetime": {"value": 1e-5, "min": 1e-9, "max": 1e-3, "vary": False},
        "hole_lifetime":     {"value": 1e-5, "min": 1e-9, "max": 1e-3, "vary": False},
        "front_srv":         {"value": 1e4, "min": 1e2, "max": 1e7, "vary": False},
        "back_srv":          {"value": 1e6, "min": 1e2, "max": 1e7, "vary": False},
        "photon_flux":       {"value": 1.0, "min": 0.1, "max": 2.0, "vary": True},
        "series_resistance": {"value": 1.0, "min": 0.0, "max": 20.0, "vary": True},

        # Rsh=0 means infinity. Use a positive value and min>=10 before setting vary=True.
        "shunt_resistance":  {"value": 0.0, "min": 0.0, "max": 5000.0, "vary": False},
    },

    # Canonical assessed workflow: a deliberately small multi-observable fit for
    # one measured cell. The single synthetic J-V fit above is only a smoke test
    # for learning how the optimizer behaves.
    "joint": {
        "default_sample": 3,
        "paths": {
            "light_iv": "data/processed/light_iv_sample{sample}.csv",
            "dark_iv": "data/processed/dark_iv_sample{sample}.csv",
            "ishort_summary": "data/processed/ishort_summary.csv",
            "voc_summary": "data/processed/voc_summary.csv",
        },
        # These are block-level priorities, not statistical confidence values.
        # Each J-V curve contributes an RMS residual after current scaling, then
        # every observable block is multiplied by sqrt(weight).
        "weights": {
            "light_iv": 1.0,
            "dark_iv": 0.35,
            "light_ishort": 0.50,
            "light_voc": 0.25,
        },
        # Model-data discrepancy scales used to compare unlike observables.
        # They are teaching assumptions, not inferred instrument uncertainties.
        "iv_sigma_fraction": 0.025,    # fraction of the selected J-V current scale
        "ishort_sigma_floor": 5e-4,   # A/cm^2
        "voc_sigma": 0.010,            # V
        # Warn when the weighted mean squared block discrepancy exceeds 4,
        # corresponding to a weighted RMS mismatch above twice the stated
        # scales. This is a teaching guard, not a statistical chi-square test.
        "quality_warning_block_score": 4.0,
    },
}
