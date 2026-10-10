"""Spectral / frequency-domain features using FFT."""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def _spectral_stats(series: pd.Series) -> dict:
    """Compute spectral features from a time-series segment."""
    values = series.values.astype(float)
    n = len(values)
    empty = {
        "dominant_freq": 0.0,
        "spectral_energy": 0.0,
        "spectral_entropy": 0.0,
        "spectral_kurtosis": 0.0,
        "band_energy_low": 0.0,
        "band_energy_mid": 0.0,
        "band_energy_high": 0.0,
    }
    if n < 4:
        return empty

    fft_vals = np.fft.rfft(values - np.mean(values))
    power = np.abs(fft_vals) ** 2
    freqs = np.fft.rfftfreq(n)

    total_power = power.sum()
    if total_power == 0:
        return empty

    # Dominant frequency
    dominant_idx = np.argmax(power[1:]) + 1  # skip DC component
    dominant_freq = float(freqs[dominant_idx])

    # Spectral energy
    spectral_energy = float(total_power)

    # Spectral entropy
    p = power / total_power
    p = p[p > 0]
    spectral_entropy = float(-np.sum(p * np.log2(p)))

    power_mean = float(power.mean())
    power_std = float(power.std())
    spectral_kurtosis = (
        float(np.mean(((power - power_mean) / power_std) ** 4) - 3.0)
        if power_std > 0
        else 0.0
    )
    bands = ((0.0, 1.0 / 6.0), (1.0 / 6.0, 1.0 / 3.0), (1.0 / 3.0, 0.5 + 1e-12))

    return {
        "dominant_freq": dominant_freq,
        "spectral_energy": spectral_energy,
        "spectral_entropy": spectral_entropy,
        "spectral_kurtosis": spectral_kurtosis,
        "band_energy_low": float(power[(freqs >= bands[0][0]) & (freqs < bands[0][1])].sum()),
        "band_energy_mid": float(power[(freqs >= bands[1][0]) & (freqs < bands[1][1])].sum()),
        "band_energy_high": float(power[(freqs >= bands[2][0]) & (freqs <= bands[2][1])].sum()),
    }


def spectral_features(
    df: pd.DataFrame,
    window: int = 50,
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compute spectral features per machine+sensor using a sliding FFT window.

    Returns DataFrame with original columns + spectral feature columns.
    """
    if group_cols is None:
        group_cols = ["machine_id", "sensor"]

    df = df.sort_values(group_cols + ["time"]).copy()
    result_frames = []

    for key, grp in df.groupby(group_cols):
        feat_df = grp.copy()
        values = grp["value"]

        dom_freq = []
        energy = []
        entropy = []
        kurtosis = []
        low_energy = []
        mid_energy = []
        high_energy = []

        for i in range(len(values)):
            start = max(0, i - window + 1)
            segment = values.iloc[start : i + 1]
            stats = _spectral_stats(segment)
            dom_freq.append(stats["dominant_freq"])
            energy.append(stats["spectral_energy"])
            entropy.append(stats["spectral_entropy"])
            kurtosis.append(stats["spectral_kurtosis"])
            low_energy.append(stats["band_energy_low"])
            mid_energy.append(stats["band_energy_mid"])
            high_energy.append(stats["band_energy_high"])

        feat_df["dominant_freq"] = dom_freq
        feat_df["spectral_energy"] = energy
        feat_df["spectral_entropy"] = entropy
        feat_df["spectral_kurtosis"] = kurtosis
        feat_df["band_energy_low"] = low_energy
        feat_df["band_energy_mid"] = mid_energy
        feat_df["band_energy_high"] = high_energy

        result_frames.append(feat_df)

    result = pd.concat(result_frames, ignore_index=True)
    logger.info("Computed spectral features (window=%d) — %d rows", window, len(result))
    return result
