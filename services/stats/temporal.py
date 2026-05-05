from statistics import mean, pstdev


def rolling_zscore_spikes(series: list[dict], min_history: int = 6, z_threshold: float = 2.5) -> list[dict]:
    """
    series: [{"bucket": "...", "count": int}, ...] sorted by time.
    Returns spikes with z-score.
    """
    spikes = []
    counts = [int(x["count"]) for x in series]
    for i in range(min_history, len(counts)):
        history = counts[:i]
        mu = mean(history)
        sigma = pstdev(history) or 1.0
        z = (counts[i] - mu) / sigma
        if z >= z_threshold:
            spikes.append(
                {
                    "bucket": series[i]["bucket"],
                    "count": counts[i],
                    "baseline_mean": round(mu, 4),
                    "baseline_std": round(sigma, 4),
                    "z_score": round(z, 4),
                }
            )
    return spikes

