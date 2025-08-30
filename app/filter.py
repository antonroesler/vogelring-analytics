from dataclasses import dataclass
import pandas as pd


@dataclass
class Filter:
    klass_name = "Filter"
    name: str
    description: str
    column: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df


class EqualsFilter(Filter):
    klass_name = "Gleich Filter"
    value: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df[self.column] == self.value]


class RangeFilter(Filter):
    klass_name = "Bereich Filter"
    min_value: str
    max_value: str


class MultiSelectFilter(Filter):
    klass_name = "Mehrfachauswahl Filter"
    values: list[str]

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df[self.column].isin(self.values)]


class IncludesFilter(Filter):
    klass_name = "Enthält Filter"
    value: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df[self.column].str.contains(self.value, case=False)]


class DateRangeFilter(Filter):
    klass_name = "Datum Bereich Filter"
    min_date: str
    max_date: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df[self.column].between(self.min_date, self.max_date)]


class MonthFilter(Filter):
    klass_name = "Monat Filter"
    month: str

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        return df[df[self.column].str.contains(self.month, case=False)]


class YearFilter(Filter):
    klass_name = "Jahr Filter"
    year: int
