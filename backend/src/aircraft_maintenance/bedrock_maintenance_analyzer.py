"""
Amazon Bedrock maintenance analyzer for the Aircraft Maintenance Platform.

This module sends deterministic engineering analytics plus the full internal
maintenance manual PDF to Amazon Bedrock Nova Pro using the Converse API.
The model is asked to return a structured maintenance report as JSON only.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)


class BedrockRuntimeClient(Protocol):
    """Minimal protocol for the boto3 Bedrock Runtime client."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Call the Bedrock Converse API."""


class AircraftMaintenanceAnalyzer:
    """
    Generate AI maintenance reports using Amazon Bedrock and a manual PDF.
    """

    def __init__(
        self,
        bedrock_client: BedrockRuntimeClient,
        model_id: str,
        manual_pdf_path: str | Path,
        temperature: float = 0.2,
        max_tokens: int = 2_000,
    ) -> None:
        self.bedrock_client = bedrock_client
        self.model_id = model_id
        self.manual_pdf_path = Path(manual_pdf_path)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def load_manual(self) -> bytes:
        """Load the complete aircraft maintenance manual PDF as bytes."""
        if not self.manual_pdf_path.exists():
            raise FileNotFoundError(
                f"Maintenance manual not found: {self.manual_pdf_path}"
            )

        if self.manual_pdf_path.suffix.lower() != ".pdf":
            raise ValueError(
                "Maintenance manual must be a PDF file. "
                f"Received: {self.manual_pdf_path}"
            )

        logger.info("Loading maintenance manual: %s", self.manual_pdf_path)
        return self.manual_pdf_path.read_bytes()

    def build_prompt(self, engineering_analytics: dict[str, Any]) -> str:
        """Build the model prompt from engineering analytics JSON."""
        analytics_json = json.dumps(
            engineering_analytics,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        return f"""
You are a Senior Aircraft Maintenance Engineer.

Your task is to generate a professional aircraft maintenance engineering report
using two inputs:

1. Engineering Analytics JSON provided below.
2. The attached internal Aircraft Maintenance Manual PDF.

Important rules:
- Compare every engineering parameter in the analytics JSON against the
  thresholds, safe operating limits, risk matrix, decision trees, inspection
  procedures, failure modes, and maintenance actions defined in the manual.
- Use only thresholds and maintenance procedures found in the attached manual.
- Do not invent thresholds, limits, failure modes, or maintenance actions.
- If a required threshold or procedure is unavailable in the manual, state that
  explicitly in the JSON output.
- Prioritize maintenance actions when multiple actions apply.
- Determine whether the aircraft status is one of:
  SAFE, MONITOR, MAINTENANCE REQUIRED, GROUND AIRCRAFT.
- Produce a final flight decision for the operations dashboard. The decision
  must clearly state whether the aircraft may fly now, may fly with monitoring,
  or must not fly until maintenance is completed.
- Return JSON only. Do not include Markdown, prose outside JSON, or code fences.

Required analysis:
- Health Status
- Failure Severity
- Threshold Violations
- Maintenance Recommendation
- Flight Readiness
- Final Fly / No-Fly Decision
- Inspection Required
- Root Cause
- Confidence
- Generated Work Order

Engineering Analytics JSON:
{analytics_json}

Return exactly one JSON object with this schema:
{{
  "aircraft": "string",
  "aircraft_model": "string",
  "health_status": "SAFE | MONITOR | MAINTENANCE REQUIRED | GROUND AIRCRAFT",
  "risk_level": "LOW | MEDIUM | HIGH | CRITICAL | UNKNOWN",
  "safe_for_next_flight": true,
  "final_flight_decision": {{
    "decision": "CLEARED_TO_FLY | FLY_WITH_MONITORING | MAINTENANCE_REQUIRED_BEFORE_FLIGHT | GROUND_AIRCRAFT",
    "can_fly_now": true,
    "ui_statement": "string",
    "required_before_next_flight": "string",
    "decision_rationale": "string"
  }},
  "overall_summary": "string",
  "threshold_violations": [
    {{
      "parameter": "string",
      "observed_value": "number or string",
      "manual_threshold": "string",
      "severity": "LOW | MEDIUM | HIGH | CRITICAL | UNKNOWN",
      "manual_reference": "string",
      "explanation": "string"
    }}
  ],
  "root_cause": {{
    "most_likely_cause": "string",
    "supporting_evidence": ["string"],
    "manual_reference": "string"
  }},
  "maintenance_actions": [
    {{
      "priority": 1,
      "action": "string",
      "reason": "string",
      "manual_reference": "string"
    }}
  ],
  "inspection_checklist": [
    {{
      "step": 1,
      "inspection_item": "string",
      "acceptance_criteria": "string",
      "manual_reference": "string"
    }}
  ],
  "work_order": {{
    "title": "string",
    "aircraft_id": "string",
    "work_order_type": "INSPECTION | REPAIR | MONITORING | GROUNDING",
    "priority": "LOW | MEDIUM | HIGH | CRITICAL",
    "tasks": ["string"],
    "required_parts_or_tools": ["string"],
    "estimated_maintenance_category": "string"
  }},
  "confidence": {{
    "score": 0.0,
    "rationale": "string",
    "missing_information": ["string"]
  }}
}}
""".strip()

    def analyze(self, engineering_analytics: dict[str, Any]) -> dict[str, Any]:
        """Generate a structured AI maintenance report from analytics and PDF."""
        prompt = self.build_prompt(engineering_analytics)
        manual_bytes = self.load_manual()

        conversation = [
            {
                "role": "user",
                "content": [
                    {"text": prompt},
                    {
                        "document": {
                            "format": "pdf",
                            "name": self._document_name(),
                            "source": {"bytes": manual_bytes},
                        }
                    },
                ],
            }
        ]

        try:
            logger.info("Invoking Bedrock model: %s", self.model_id)
            response = self.bedrock_client.converse(
                modelId=self.model_id,
                messages=conversation,
                inferenceConfig={
                    "maxTokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
        except (ClientError, BotoCoreError) as exc:
            logger.exception("Bedrock invocation failed")
            raise RuntimeError(
                f"Unable to invoke Bedrock model '{self.model_id}'"
            ) from exc

        response_text = self._extract_response_text(response)
        return self._parse_json_response(response_text)

    def _document_name(self) -> str:
        """Return a Bedrock-safe document name."""
        return self.manual_pdf_path.stem.replace("_", " ").replace("-", " ")

    @staticmethod
    def _extract_response_text(response: dict[str, Any]) -> str:
        """Extract text from a Bedrock Converse response."""
        try:
            content = response["output"]["message"]["content"]
        except KeyError as exc:
            raise ValueError("Bedrock response did not contain message content") from exc

        text_parts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and "text" in block
        ]
        response_text = "\n".join(text_parts).strip()

        if not response_text:
            raise ValueError("Bedrock returned an empty response")

        return response_text

    @staticmethod
    def _parse_json_response(response_text: str) -> dict[str, Any]:
        """Parse and validate the JSON-only model response."""
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.error("Model returned non-JSON response: %s", response_text)
            raise ValueError("Bedrock response was not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise ValueError("Bedrock response JSON must be an object")

        return parsed


if __name__ == "__main__":
    import boto3

    logging.basicConfig(level=logging.INFO)

    base_dir = Path(__file__).resolve().parents[2]
    manual_pdf_path = base_dir / "data" / "AeroTech_ATX200_Maintenance_Manual.pdf"

    if not manual_pdf_path.exists():
        raise FileNotFoundError(f"Maintenance manual not found: {manual_pdf_path}")

    # Example usage:
    # 1. Generate analytics JSON from the engineering analytics module
    # 2. Paste that JSON into the `engineering_json` variable below
    engineering_json = {
  "aircraft_id": "AIR-001",
  "latest_flight_cycle": 100,
  "current_record": {
    "Aircraft_ID": "AIR-001",
    "Aircraft_Model": "A320neo",
    "Engine_Model": "CFM LEAP-1A",
    "Airport_Code": "DEL",
    "Flight_Cycle": 100,
    "Flight_Hours": 340.0,
    "Cycles_Since_Overhaul": 100,
    "Last_Maintenance_Date": "2026-10-28",
    "Ambient_Temperature": 4.717116117435664,
    "Humidity": 90,
    "Outside_Air_Temperature": -2.5,
    "Engine_Temperature": 720.9,
    "Exhaust_Gas_Temperature": 685.1,
    "Oil_Temperature": 102.1,
    "Oil_Pressure": 47.9,
    "Engine_Vibration": 6.08,
    "Compressor_Pressure": 44.6,
    "Fuel_Flow": 2456.8,
    "Hydraulic_Pressure": 3017.9,
    "Engine_RPM": 9796,
    "Risk_Score": 77.2,
    "Remaining_Useful_Life": 30
  },
  "historical_window_size": 10,
  "historical_analysis": [
    {
      "column": "Ambient_Temperature",
      "latest_value": 4.717,
      "historical_average": 17.377,
      "historical_median": 21.16,
      "historical_std_dev": 11.17,
      "change_from_average": -12.66,
      "change_percent": -72.854,
      "trend_direction": "DECREASING"
    },
    {
      "column": "Humidity",
      "latest_value": 90.0,
      "historical_average": 57.8,
      "historical_median": 55.0,
      "historical_std_dev": 21.521,
      "change_from_average": 32.2,
      "change_percent": 55.709,
      "trend_direction": "INCREASING"
    },
    {
      "column": "Outside_Air_Temperature",
      "latest_value": -2.5,
      "historical_average": 11.68,
      "historical_median": 15.85,
      "historical_std_dev": 12.857,
      "change_from_average": -14.18,
      "change_percent": -121.404,
      "trend_direction": "DECREASING"
    },
    {
      "column": "Engine_Temperature",
      "latest_value": 720.9,
      "historical_average": 713.3,
      "historical_median": 713.5,
      "historical_std_dev": 2.5,
      "change_from_average": 7.6,
      "change_percent": 1.065,
      "trend_direction": "STABLE"
    },
    {
      "column": "Exhaust_Gas_Temperature",
      "latest_value": 685.1,
      "historical_average": 681.73,
      "historical_median": 681.25,
      "historical_std_dev": 2.297,
      "change_from_average": 3.37,
      "change_percent": 0.494,
      "trend_direction": "STABLE"
    },
    {
      "column": "Oil_Temperature",
      "latest_value": 102.1,
      "historical_average": 100.01,
      "historical_median": 99.6,
      "historical_std_dev": 1.49,
      "change_from_average": 2.09,
      "change_percent": 2.09,
      "trend_direction": "STABLE"
    },
    {
      "column": "Oil_Pressure",
      "latest_value": 47.9,
      "historical_average": 49.1,
      "historical_median": 49.25,
      "historical_std_dev": 0.438,
      "change_from_average": -1.2,
      "change_percent": -2.444,
      "trend_direction": "STABLE"
    },
    {
      "column": "Engine_Vibration",
      "latest_value": 6.08,
      "historical_average": 5.713,
      "historical_median": 5.68,
      "historical_std_dev": 0.157,
      "change_from_average": 0.367,
      "change_percent": 6.424,
      "trend_direction": "INCREASING"
    },
    {
      "column": "Compressor_Pressure",
      "latest_value": 44.6,
      "historical_average": 44.13,
      "historical_median": 44.3,
      "historical_std_dev": 0.344,
      "change_from_average": 0.47,
      "change_percent": 1.065,
      "trend_direction": "STABLE"
    },
    {
      "column": "Fuel_Flow",
      "latest_value": 2456.8,
      "historical_average": 2427.43,
      "historical_median": 2425.85,
      "historical_std_dev": 7.294,
      "change_from_average": 29.37,
      "change_percent": 1.21,
      "trend_direction": "STABLE"
    },
    {
      "column": "Hydraulic_Pressure",
      "latest_value": 3017.9,
      "historical_average": 3011.3,
      "historical_median": 3018.15,
      "historical_std_dev": 33.517,
      "change_from_average": 6.6,
      "change_percent": 0.219,
      "trend_direction": "STABLE"
    },
    {
      "column": "Engine_RPM",
      "latest_value": 9796.0,
      "historical_average": 9818.4,
      "historical_median": 9813.0,
      "historical_std_dev": 54.276,
      "change_from_average": -22.4,
      "change_percent": -0.228,
      "trend_direction": "STABLE"
    },
    {
      "column": "Risk_Score",
      "latest_value": 77.2,
      "historical_average": 73.43,
      "historical_median": 73.45,
      "historical_std_dev": 1.983,
      "change_from_average": 3.77,
      "change_percent": 5.134,
      "trend_direction": "INCREASING"
    },
    {
      "column": "Remaining_Useful_Life",
      "latest_value": 30.0,
      "historical_average": 35.5,
      "historical_median": 35.5,
      "historical_std_dev": 2.872,
      "change_from_average": -5.5,
      "change_percent": -15.493,
      "trend_direction": "DECREASING"
    }
  ]
}
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    analyzer = AircraftMaintenanceAnalyzer(
        bedrock_client=bedrock_client,
        model_id="amazon.nova-pro-v1:0",
        manual_pdf_path=manual_pdf_path,
        temperature=0.2,
        max_tokens=2000,
    )

    result = analyzer.analyze(engineering_json)
    print(json.dumps(result, indent=2))
