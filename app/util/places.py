from data import load_data, unique_nonempty


def get_places_sorted_by_frequency(limit: int | None = None) -> list[str]:
    """Return places sorted by number of sightings (desc). Optionally limit length."""
    df = load_data()
    places = unique_nonempty(df, "place")
    # Pre-compute counts efficiently
    counts = df.groupby("place")["id"].count().sort_values(ascending=False)
    ordered = [p for p in counts.index.tolist() if p in places]
    if limit is not None:
        return ordered[:limit]
    return ordered


def get_top_k_places(k: int = 10) -> list[str]:
    return get_places_sorted_by_frequency(limit=k)
