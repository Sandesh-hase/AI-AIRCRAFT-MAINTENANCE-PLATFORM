"""
Simple FastAPI backend for the aircraft maintenance platform.

This file exposes three lightweight endpoints:
1. Health check
2. Aircraft analytics from an uploaded Excel file
3. Maintenance prediction from analytics output
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import boto3
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.aircraft_maintenance.bedrock_maintenance_analyzer import AircraftMaintenanceAnalyzer
from src.aircraft_maintenance.engineering_analytics import AircraftEngineeringAnalytics

# Load environment variables from .env file
load_dotenv()


app = FastAPI(
    title="Aircraft Maintenance API",
    version="1.0.0",
    description="Simple API for aircraft engineering analytics and maintenance reporting",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
def root() -> dict[str, str]:
    """Simple root endpoint so the frontend can confirm the backend is live."""
    return {"status": "ok", "service": "aircraft-maintenance-api", "message": "Backend is running"}


@app.get("/testing/health")
def health_check() -> dict[str, str]:
    """Simple health check endpoint for smoke testing."""
    return {"status": "ok", "service": "aircraft-maintenance-api"}


@app.post("/aircraft/analytics")
async def aircraft_analytics(
    excel_file: UploadFile = File(...),
) -> dict[str, Any]:
    """
    Generate engineering analytics from an uploaded Excel file.

    This endpoint keeps the input simple by requiring only the Excel upload.
    It uses the default sheet and the first available aircraft in the file.
    """
    if not excel_file.filename:
        raise HTTPException(status_code=400, detail="Please upload an Excel file.")

    if not excel_file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid Excel file (.xlsx or .xls).",
        )

    temp_path: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(excel_file.filename).suffix,
        ) as temp_file:
            content = await excel_file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        analytics = AircraftEngineeringAnalytics(
            excel_path=temp_path,
            sheet_name=0,
        )
        analytics.load_dataset()

        aircraft_list = analytics.list_aircraft()
        if not aircraft_list:
            raise ValueError("No aircraft data found in the uploaded file.")

        first_aircraft = aircraft_list[0]
        summary = analytics.generate_summary(
            aircraft_id=first_aircraft,
            history_window=10,
        )
        return {
            "message": "Analytics generated successfully",
            "aircraft_id": first_aircraft,
            "summary": summary.to_dict(),
        }

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/aircraft/maintenance-prediction")
def maintenance_prediction(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a maintenance prediction report from the analytics output.

    The request body can be the full response from the analytics endpoint,
    and this function will extract the analytics payload automatically.
    """
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Please send the analytics output from the second API.")

    if isinstance(payload.get("summary"), dict):
        engineering_json = payload["summary"]
    elif isinstance(payload.get("engineering_json"), dict):
        engineering_json = payload["engineering_json"]
    else:
        engineering_json = payload

    if not isinstance(engineering_json, dict) or not engineering_json:
        raise HTTPException(status_code=400, detail="The analytics payload is empty or invalid.")

    base_dir = Path(__file__).resolve().parent
    manual_pdf_path = str(base_dir / "data" / "AeroTech_ATX200_Maintenance_Manual.pdf")

    if not Path(manual_pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"Maintenance manual not found at: {manual_pdf_path}.",
        )

    try:
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")

        boto3_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": aws_region,
        }
        
        # Only add explicit credentials if they are provided in .env
        # Otherwise, boto3 will fall back to default credential providers (e.g., ~/.aws/credentials)
        if aws_access_key and aws_access_key != "YOUR_ACCESS_KEY" and aws_secret_key and aws_secret_key != "YOUR_SECRET_KEY":
            boto3_kwargs["aws_access_key_id"] = aws_access_key
            boto3_kwargs["aws_secret_access_key"] = aws_secret_key

        bedrock_client = boto3.client(**boto3_kwargs)

        analyzer = AircraftMaintenanceAnalyzer(
            bedrock_client=bedrock_client,
            model_id=bedrock_model_id,
            manual_pdf_path=manual_pdf_path,
            temperature=0.2,
            max_tokens=2_000,
        )

        report = analyzer.analyze(engineering_json)
        return {"success": True, "report": report}

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Maintenance prediction failed: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
