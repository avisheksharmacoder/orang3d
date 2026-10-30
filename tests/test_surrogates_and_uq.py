"""
Comprehensive verification test suite for AI/PINN Fast Surrogates and Uncertainty Quantification (Phase 9):
- Sub-millisecond CPU inference latency (< 1 ms threshold)
- Physics conservation (horizontal static equilibrium sum Fx = 0 within 2%)
- Surrogate accuracy (R2 >= 0.98, MAPE < 3%)
- Latin Hypercube Sampling (LHS) uniformity (Kolmogorov-Smirnov test p > 0.05)
- Monte Carlo Reliability & Failure Probability Pf = P(FS < 1.0)
- Monotonic Seismic Fragility Curves across Slight, Moderate, Extensive, Collapse damage states
"""

import time
import math
import pytest
import numpy as np
from scipy import stats

from orang3d.physics.surrogate_engine import (
    SurrogateInputs,
    SurrogatePrediction,
    FastPINNSurrogate,
    get_fast_pinn_surrogate,
    predict_surrogate,
    TORCH_AVAILABLE,
)
from orang3d.physics.pinn_trainer import (
    PINNLossConfig,
    TrainingSample,
    TrainingMetrics,
    PINNTrainer,
    generate_ground_truth_sample,
)
from orang3d.physics.uncertainty import (
    DamageState,
    DistributionConfig,
    ReliabilityResult,
    FragilityCurveData,
    LatinHypercubeSampler,
    MonteCarloReliabilityEngine,
    SeismicFragilityEngine,
)


# ==============================================================================
# 1. Latency Benchmark: Sub-Millisecond CPU Inference (< 1 ms threshold)
# ==============================================================================

def test_surrogate_inference_latency():
    """
    Phase 9.4: Enforces runtime threshold: single prediction in < 1.0 ms on CPU,
    guaranteeing smooth 60 FPS slider tuning in desktop GUI viewports.
    """
    surrogate = FastPINNSurrogate()
    inputs = SurrogateInputs(
        panel_height=8.0,
        bay_span=4.0,
        shell_radius=4.5,
        cohesion=20.0,
        friction_angle=32.0,
        unit_weight=19.0,
        pga_g=0.30,
        num_struts=2,
    )

    # Warmup run
    _ = surrogate.predict(inputs)

    # Benchmark over 50 iterations
    iterations = 50
    t0 = time.perf_counter()
    for _ in range(iterations):
        _ = surrogate.predict(inputs)
    total_time_s = time.perf_counter() - t0
    avg_latency_ms = (total_time_s / iterations) * 1000.0

    print(f"\n[BENCHMARK] FastPINNSurrogate average latency: {avg_latency_ms:.3f} ms (Threshold: < 1.0 ms)")
    assert avg_latency_ms < 1.0, f"Inference latency {avg_latency_ms:.3f} ms exceeded 1.0 ms threshold"


# ==============================================================================
# 2. Physics Conservation: Horizontal Equilibrium Sum Fx = 0
# ==============================================================================

def test_physics_loss_conservation():
    """
    Phase 9.4: Asserts that surrogate predictions satisfy horizontal static equilibrium
    within 2% across varying heights and seismic PGA demands:
        Sum Fx = P_ae - sum(F_strut) - R_base = 0
    """
    surrogate = FastPINNSurrogate()
    test_cases = [
        SurrogateInputs(panel_height=5.0, bay_span=3.0, pga_g=0.15, num_struts=1),
        SurrogateInputs(panel_height=8.0, bay_span=4.0, pga_g=0.30, num_struts=2),
        SurrogateInputs(panel_height=12.0, bay_span=5.0, pga_g=0.45, num_struts=3),
    ]

    for inp in test_cases:
        pred = surrogate.predict(inp)
        p_ae = pred.total_earth_thrust_kN
        strut_sum = sum(pred.strut_loads_kN)
        base_rxn = pred.base_shear_reaction_kN

        total_resistance = strut_sum + base_rxn
        imbalance = abs(p_ae - total_resistance)
        imbalance_percent = (imbalance / max(p_ae, 1e-3)) * 100.0

        assert imbalance_percent < 2.0, (
            f"Equilibrium imbalance {imbalance_percent:.2f}% exceeded 2.0% for H={inp.panel_height}m"
        )
        assert pred.equilibrium_imbalance_percent < 2.0
        assert len(pred.elevations_m) == 50
        assert len(pred.bending_moment_kNm_m) == 50
        assert len(pred.shear_force_kN_m) == 50


# ==============================================================================
# 3. Surrogate Accuracy: R2 >= 0.98 and MAPE < 3%
# ==============================================================================

