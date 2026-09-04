"""Parameter-identification tools for measured solar-cell data."""
from .fit import (
    JointData,
    evaluate_joint,
    fit,
    fit_from_csv,
    fit_joint,
    joint_block_diagnostics,
    joint_block_score,
    joint_residual,
    load_iv_csv,
    load_joint_data,
    make_params,
    residual,
    validate_iv_data,
)
from .report import (
    comparison_figure,
    joint_comparison_figure,
    physical_warnings,
    correlation_from_covar,
    identifiability_figure,
    identifiability_summary,
)
from .trace import (
    fit_with_trace,
    plot_optimization_trace,
    trace_to_gif,
    save_optimization_gif,
)

__all__ = [
    "fit", "fit_from_csv", "fit_joint", "joint_block_diagnostics", "joint_block_score",
    "load_iv_csv", "load_joint_data",
    "joint_residual", "evaluate_joint", "JointData", "make_params", "residual",
    "validate_iv_data",
    "comparison_figure", "physical_warnings",
    "joint_comparison_figure",
    "correlation_from_covar", "identifiability_figure", "identifiability_summary",
    "fit_with_trace", "plot_optimization_trace", "trace_to_gif",
    "save_optimization_gif",
]
