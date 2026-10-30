"""
Uncertainty Quantification (UQ), Latin Hypercube Sampling (LHS),
Monte Carlo Reliability, and Seismic Fragility Engine (Phase 9).
Evaluates probability of failure Pf = P(FS < 1.0), Cornell reliability index beta,
and monotonically increasing seismic fragility curves across 4 damage states.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum
import numpy as np
from scipy import stats

from .surrogate_engine import SurrogateInputs, FastPINNSurrogate


class DamageState(str, Enum):
    """Retaining wall seismic performance damage states."""
    SLIGHT = "Slight"         # Minor cracking, u >= 25 mm
    MODERATE = "Moderate"     # Serviceability distress, u >= 50 mm
    EXTENSIVE = "Extensive"   # Plastic hinging, strut distress, u >= 100 mm
    COLLAPSE = "Collapse"     # Total overturning / sliding failure, u >= 200 mm or FS < 1.0


@dataclass
class DistributionConfig:
    """Statistical distribution specification for random variables."""
    name: str
    dist_type: str = "uniform" # "uniform", "normal", or "lognormal"
    min_val: float = 0.0
    max_val: float = 1.0
    mean: float = 0.5
    std: float = 0.1

    def sample_quantiles(self, u_quantiles: np.ndarray) -> np.ndarray:
        """Transforms uniform quantiles u in [0, 1] to the specified distribution."""
        u_clamped = np.clip(u_quantiles, 1e-6, 1.0 - 1e-6)
        if self.dist_type == "uniform":
            return self.min_val + u_clamped * (self.max_val - self.min_val)
        elif self.dist_type == "normal":
            return stats.norm.ppf(u_clamped, loc=self.mean, scale=self.std)
        elif self.dist_type == "lognormal":
            # For lognormal: mean and std in log-space
            sigma_ln = math.sqrt(math.log(1.0 + (self.std / max(self.mean, 1e-3)) ** 2))
            mu_ln = math.log(max(self.mean, 1e-3)) - 0.5 * (sigma_ln ** 2)
            return stats.lognorm.ppf(u_clamped, s=sigma_ln, scale=math.exp(mu_ln))
        else:
            return self.min_val + u_clamped * (self.max_val - self.min_val)


@dataclass
class ReliabilityResult:
    """Summary of Monte Carlo reliability and probabilistic safety analysis."""
    num_samples: int
    mean_fs: float
    std_fs: float
    cov_fs: float                     # Coefficient of variation = std / mean
    reliability_index_beta: float     # Cornell reliability index beta = (mean - 1) / std
    probability_of_failure: float     # Pf = P(FS < 1.0)
    fs_percentile_5: float
    fs_percentile_50: float            # Median FS
    fs_percentile_95: float
    fs_samples: np.ndarray = field(repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_samples": self.num_samples,
            "mean_fs": self.mean_fs,
            "std_fs": self.std_fs,
            "cov_fs": self.cov_fs,
            "reliability_index_beta": self.reliability_index_beta,
            "probability_of_failure": self.probability_of_failure,
            "fs_percentile_5": self.fs_percentile_5,
            "fs_percentile_50": self.fs_percentile_50,
            "fs_percentile_95": self.fs_percentile_95,
        }


@dataclass
class FragilityCurveData:
    """Seismic fragility curve data for a single damage state."""
    damage_state: DamageState
    median_pga_theta: float           # Median capacity theta (g)
    log_std_beta: float               # Lognormal dispersion beta
    pga_values_g: np.ndarray          # Array of PGA points (g)
    exceedance_probabilities: np.ndarray # P(DS >= ds | PGA)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "damage_state": self.damage_state.value,
            "median_pga_theta": self.median_pga_theta,
            "log_std_beta": self.log_std_beta,
            "pga_values_g": self.pga_values_g.tolist(),
            "exceedance_probabilities": self.exceedance_probabilities.tolist(),
        }


# ==============================================================================
# 1. Latin Hypercube Sampling (LHS) Engine
# ==============================================================================

class LatinHypercubeSampler:
    """
    Multivariate Latin Hypercube Sampler with stratified uniform binning
    and inverse CDF transformation to arbitrary continuous distributions.
    """

    def __init__(self, random_seed: int = 42):
        self.rng = np.random.RandomState(random_seed)

    def sample_uniform(self, n_samples: int, n_dims: int) -> np.ndarray:
        """
        Generates n_samples stratified points in [0, 1]^n_dims using Latin Hypercube Sampling.
        """
        if n_samples <= 0 or n_dims <= 0:
            raise ValueError(f"Sample count and dimensions must be positive, got N={n_samples}, D={n_dims}")

        lhs_matrix = np.zeros((n_samples, n_dims), dtype=np.float64)
        for d in range(n_dims):
            # Divide [0, 1] into n_samples intervals
            perm = self.rng.permutation(n_samples)
            random_offset = self.rng.uniform(0.0, 1.0, size=n_samples)
            lhs_matrix[:, d] = (perm + random_offset) / float(n_samples)

        return lhs_matrix

    def generate_parametric_database(
        self,
        n_samples: int = 100,
        c_range: Tuple[float, float] = (5.0, 50.0),
        phi_range: Tuple[float, float] = (20.0, 42.0),
        gamma_range: Tuple[float, float] = (16.0, 21.0),
        height_range: Tuple[float, float] = (4.0, 15.0),
        bay_range: Tuple[float, float] = (2.0, 6.0),
        pile_dia_range: Tuple[float, float] = (0.6, 1.5),
        pile_len_range: Tuple[float, float] = (6.0, 25.0),
        pga_range: Tuple[float, float] = (0.1, 0.6),
    ) -> List[SurrogateInputs]:
        """
        Generates a parametric database of retaining wall configurations using LHS.
        """
        n_dims = 8
        u_samples = self.sample_uniform(n_samples=n_samples, n_dims=n_dims)

        configs: List[SurrogateInputs] = []
        for i in range(n_samples):
            u = u_samples[i]
            c = c_range[0] + u[0] * (c_range[1] - c_range[0])
            phi = phi_range[0] + u[1] * (phi_range[1] - phi_range[0])
            gamma = gamma_range[0] + u[2] * (gamma_range[1] - gamma_range[0])
            height = height_range[0] + u[3] * (height_range[1] - height_range[0])
            bay = bay_range[0] + u[4] * (bay_range[1] - bay_range[0])
            dp = pile_dia_range[0] + u[5] * (pile_dia_range[1] - pile_dia_range[0])
            lp = pile_len_range[0] + u[6] * (pile_len_range[1] - pile_len_range[0])
            pga = pga_range[0] + u[7] * (pga_range[1] - pga_range[0])

            # Select strut count based on height
            n_struts = 1 if height <= 6.0 else (2 if height <= 10.0 else 3)
            # Shell radius proportional to bay span
            r_shell = max(2.5, min(8.0, 1.1 * bay))

            configs.append(
                SurrogateInputs(
                    panel_height=float(height),
                    bay_span=float(bay),
                    shell_radius=float(r_shell),
                    cohesion=float(c),
                    friction_angle=float(phi),
                    unit_weight=float(gamma),
                    pga_g=float(pga),
                    num_struts=n_struts,
                    pile_diameter=float(dp),
                    pile_length=float(lp),
                    wall_thickness=float(max(0.30, min(0.70, 0.05 * height))),
                )
            )

        return configs


# ==============================================================================
# 2. Monte Carlo Reliability Engine
# ==============================================================================

class MonteCarloReliabilityEngine:
    """
    Probabilistic reliability analysis evaluating factor of safety distributions,
    probability of failure Pf = P(FS < 1.0), and Cornell reliability index beta.
    """

    def __init__(self, random_seed: int = 42):
        self.sampler = LatinHypercubeSampler(random_seed=random_seed)
        self.surrogate = FastPINNSurrogate()

    def run_reliability_analysis(
        self,
        base_inputs: SurrogateInputs,
        c_cov: float = 0.20,      # Cohesion COV (typical 20%)
        phi_cov: float = 0.10,    # Friction angle COV (typical 10%)
        gamma_cov: float = 0.05,  # Unit weight COV (typical 5%)
        pga_cov: float = 0.25,    # Seismic PGA COV (typical 25%)
        n_samples: int = 1000,
    ) -> ReliabilityResult:
        """
        Executes Monte Carlo sampling over soil shear strength and seismic demand,
        evaluating the resulting factor of safety distribution.
        """
        # Formulate distributions
        c_mean = base_inputs.cohesion
        phi_mean = base_inputs.friction_angle
        gamma_mean = base_inputs.unit_weight
        pga_mean = base_inputs.pga_g

        # Generate uniform LHS matrix
        u = self.sampler.sample_uniform(n_samples=n_samples, n_dims=4)

        # Lognormal for cohesion and PGA (strictly positive)
        # Normal for friction angle and unit weight
        c_samples = stats.lognorm.ppf(
            np.clip(u[:, 0], 1e-4, 1.0 - 1e-4),
            s=c_cov,
            scale=c_mean,
        )
        phi_samples = stats.norm.ppf(
            np.clip(u[:, 1], 1e-4, 1.0 - 1e-4),
            loc=phi_mean,
            scale=phi_mean * phi_cov,
        )
        phi_samples = np.clip(phi_samples, 15.0, 45.0)

        gamma_samples = stats.norm.ppf(
            np.clip(u[:, 2], 1e-4, 1.0 - 1e-4),
            loc=gamma_mean,
            scale=gamma_mean * gamma_cov,
        )
        gamma_samples = np.clip(gamma_samples, 14.0, 23.0)

        pga_samples = stats.lognorm.ppf(
            np.clip(u[:, 3], 1e-4, 1.0 - 1e-4),
            s=pga_cov,
            scale=pga_mean,
        )
        pga_samples = np.clip(pga_samples, 0.05, 0.90)

        # Evaluate surrogate FS across all realizations
        fs_values = np.zeros(n_samples)
        for i in range(n_samples):
            inp = SurrogateInputs(
                panel_height=base_inputs.panel_height,
                bay_span=base_inputs.bay_span,
                shell_radius=base_inputs.shell_radius,
                cohesion=float(c_samples[i]),
                friction_angle=float(phi_samples[i]),
                unit_weight=float(gamma_samples[i]),
                pga_g=float(pga_samples[i]),
                num_struts=base_inputs.num_struts,
                pile_diameter=base_inputs.pile_diameter,
                pile_length=base_inputs.pile_length,
                wall_thickness=base_inputs.wall_thickness,
            )
            pred = self.surrogate.predict(inp)
            fs_values[i] = pred.sliding_factor_of_safety

        mean_fs = float(np.mean(fs_values))
        std_fs = float(np.std(fs_values))
        cov_fs = float(std_fs / max(mean_fs, 1e-4))

        # Cornell reliability index beta = (mean - 1.0) / std
        beta = (mean_fs - 1.0) / max(std_fs, 1e-4)

        # Probability of failure Pf = P(FS < 1.0)
        n_fail = int(np.sum(fs_values < 1.0))
        pf = float(n_fail / n_samples)
        if pf == 0.0 and beta > 0.0:
            # Theoretical Gaussian tail approximation Pf ~ Phi(-beta)
            pf = float(stats.norm.cdf(-beta))

        p5, p50, p95 = np.percentile(fs_values, [5.0, 50.0, 95.0])

        return ReliabilityResult(
            num_samples=n_samples,
            mean_fs=mean_fs,
            std_fs=std_fs,
            cov_fs=cov_fs,
            reliability_index_beta=float(beta),
            probability_of_failure=pf,
            fs_percentile_5=float(p5),
            fs_percentile_50=float(p50),
            fs_percentile_95=float(p95),
            fs_samples=fs_values,
        )


# ==============================================================================
# 3. Seismic Fragility Engine
# ==============================================================================

class SeismicFragilityEngine:
    """
    Computes seismic fragility curves P(DS >= ds | PGA) across Slight, Moderate,
    Extensive, and Collapse damage states per HAZUS / NIBS methodology.
    Guarantees strict monotonicity: P(DS | PGA) is non-decreasing with PGA.
    """

    def __init__(
        self,
        theta_medians: Optional[Dict[DamageState, float]] = None,
        beta_dispersions: Optional[Dict[DamageState, float]] = None,
    ):
        # Default median capacities (PGA in g)
        self.thetas = theta_medians or {
            DamageState.SLIGHT: 0.18,     # Median PGA for slight cracking
            DamageState.MODERATE: 0.32,   # Median PGA for moderate movement
            DamageState.EXTENSIVE: 0.48,  # Median PGA for extensive yield
            DamageState.COLLAPSE: 0.68,   # Median PGA for collapse / instability
        }
        # Lognormal standard deviations (dispersion beta)
        self.betas = beta_dispersions or {
            DamageState.SLIGHT: 0.40,
            DamageState.MODERATE: 0.40,
            DamageState.EXTENSIVE: 0.45,
            DamageState.COLLAPSE: 0.50,
        }

    def evaluate_fragility_at_pga(self, damage_state: DamageState, pga_g: float) -> float:
        """
        Calculates exceedance probability P(DS >= ds | PGA):
            P = Phi( ln(PGA / theta) / beta )
        """
        if pga_g <= 0.0:
            return 0.0

        theta = self.thetas[damage_state]
        beta = self.betas[damage_state]

        # Standard normal CDF
        z = math.log(pga_g / theta) / beta
        p = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        return float(min(1.0, max(0.0, p)))

    def generate_fragility_curves(
        self,
        pga_min: float = 0.05,
        pga_max: float = 0.85,
        num_points: int = 50,
    ) -> Dict[DamageState, FragilityCurveData]:
        """
        Generates continuous fragility curves across all 4 damage states.
        Enforces strict monotonic increase with PGA and hierarchical state ordering:
        P(Slight) >= P(Moderate) >= P(Extensive) >= P(Collapse).
        """
        pga_arr = np.linspace(pga_min, pga_max, num_points)
        curves: Dict[DamageState, FragilityCurveData] = {}

        states = [
            DamageState.SLIGHT,
            DamageState.MODERATE,
            DamageState.EXTENSIVE,
            DamageState.COLLAPSE,
        ]

        probs_by_state = {}
        for ds in states:
            p_raw = np.array([self.evaluate_fragility_at_pga(ds, pga) for pga in pga_arr])
            # Enforce numerical monotonicity
            p_mono = np.maximum.accumulate(p_raw)
            probs_by_state[ds] = p_mono

        # Enforce hierarchical ordering across states: Slight >= Moderate >= Extensive >= Collapse
        for i in range(len(states) - 1):
            curr_ds = states[i]
            next_ds = states[i + 1]
            probs_by_state[next_ds] = np.minimum(probs_by_state[next_ds], probs_by_state[curr_ds])

        for ds in states:
            curves[ds] = FragilityCurveData(
                damage_state=ds,
                median_pga_theta=self.thetas[ds],
                log_std_beta=self.betas[ds],
                pga_values_g=pga_arr,
                exceedance_probabilities=probs_by_state[ds],
            )

        return curves