def test_surrogate_accuracy():
    """
    Phase 9.4: Verifies that surrogate output achieves R2 >= 0.98 and MAPE < 3%
    against ground-truth test splits generated across the parametric domain.
    """
    sampler = LatinHypercubeSampler(random_seed=123)
    configs = sampler.generate_parametric_database(n_samples=40)

    # Generate paired dataset
    dataset: list[TrainingSample] = []
    for cfg in configs:
        sample = generate_ground_truth_sample(cfg)
        dataset.append(sample)

    trainer = PINNTrainer(loss_config=PINNLossConfig())
    surrogate, metrics = trainer.train_and_evaluate(dataset=dataset, test_split=0.25)

    print(f"\n[ACCURACY] PINN Surrogate R2: {metrics.r2_score:.4f} (Target: >= 0.98), MAPE: {metrics.mape_percent:.2f}% (Target: < 3%)")
    assert metrics.r2_score >= 0.98, f"Surrogate R2 {metrics.r2_score:.4f} is below 0.98"
    assert metrics.mape_percent < 3.0, f"Surrogate MAPE {metrics.mape_percent:.2f}% is above 3.0%"
    assert metrics.equilibrium_loss < 5.0 # Very small residual
    assert metrics.training_duration_sec < 5.0


# ==============================================================================
# 4. Latin Hypercube Sampling: Kolmogorov-Smirnov Uniformity Test
# ==============================================================================

def test_lhs_distribution_uniformity():
    """
    Phase 9.4: Verifies Kolmogorov-Smirnov test on generated random soil fields
    satisfying standard uniform distribution properties (p-value > 0.05).
    """
    sampler = LatinHypercubeSampler(random_seed=42)
    n_samples = 200
    n_dims = 5
    u_samples = sampler.sample_uniform(n_samples=n_samples, n_dims=n_dims)

    # Each dimension must pass Kolmogorov-Smirnov test against uniform[0, 1]
    for d in range(n_dims):
        col = u_samples[:, d]
        # Must be strictly bounded in (0, 1)
        assert np.all(col >= 0.0)
        assert np.all(col <= 1.0)
        # One point per stratified interval: histogram of n_bins=10 should have 20 points
        hist, _ = np.histogram(col, bins=10, range=(0.0, 1.0))
        assert np.all(hist == 20) # Exact stratification property of LHS!

        # KS test against uniform(0, 1)
        ks_stat, p_value = stats.kstest(col, "uniform")
        assert p_value > 0.05, f"Dim {d} failed KS uniformity test: p-value = {p_value:.4f}"

    # Parametric database generation
    db = sampler.generate_parametric_database(n_samples=25)
    assert len(db) == 25
    for item in db:
        assert 4.0 <= item.panel_height <= 15.0
        assert 5.0 <= item.cohesion <= 50.0
        assert 20.0 <= item.friction_angle <= 42.0
        assert 0.1 <= item.pga_g <= 0.6


# ==============================================================================
# 5. Seismic Fragility Monotonicity & Hierarchy
# ==============================================================================

def test_fragility_monotonicity():
    """
    Phase 9.4: Asserts that failure probability increases monotonically with PGA
    and satisfies hierarchical damage ordering:
        P(Slight) >= P(Moderate) >= P(Extensive) >= P(Collapse)
    """
    engine = SeismicFragilityEngine()
    curves = engine.generate_fragility_curves(pga_min=0.05, pga_max=0.85, num_points=40)

    pga_vals = curves[DamageState.SLIGHT].pga_values_g
    assert len(pga_vals) == 40

    for ds, data in curves.items():
        probs = data.exceedance_probabilities
        # 1. Monotonicity with PGA: P(PGA_{i+1}) >= P(PGA_i)
        diffs = np.diff(probs)
        assert np.all(diffs >= -1e-7), f"Fragility curve for {ds.value} is not monotonically increasing"
        # 2. Probability bounds [0, 1]
        assert np.all((probs >= 0.0) & (probs <= 1.0))

    # 3. Hierarchy: Slight >= Moderate >= Extensive >= Collapse
    p_slight = curves[DamageState.SLIGHT].exceedance_probabilities
    p_moderate = curves[DamageState.MODERATE].exceedance_probabilities
    p_extensive = curves[DamageState.EXTENSIVE].exceedance_probabilities
    p_collapse = curves[DamageState.COLLAPSE].exceedance_probabilities

    assert np.all(p_slight >= p_moderate - 1e-7)
    assert np.all(p_moderate >= p_extensive - 1e-7)
    assert np.all(p_extensive >= p_collapse - 1e-7)

    # High PGA asymptotic behavior: At 0.85g, Slight should be near 1.0
    assert p_slight[-1] > 0.90
    # Low PGA behavior: At 0.05g, Collapse should be near 0.0
    assert p_collapse[0] < 0.05


# ==============================================================================
# 6. Monte Carlo Probabilistic Reliability & Safety Index beta
# ==============================================================================

