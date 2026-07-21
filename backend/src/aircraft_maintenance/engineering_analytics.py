"""
Step 1 analytics module for the Aircraft Maintenance Intelligence Platform.

This module loads an Excel maintenance dataset, selects an aircraft's latest
flight record, analyzes recent history, and returns neutral statistical context
as JSON-ready Python dictionaries.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)


# Sensor fields used for deterministic trend analysis. These names match the
# cleaned dataset columns after units such as "(PSI)" and "(cycles)" are removed.
SENSOR_COLUMNS = [
    "Ambient_Temperature",
    "Humidity",
    "Outside_Air_Temperature",
    "Engine_Temperature",
    "Exhaust_Gas_Temperature",
    "Oil_Temperature",
    "Oil_Pressure",
    "Engine_Vibration",
    "Compressor_Pressure",
    "Fuel_Flow",
    "Hydraulic_Pressure",
    "Engine_RPM",
]


# The source Excel file may contain user-friendly headers such as
# "Flight_Cycle (cycles)" or "Aircraft ID". This map converts common variants
# into the canonical names used throughout the analytics module.
COLUMN_ALIASES = {
    "aircraftid": "Aircraft_ID",
    "aircraft": "Aircraft_ID",
    "tailnumber": "Aircraft_ID",
    "tailno": "Aircraft_ID",
    "flightcycle": "Flight_Cycle",
    "flightcycles": "Flight_Cycle",
    "cycle": "Flight_Cycle",
    "cycles": "Flight_Cycle",
    "flightnumber": "Flight_Cycle",
    "flightno": "Flight_Cycle",
}


DECISION_COLUMNS = {
    "Detected_Failure_Mode",
    "Recommended_Maintenance_Action",
    "Maintenance_Status",
}


@dataclass(frozen=True)
class HistoricalAnalysis:
    """Neutral trend and historical statistics for one numeric signal."""

    column: str
    latest_value: float
    historical_average: float
    historical_median: float
    historical_std_dev: float
    change_from_average: float
    change_percent: float
    trend_direction: str


@dataclass
class EngineeringSummary:
    """Final JSON-ready engineering summary."""

    aircraft_id: str
    latest_flight_cycle: int
    current_record: dict[str, Any]
    historical_window_size: int
    historical_analysis: list[HistoricalAnalysis] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "aircraft_id": self.aircraft_id,
            "latest_flight_cycle": self.latest_flight_cycle,
            "current_record": self.current_record,
            "historical_window_size": self.historical_window_size,
            "historical_analysis": [item.__dict__ for item in self.historical_analysis],
        }


class AircraftEngineeringAnalytics:
    """Loads aircraft maintenance data and generates deterministic analytics."""

    def __init__(
        self,
        excel_path: str | Path,
        sheet_name: str | int = 0,
    ) -> None:
        self.excel_path = Path(excel_path)
        self.sheet_name = sheet_name
        self.data: pd.DataFrame | None = None

    def load_dataset(self) -> pd.DataFrame:
        """
        Load, clean, validate, and sort the Excel dataset.

        The analytics engine depends on stable column names. The source dataset
        can include units in headers, so columns are normalized before validation.
        """
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.excel_path}")

        logger.info("Loading aircraft maintenance dataset: %s", self.excel_path)
        data = pd.read_excel(self.excel_path, sheet_name=self.sheet_name)
        data = self._clean_columns(data)
        self._validate_required_columns(data)

        data["Flight_Cycle"] = pd.to_numeric(data["Flight_Cycle"], errors="coerce")
        data = data.dropna(subset=["Aircraft_ID", "Flight_Cycle"])
        data["Flight_Cycle"] = data["Flight_Cycle"].astype(int)

        self.data = data.sort_values(["Aircraft_ID", "Flight_Cycle"]).reset_index(
            drop=True
        )
        return self.data

    def list_aircraft(self) -> list[str]:
        """Return all aircraft IDs in the loaded dataset."""
        data = self._require_data()
        return sorted(data["Aircraft_ID"].astype(str).unique().tolist())

    def get_aircraft_history(self, aircraft_id: str) -> pd.DataFrame:
        """Return all historical records for one aircraft."""
        data = self._require_data()
        history = data[data["Aircraft_ID"].astype(str) == str(aircraft_id)].copy()

        if history.empty:
            raise ValueError(f"No records found for aircraft: {aircraft_id}")

        return history.sort_values("Flight_Cycle").reset_index(drop=True)

    def get_latest_record(self, aircraft_id: str) -> pd.Series:
        """Return the latest flight record for one aircraft."""
        history = self.get_aircraft_history(aircraft_id)
        return history.iloc[-1]

    def get_previous_records(self, aircraft_id: str, window: int = 10) -> pd.DataFrame:
        """Return the previous N flights, excluding the latest flight."""
        history = self.get_aircraft_history(aircraft_id)
        return history.iloc[:-1].tail(window).reset_index(drop=True)

    def generate_summary(
        self,
        aircraft_id: str,
        history_window: int = 10,
    ) -> EngineeringSummary:
        """
        Generate deterministic engineering analytics for one aircraft.

        This method does not call an LLM. It prepares trusted structured facts
        that can later be passed to Bedrock as engineering context.
        """
        latest = self.get_latest_record(aircraft_id)
        previous = self.get_previous_records(aircraft_id, window=history_window)

        historical_analysis = self._calculate_historical_analysis(latest, previous)

        return EngineeringSummary(
            aircraft_id=str(aircraft_id),
            latest_flight_cycle=int(latest["Flight_Cycle"]),
            current_record=self._series_to_json_ready_dict(latest),
            historical_window_size=len(previous),
            historical_analysis=historical_analysis,
        )

    def _calculate_historical_analysis(
        self,
        latest: pd.Series,
        previous: pd.DataFrame,
    ) -> list[HistoricalAnalysis]:
        """Compare latest numeric values against the previous flight window."""
        if previous.empty:
            return []

        analysis: list[HistoricalAnalysis] = []
        numeric_columns = [
            column
            for column in SENSOR_COLUMNS + ["Risk_Score", "Remaining_Useful_Life"]
            if column in previous.columns and column in latest.index
        ]

        for column in numeric_columns:
            history_values = pd.to_numeric(previous[column], errors="coerce").dropna()
            latest_value = pd.to_numeric(pd.Series([latest[column]]), errors="coerce")

            if history_values.empty or latest_value.isna().iloc[0]:
                continue

            latest_float = float(latest_value.iloc[0])
            average = float(history_values.mean())
            median = float(history_values.median())
            std_dev = float(history_values.std(ddof=0))
            change = latest_float - average
            change_percent = 0.0 if average == 0 else (change / average) * 100

            analysis.append(
                HistoricalAnalysis(
                    column=column,
                    latest_value=round(latest_float, 3),
                    historical_average=round(average, 3),
                    historical_median=round(median, 3),
                    historical_std_dev=round(std_dev, 3),
                    change_from_average=round(change, 3),
                    change_percent=round(change_percent, 3),
                    trend_direction=self._trend_direction(change_percent),
                )
            )

        return analysis

    @staticmethod
    def _clean_columns(data: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize source Excel headers into stable Python-friendly names.
        """
        data = data.copy()
        cleaned_columns = []

        for column in data.columns:
            column_name = str(column).strip()
            column_without_units = re.sub(r"\s*\([^)]*\)", "", column_name).strip()
            normalized_key = re.sub(
                r"[^a-z0-9]+",
                "",
                column_without_units.lower(),
            )

            if normalized_key in COLUMN_ALIASES:
                cleaned_columns.append(COLUMN_ALIASES[normalized_key])
            else:
                cleaned_columns.append(
                    re.sub(r"[^A-Za-z0-9]+", "_", column_without_units).strip("_")
                )

        data.columns = cleaned_columns
        return data

    @staticmethod
    def _validate_required_columns(data: pd.DataFrame) -> None:
        """Validate the minimum columns needed for aircraft timeline analysis."""
        required_columns = {"Aircraft_ID", "Flight_Cycle"}
        missing_columns = required_columns.difference(data.columns)
        if missing_columns:
            available_columns = ", ".join(data.columns)
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}. "
                f"Available columns after cleanup: [{available_columns}]"
            )

    def _require_data(self) -> pd.DataFrame:
        if self.data is None:
            return self.load_dataset()
        return self.data

    @staticmethod
    def _trend_direction(change_percent: float) -> str:
        """Convert percent change into a simple trend label."""
        if change_percent > 3:
            return "INCREASING"
        if change_percent < -3:
            return "DECREASING"
        return "STABLE"

    @staticmethod
    def _series_to_json_ready_dict(row: pd.Series) -> dict[str, Any]:
        """Convert pandas values into JSON-safe Python values."""
        clean: dict[str, Any] = {}
        for key, value in row.to_dict().items():
            if key in DECISION_COLUMNS:
                continue
            if pd.isna(value):
                clean[key] = None
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        return clean


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    dataset_path = (
        r"./backend/data/aircraft_maintenance_intelligence_dataset.xlsx"
    )
    aircraft_id = "AIR-001"

    analytics = AircraftEngineeringAnalytics(
        dataset_path,
        sheet_name="AircraftMaintenanceData",
    )
    analytics.load_dataset()
 
    summary = analytics.generate_summary(aircraft_id, history_window=10)
    print(json.dumps(summary.to_dict(), indent=2))
