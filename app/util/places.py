from data import load_data, unique_nonempty


def get_top_k_places(k: int = 10) -> list[str]:
    """Returns the names of the top k places by number of sightings"""
    df = load_data()
    return sorted(unique_nonempty(df, "place"), key=lambda x: df[df["place"] == x]["id"].count(), reverse=True)[:k]