def test_monte_carlo_reliability_analysis():
    """
    Validates Monte Carlo probabilistic safety evaluation:
    evaluates factor of safety distribution, reliability index beta, and Pf = P(FS < 1.0).
    """
    reliability_engine = MonteCarloReliabilityEngine(random_seed=42)
    inputs = SurrogateInputs(
        panel_height=6.0,
        bay_span=4.0,
        cohesion=25.0,
        friction_angle=32.0,
        unit_weight=18.5,
        pga_g=0.20,
    )

    result = reliability_engine.run_reliability_analysis(
        base_inputs=inputs,
        c_cov=0.20,
        phi_cov=0.10,
        pga_cov=0.20,
        n_samples=200,
    )

    assert result.num_samples == 200
    assert result.mean_fs > 1.0
    assert result.std_fs > 0.0
    assert result.reliability_index_beta > 0.5
    assert 0.0 <= result.probability_of_failure <= 0.50
    assert result.fs_percentile_5 < result.fs_percentile_50 < result.fs_percentile_95

    d = result.to_dict()
    assert "reliability_index_beta" in d
    assert "probability_of_failure" in d


# ==============================================================================
# 7. Distribution Config & Edge Cases
# ==============================================================================

def test_uncertainty_and_surrogate_edge_cases():
    """
    Tests DistributionConfig transformations, singleton prediction,
    loss computation, and invalid inputs.
    """
    # 1. DistributionConfig normal and lognormal
    cfg_norm = DistributionConfig(name="phi", dist_type="normal", mean=30.0, std=3.0)
    samples_norm = cfg_norm.sample_quantiles(np.array([0.1, 0.5, 0.9]))
    assert samples_norm[0] < samples_norm[1] < samples_norm[2]

    cfg_lognorm = DistributionConfig(name="c", dist_type="lognormal", mean=20.0, std=4.0)
    samples_log = cfg_lognorm.sample_quantiles(np.array([0.1, 0.5, 0.9]))
    assert np.all(samples_log > 0.0)

    cfg_uni = DistributionConfig(name="gamma", dist_type="uniform", min_val=16.0, max_val=20.0)
    samples_uni = cfg_uni.sample_quantiles(np.array([0.0, 0.5, 1.0]))
    assert samples_uni[0] == pytest.approx(16.0, abs=1e-3)
    assert samples_uni[2] == pytest.approx(20.0, abs=1e-3)

    # 2. FastPINNSurrogate singleton & predict_surrogate
    inp = SurrogateInputs(panel_height=7.0, bay_span=3.5, pga_g=0.25)
    pred = predict_surrogate(inp)
    assert isinstance(pred, SurrogatePrediction)
    assert pred.sliding_factor_of_safety > 0.5
    d_pred = pred.to_dict()
    assert "crest_displacement_mm" in d_pred

    # 3. Invalid inputs in LHS
    sampler = LatinHypercubeSampler()
    with pytest.raises(ValueError, match="Sample count and dimensions must be positive"):
        sampler.sample_uniform(0, 5)

    with pytest.raises(ValueError, match="Sample count and dimensions must be positive"):
        sampler.sample_uniform(10, 0)

    # 4. Zero PGA fragility check
    frag_engine = SeismicFragilityEngine()
    assert frag_engine.evaluate_fragility_at_pga(DamageState.SLIGHT, 0.0) == 0.0

    # 5. PINN loss evaluation
    trainer = PINNTrainer()
    sample = generate_ground_truth_sample(inp)
    surrogate = get_fast_pinn_surrogate()
    tot_loss, l_data, l_eq, l_diff = trainer.evaluate_loss(surrogate, [sample])
    assert tot_loss >= 0.0
    assert l_eq < 0.05

    # 6. Additional branch coverage: TrainingMetrics to_dict, FragilityCurveData to_dict, DistributionConfig fallback
    metrics = TrainingMetrics(
        r2_score=0.99,
        mape_percent=1.5,
        rmse=2.0,
        equilibrium_loss=0.0,
        differential_loss=0.01,
        training_duration_sec=0.5,
    )
    d_metrics = metrics.to_dict()
    assert d_metrics["r2_score"] == 0.99

    curves = frag_engine.generate_fragility_curves(num_points=10)
    d_curve = curves[DamageState.SLIGHT].to_dict()
    assert "exceedance_probabilities" in d_curve

    cfg_custom = DistributionConfig(name="custom", dist_type="triangular", min_val=1.0, max_val=5.0)
    samples_custom = cfg_custom.sample_quantiles(np.array([0.5]))
    assert 1.0 <= samples_custom[0] <= 5.0

    # Test high safety margin zero failure Pf tail approximation
    safe_inp = SurrogateInputs(panel_height=4.0, bay_span=2.5, cohesion=45.0, friction_angle=40.0, pga_g=0.05)
    rel_eng = MonteCarloReliabilityEngine(random_seed=1)
    safe_rel = rel_eng.run_reliability_analysis(safe_inp, c_cov=0.05, phi_cov=0.02, pga_cov=0.05, n_samples=50)
    assert safe_rel.probability_of_failure <= 1e-3
