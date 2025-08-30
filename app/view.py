from dataclasses import dataclass
import pandas as pd
from filter import Filter
from pathlib import Path
import json

STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DataView:
    name: str
    description: str
    columns: list[str]
    filters: list[Filter]

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        for filter in self.filters:
            df = filter.apply(df)
        return df[self.columns]

    def save(self) -> None:
        with open(STORAGE_DIR / f"{self.name}.json", "w") as f:
            json.dump(self, f)

    @classmethod
    def load(cls, name: str) -> "DataView":
        with open(STORAGE_DIR / f"{name}.json", "r") as f:
            return cls(**json.load(f))
