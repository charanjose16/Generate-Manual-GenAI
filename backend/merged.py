# UseCase 1
from fastapi import FastAPI, Query, HTTPException  # type: ignore
import pandas as pd  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import os
import dspy  # type: ignore
import logging
from dotenv import load_dotenv  # type: ignore
import base64
from typing import Optional
import numpy as np  # trend-analysis: Added numpy for regression and moving average calculations
 
# Configure logging
logging.basicConfig(level=logging.INFO)
load_dotenv()
 
app = FastAPI()
 
# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Path to the CSV file
file_path = r"C:\Final Regal Rex Nord\Backend\dataset.csv"
 
#############################################
# DSPy Setup for Extended Maintenance Insight Module
#############################################
 
class MaintenanceInsightSignature(dspy.Signature):
    """
    DSPy signature for obtaining a maintenance insight.
    The LM will receive:
    - aggregated_data: the aggregated JSON data for the motor (grouped by date)
    - question: a prompt asking for a maintenance insight, which should instruct the LM to return a JSON object
      with the following keys:
         - risk: one of "low", "moderate", or "high"
         - description: a textual description of the risk or trend (formatted as bullet points)
         - dates: a list of dates (as strings) where anomalies or risk factors were detected
         - ai_suggestions: a bullet-point formatted list of AI suggestions (including any date information as needed)
    """
    aggregated_data: str = dspy.InputField(desc="Aggregated JSON data for the motor")
    question: str = dspy.InputField(desc="Prompt for maintenance insight")
    risk: str = dspy.OutputField(desc="Risk rating: low, moderate, or high")
    description: str = dspy.OutputField(desc="Description of the risk or trend, formatted as bullet points")
    dates: str = dspy.OutputField(desc="List of relevant dates (as a JSON-formatted string)")
    ai_suggestions: str = dspy.OutputField(desc="AI-based suggestions formatted as bullet points")
 
class MaintenanceInsightModule(dspy.Module):
    def __init__(self):
        # Initialize a chain-of-thought module with the extended signature
        self.get_insight = dspy.ChainOfThought(MaintenanceInsightSignature)
   
    def forward(self, aggregated_data: str, question: str):
        result = self.get_insight(aggregated_data=aggregated_data, question=question)
        return {
            "risk": result.risk,
            "description": result.description,
            "dates": result.dates,
            "ai_suggestions": result.ai_suggestions
        }
 
# Initialize the LM for DSPy
dspy_lm = dspy.LM(
    model='azure/gpt-35-turbo',  # Replace with your desired model identifier
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
    temperature=0.2,
    max_tokens=4096,
)
dspy.configure(lm=dspy_lm)
 
# Initialize the extended maintenance insight module
maintenance_insight_module = MaintenanceInsightModule()
 
#############################################
# DSPy Setup for Motor Analytics Module
#############################################
 
class MotorAnalyticsSignature(dspy.Signature):
    """
    DSPy signature for obtaining motor analytics insights.
    The LM will receive:
    - analytics_data: a JSON string containing analytics metrics
    - prompt: a prompt asking for AI-based observations
    It returns:
    - ai_observations: the AI-generated observations formatted accordingly.
    """
    analytics_data: str = dspy.InputField(desc="JSON string of analytics data")
    prompt: str = dspy.InputField(desc="Prompt for motor analytics insights")
    ai_observations: str = dspy.OutputField(desc="AI-based observations in specified format")
 
class MotorAnalyticsModule(dspy.Module):
    def __init__(self):
        self.get_analytics = dspy.ChainOfThought(MotorAnalyticsSignature)
   
    def forward(self, analytics_data: str, prompt: str):
        result = self.get_analytics(analytics_data=analytics_data, prompt=prompt)
        return result.ai_observations
 
# Initialize the motor analytics module
motor_analytics_module = MotorAnalyticsModule()
 
#############################
# Existing Endpoints
#############################
 
@app.get("/api/motors")
def extract_motor_ids():
    try:
        df = pd.read_csv(file_path)
        if "Motor_ID" not in df.columns:
            raise HTTPException(status_code=400, detail="CSV file is missing the 'Motor_ID' column.")
        motor_ids = df["Motor_ID"].unique().tolist()
        return {"motors": motor_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.get("/api/motor-data")
def get_motor_data(
    motor_id: str = Query(..., description="Motor ID to filter data"),
    months: int = Query(..., description="Number of months for filtering (1, 6, 12, 24, 36, 48, 60)")
):
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        filtered_df = df[(df["Timestamp"] >= start_date) & (df["Timestamp"] <= today) & (df["Motor_ID"] == motor_id)]
        if filtered_df.empty:
            return {"message": f"No data available for Motor ID {motor_id} in the past {months} months."}
        return {"motor_data": filtered_df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
#############################################
# Extended Motor Maintenance Insight Endpoint
#############################################
 
@app.get("/api/motor-maintenance")
def get_motor_maintenance_insight(
    motor_id: str = Query(..., description="Motor ID for maintenance insight"),
    months: int = Query(..., description="Number of months for filtering aggregated data (1, 6, 12, 24, 36, 48, 60)")
):
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
   
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        motor_df = df[(df["Timestamp"] >= start_date) & (df["Timestamp"] <= today) & (df["Motor_ID"] == motor_id)]
        if motor_df.empty:
            return {"message": f"No data available for Motor ID {motor_id} in the past {months} months."}
       
        motor_df["Date"] = motor_df["Timestamp"].dt.date
        aggregated_df = motor_df.groupby("Date").size().reset_index(name="record_count")
        aggregated_data_json = aggregated_df.to_json(orient="records", date_format="iso", indent=2)
        logging.info(f"Aggregated data for motor {motor_id}:\n{aggregated_data_json}")
       
        anomaly_prompt = (
            f"Analyze the following aggregated maintenance data for Motor ID {motor_id} "
            f"to detect anomalies in power consumption. Identify unusual spikes or drops, list the specific dates when these anomalies occurred, "
            f"and provide AI-based suggestions for further investigation. Return your result in JSON format with keys: 'risk', 'description', 'dates', and 'ai_suggestions'. "
            f"Format both the 'description' and 'ai_suggestions' as bullet points. Data:\n{aggregated_data_json}"
        )
        anomaly_insight = maintenance_insight_module.forward(
            aggregated_data=aggregated_data_json, question=anomaly_prompt
        )
       
        risk_prompt = (
            f"Analyze the following aggregated maintenance data for Motor ID {motor_id} to determine if the motor is at high risk of failure. "
            f"Identify the dates where risk factors are evident and provide AI-based suggestions for maintenance actions. Return your result in JSON format with keys: "
            f"'risk', 'description', 'dates', and 'ai_suggestions'. Format the 'description' and 'ai_suggestions' fields as bullet points. Data:\n{aggregated_data_json}"
        )
        risk_insight = maintenance_insight_module.forward(
            aggregated_data=aggregated_data_json, question=risk_prompt
        )
       
        predictive_prompt = (
            f"Using the following aggregated maintenance data for Motor ID {motor_id}, perform AI-based predictive failure modeling. "
            f"Forecast potential future failures by identifying trends and listing the relevant dates or date ranges. Additionally, provide AI-based suggestions on how to rectify any defects observed. "
            f"Return your result in JSON format with keys: 'risk', 'description', 'dates', and 'ai_suggestions', ensuring that both 'description' and 'ai_suggestions' are formatted as bullet points. Data:\n{aggregated_data_json}"
        )
        predictive_insight = maintenance_insight_module.forward(
            aggregated_data=aggregated_data_json, question=predictive_prompt
        )
       
        if "Status" in motor_df.columns:
            status_counts = motor_df["Status"].value_counts()
        else:
            status_counts = pd.Series({"Operational": 70, "Maintenance": 20, "Failure": 10})
       
        pie_chart_data = {
            "labels": status_counts.index.tolist(),
            "datasets": [
                {
                    "label": "Motor Status",
                    "data": status_counts.tolist(),
                    "backgroundColor": ["#36A2EB", "#FFCE56", "#FF6384"],
                    "hoverBackgroundColor": ["#36A2EB", "#FFCE56", "#FF6384"]
                }
            ]
        }
       
        return {
            "motor_id": motor_id,
            "maintenance_insights": {
                "anomaly_detection": anomaly_insight,
                "high_failure_risk": risk_insight,
                "predictive_failure_modeling": predictive_insight,
            },
            "motor_status_pie_data": pie_chart_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
#############################################
# New Analytics Endpoint Using DSPy
#############################################
 
@app.get("/api/analytics")
def get_motor_analytics(
    motor_id: str = Query(..., description="Motor ID for analytics"),
    months: int = Query(..., description="Number of months for filtering data (allowed: 1, 6, 12, 24, 36, 48, 60)")
):
    """
    Returns analytics data for a specific motor_id filtered by the number of months,
    and generates AI-based observations using DSPy.
    """
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
 
    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()
        df = df.rename(columns={
            "Timestamp": "timestamp",
            "Motor_ID": "motor_id",
            "Voltage (V)": "voltage",
            "Current (A)": "current",
            "Power (kW)": "power",
            "Frequency (Hz)": "frequency",
            "Power Factor": "power_factor",
            "Torque (Nm)": "torque",
            "RPM": "rpm",
            "Load (%)": "load",  
            "Temperature (Â°C)": "temperature",
            "Humidity (%)": "humidity",
            "Vibration (mm/s)": "vibration",
            "Status": "status"
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["rpm"] = pd.to_numeric(df["rpm"], errors="coerce")
        df["load"] = pd.to_numeric(df["load"], errors="coerce")
        df["vibration"] = pd.to_numeric(df["vibration"], errors="coerce")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dataset not loaded: {e}")
 
    df.columns = df.columns.str.lower()
 
    if "timestamp" not in df.columns:
        raise HTTPException(status_code=500, detail="Timestamp column not found in dataset")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if "motor_id" not in df.columns:
        raise HTTPException(status_code=500, detail="motor_id column not found in dataset")
 
    filtered_df = df[df["motor_id"] == motor_id]
    if filtered_df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for motor_id: {motor_id}")
 
    today = datetime.today()
    start_date = today - relativedelta(months=months)
    filtered_df = filtered_df[(filtered_df["timestamp"] >= start_date) & (filtered_df["timestamp"] <= today)]
    if filtered_df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for motor_id: {motor_id} in the past {months} months")
 
    filtered_data = filtered_df.to_dict(orient="records")
 
    def calculate_averages(data_list, field):
        values = [float(record[field]) for record in data_list if record.get(field)]
        return sum(values) / len(values) if values else 0
     
    try:
        analytics = {
            "voltage": {
                "avg": round(calculate_averages(filtered_data, "voltage"), 2),
                "max": round(max(float(r["voltage"]) for r in filtered_data), 2),
                "min": round(min(float(r["voltage"]) for r in filtered_data), 2)
            },
            "current": {
                "avg": round(calculate_averages(filtered_data, "current"), 2),
                "max": round(max(float(r["current"]) for r in filtered_data), 2),
                "min": round(min(float(r["current"]) for r in filtered_data), 2)
            },
            "power": {
                "avg": round(calculate_averages(filtered_data, "power"), 2),
                "max": round(max(float(r["power"]) for r in filtered_data), 2),
                "min": round(min(float(r["power"]) for r in filtered_data), 2)
            },
            "load": {
                "avg": round(calculate_averages(filtered_data, "load"), 2),
                "max": round(max(float(r["load"]) for r in filtered_data), 2),
                "min": round(min(float(r["load"]) for r in filtered_data), 2)
            },
            "vibration": {
                "avg": round(calculate_averages(filtered_data, "vibration"), 2),
                "max": round(max(float(r["vibration"]) for r in filtered_data), 2),
                "min": round(min(float(r["vibration"]) for r in filtered_data), 2)
            },
            "failures": len([r for r in filtered_data if r["status"] in ["Motor Failure", "Shutdown"]]),
            "period": {
                "start": min(pd.to_datetime(r["timestamp"]) for r in filtered_data).strftime("%Y-%m-%d"),
                "end": max(pd.to_datetime(r["timestamp"]) for r in filtered_data).strftime("%Y-%m-%d")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing analytics: {e}")
 
    prompt = f"""
    You are an AI trained to analyze motor performance data and provide insights. Based on the following data, generate three AI-based observations with recommendations:
    - Voltage: Avg {analytics['voltage']['avg']}V, Max {analytics['voltage']['max']}V, Min {analytics['voltage']['min']}V
    - Current: Avg {analytics['current']['avg']}A, Max {analytics['current']['max']}A, Min {analytics['current']['min']}A
    - Power: Avg {analytics['power']['avg']}W, Max {analytics['power']['max']}W, Min {analytics['power']['min']}W
    - Load: Avg {analytics['load']['avg']}%, Max {analytics['load']['max']}%, Min {analytics['load']['min']}%
    - Vibration: Avg {analytics['vibration']['avg']}, Max {analytics['vibration']['max']}, Min {analytics['vibration']['min']}
    - Failures: {analytics['failures']} incidents
    - Period: {analytics['period']['start']} to {analytics['period']['end']}
    Provide three concise insights in this format:
        Observation: [AI analysis]  
        Insight: [What’s happening]  
        Recommendation: [What action to take]
    """
 
    # Use DSPy for AI observations
    analytics_data_json = json.dumps(analytics)
    ai_observations = motor_analytics_module.forward(analytics_data=analytics_data_json, prompt=prompt)
 
    return {
        "analytics": analytics,
        "ai_observations": ai_observations
    }
   
#############################################
# Trend Analysis Endpoints
#############################################
 
 
 
 
class TrendAnalysisSignature(dspy.Signature):
    """
    DSPy signature for obtaining trend analysis insights.
    The LM will receive:
    - analytics_data: a JSON string containing aggregated or trend data.
    - prompt: a prompt asking for trend analysis, instructing the LM to return a JSON object
      with keys such as 'ai_trend' that include observations and recommendations.
    """
    analytics_data: str = dspy.InputField(desc="JSON string of trend data")
    prompt: str = dspy.InputField(desc="Prompt for trend analysis insights")
    ai_trend: str = dspy.OutputField(desc="AI-generated trend insights with recommendations")
 
class TrendAnalysisModule(dspy.Module):
    def __init__(self):
        self.get_trend = dspy.ChainOfThought(TrendAnalysisSignature)
   
    def forward(self, analytics_data: str, prompt: str):
        result = self.get_trend(analytics_data=analytics_data, prompt=prompt)
        return result.ai_trend
   
trend_analysis_module = TrendAnalysisModule()
 
@app.get("/api/motor-ids")
def get_motor_ids():
    """Returns list of unique motor IDs from the dataset."""
    try:
        df = pd.read_csv(file_path)
        unique_ids = df["Motor_ID"].unique().tolist()
        return {"data": unique_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
 
@app.get("/api/failure-trends")
def get_failure_trends(
    motor_id: str = Query(..., description="Motor ID for filtering data"),
    months: int = Query(..., description="Number of months for filtering (1, 6, 12, 24, 36, 48, 60)")
):
    """Returns failure trends for a specific motor over time with AI-generated trend insights."""
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
   
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        filtered_df = df[df["Motor_ID"] == motor_id]
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        filtered_df = filtered_df[(filtered_df["Timestamp"] >= start_date) & (filtered_df["Timestamp"] <= today)]
        if filtered_df.empty:
            return {"message": f"No data available for Motor ID {motor_id} in the past {months} months."}
       
        failure_status = filtered_df[filtered_df["Status"].isin(["High Vibration", "Overload"])]
        trends = failure_status.groupby(failure_status["Timestamp"].dt.to_period("M")).size()
        trends_list = [{"month": str(k), "count": int(v)} for k, v in trends.items()]
       
        if trends_list:
            trends_sorted = sorted(trends_list, key=lambda x: x["month"])
            x_vals = list(range(len(trends_sorted)))
            y_vals = [item["count"] for item in trends_sorted]
            slope, intercept = np.polyfit(x_vals, y_vals, 1)
            regression = {
                "slope": round(slope, 2),
                "intercept": round(intercept, 2),
                "predicted": [
                    {"month": trends_sorted[i]["month"], "predicted_count": round(slope * i + intercept, 2)}
                    for i in range(len(trends_sorted))
                ]
            }
            if len(y_vals) >= 3:
                moving_avg = np.convolve(y_vals, np.ones(3) / 3, mode="valid")
                moving_average = [
                    {"month": trends_sorted[i + 1]["month"], "moving_avg": round(moving_avg[i], 2)}
                    for i in range(len(moving_avg))
                ]
            else:
                moving_average = []
        else:
            regression = {}
            moving_average = []
       
        # Build a prompt for trend analysis of failure data
        failure_data_json = json.dumps(trends_list)
        prompt = (
            f"Analyze the following failure trend data for Motor ID {motor_id}: {failure_data_json}. "
            f"Identify trends, anomalies, and forecast potential future risks. "
             f"Return your result in JSON format with key 'ai_trend'. containing observations and recommendations in bullet points."
        )
        ai_trend_insight = trend_analysis_module.forward(
            analytics_data=failure_data_json, prompt=prompt
        )
       
        return {
            "data": trends_list,
            "total_failures": len(failure_status),
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "ai_trend_insight": ai_trend_insight,
            "trend_analysis": {
                "regression": regression,
                "moving_average": moving_average
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.get("/api/rpm-vs-load")
def get_rpm_vs_load(
    motor_id: str = Query(..., description="Motor ID for filtering data"),
    months: int = Query(..., description="Number of months for filtering (1, 6, 12, 24, 36, 48, 60)")
):
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        for col in ["Motor_ID", "Timestamp", "RPM", "Load (%)"]:
            if col not in df.columns:
                raise HTTPException(status_code=500, detail=f"Missing expected column '{col}' in dataset.")
        filtered_df = df[df["Motor_ID"] == motor_id]
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        filtered_df = filtered_df[(filtered_df["Timestamp"] >= start_date) & (filtered_df["Timestamp"] <= today)]
        if filtered_df.empty:
            return {"message": f"No data available for Motor ID {motor_id} in the past {months} months."}
        filtered_df["Month"] = filtered_df["Timestamp"].dt.to_period("M").astype(str)
        grouped = filtered_df.groupby("Month").agg(
            avg_rpm=("RPM", "mean"),
            avg_load=("Load (%)", "mean")
        ).reset_index()
        grouped["avg_rpm"] = grouped["avg_rpm"].round(2)
        grouped["avg_load"] = grouped["avg_load"].round(2)
       
        # Build aggregated data JSON and prompt for RPM vs. Load trend analysis
        aggregated_data = grouped.to_dict(orient="records")
        aggregated_data_json = json.dumps(aggregated_data)
        prompt = (
            f"Analyze the following monthly aggregated RPM and Load data for Motor ID {motor_id}: {aggregated_data_json}. "
            f"Identify any trends or shifts in performance ."
             f"Return your result in JSON format with key 'ai_trend'. containing observations and recommendations in bullet points."
        )
        ai_trend_insight = trend_analysis_module.forward(
            analytics_data=aggregated_data_json, prompt=prompt
        )
       
        return {
            "data": aggregated_data,
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "ai_trend_insight": ai_trend_insight
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 
@app.get("/api/temp-vs-vibration")
def get_temp_vs_vibration(
    motor_id: str = Query(..., description="Motor ID for filtering data"),
    months: int = Query(..., description="Number of months for filtering (1, 6, 12, 24, 36, 48, 60)")
):
    allowed_months = [1, 6, 12, 24, 36, 48, 60]
    if months not in allowed_months:
        raise HTTPException(status_code=400, detail=f"Invalid months parameter. Allowed values: {allowed_months}")
    try:
        df = pd.read_csv(file_path, parse_dates=["Timestamp"])
        filtered_df = df[df["Motor_ID"] == motor_id]
        today = datetime.today()
        start_date = today - relativedelta(months=months)
        filtered_df = filtered_df[(filtered_df["Timestamp"] >= start_date) & (filtered_df["Timestamp"] <= today)]
        if filtered_df.empty:
            return {"message": f"No data available for Motor ID {motor_id} in the past {months} months."}
        temp_vib_data = filtered_df[["Temperature (°C)", "Vibration (mm/s)", "Timestamp", "Status"]].copy()
        temp_vib_data["Timestamp"] = temp_vib_data["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        correlation = None
        if len(filtered_df) > 1:
            correlation = round(filtered_df[["Temperature (°C)", "Vibration (mm/s)"]].corr().iloc[0, 1], 3)
       
        # Build statistics for trend analysis
        stats = {
            "avg_temperature": round(filtered_df["Temperature (°C)"].mean(), 2),
            "avg_vibration": round(filtered_df["Vibration (mm/s)"].mean(), 2),
            "correlation": correlation,
            "period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            }
        }
        stats_json = json.dumps(stats)
        prompt = (
            f"Analyze the following temperature and vibration statistics for Motor ID {motor_id}: {stats_json}. "
            f"Provide an AI-based trend analysis that explains the relationship, highlights any anomalies, and recommends monitoring actions. "
            f"Return your result in JSON format with key 'ai_trend'. containing observations and recommendations in bullet points."
        )
        ai_trend_insight = trend_analysis_module.forward(
            analytics_data=stats_json, prompt=prompt
        )
       
        return {
            "data": temp_vib_data.to_dict(orient="records"),
            "statistics": stats,
            "ai_trend_insight": ai_trend_insight
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# UseCase 2

import os
import logging
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, JSONResponse
from io import BytesIO
from dotenv import load_dotenv
import dspy
from dspy import InputField, OutputField
from dspy import Example, Signature, ChainOfThought, Predict
from reportlab.lib.pagesizes import letter, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import re
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import json
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Path to the SSL certificate file
CERTIFICATE_PATH = os.path.join(os.path.dirname(__file__), "huggingface.co.crt")

# Set the environment variable for SSL verification
os.environ["REQUESTS_CA_BUNDLE"] = CERTIFICATE_PATH

# Pydantic model for input validation
class ProductData(BaseModel):
    product_category: str = Field(
        description="Category of the product (e.g., 'Electronics', 'Appliances', 'Tools')"
    )
    rag_source: UploadFile = File(..., description="Uploaded PDF file for RAG content retrieval")
    language: str = Field(
        default="en",
        description="Target language for the manual (e.g., 'en', 'es', 'fr', 'de', 'it')"
    )

# Configure DSPy with Azure OpenAI
try:
    lm = dspy.LM(
        model="azure/" + os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
        temperature=0.7,
        max_tokens=4096,
    )
    dspy.configure(lm=lm)
    logger.info("DSPy configured successfully with Azure OpenAI.")
except Exception as e:
    logger.error(f"Failed to configure DSPy: {str(e)}")
    raise RuntimeError(f"Failed to configure DSPy: {str(e)}")

# Define signatures for content generation
class GenerateContent(Signature):
    """Generate structured content for a specific section in the specified language."""
    section_title: str = InputField(desc="Title of the section")
    prompt: str = InputField(desc="Prompt for generating content")
    language: str = InputField(desc="Target language for content generation")
    output: str = OutputField(desc="Generated content in specified language")

def get_language_texts(language):
    """Return language-specific texts for UI elements."""
    texts = {
        "en": {
            "title": "USER MANUAL FOR",
            "toc": "Table of Contents",
            "page": "Page",
            "introduction": "Introduction",
            "key_features": "Key Features",
            "technical_specifications": "Technical Specifications",
            "safety_information": "Safety Information",
            "setup_instructions": "Setup Instructions",
            "operation_instructions": "Operation Instructions",
            "maintenance_and_care": "Maintenance and Care",
            "troubleshooting": "Troubleshooting",
            "faq": "FAQ",
            "warranty_information": "Warranty Information"
        },
        # Other languages...
        "es": {
            "title": "MANUAL DE USUARIO PARA",
            "toc": "Índice de Contenidos",
            "page": "Página",
            "introduction": "Introducción",
            "key_features": "Características Principales",
            "technical_specifications": "Especificaciones Técnicas",
            "safety_information": "Información de Seguridad",
            "setup_instructions": "Instrucciones de Configuración",
            "operation_instructions": "Instrucciones de Operación",
            "maintenance_and_care": "Mantenimiento y Cuidado",
            "troubleshooting": "Solución de Problemas",
            "faq": "Preguntas Frecuentes",
            "warranty_information": "Información de Garantía"
        },
        "fr": {
            "title": "MANUEL D'UTILISATION POUR",
            "toc": "Table des Matières",
            "page": "Page",
            "introduction": "Introduction",
            "key_features": "Caractéristiques Clés",
            "technical_specifications": "Spécifications Techniques",
            "safety_information": "Informations de Sécurité",
            "setup_instructions": "Instructions d'Installation",
            "operation_instructions": "Instructions d'Utilisation",
            "maintenance_and_care": "Maintenance et Entretien",
            "troubleshooting": "Dépannage",
            "faq": "FAQ",
            "warranty_information": "Informations sur la Garantie"
        },
        "de": {
            "title": "BENUTZERHANDBUCH FÜR",
            "toc": "Inhaltsverzeichnis",
            "page": "Seite",
            "introduction": "Einführung",
            "key_features": "Hauptmerkmale",
            "technical_specifications": "Technische Spezifikationen",
            "safety_information": "Sicherheitshinweise",
            "setup_instructions": "Einrichtungsanweisungen",
            "operation_instructions": "Betriebsanweisungen",
            "maintenance_and_care": "Wartung und Pflege",
            "troubleshooting": "Fehlerbehebung",
            "faq": "FAQ",
            "warranty_information": "Garantieinformationen"
        },
        "it": {
            "title": "MANUALE UTENTE PER",
            "toc": "Indice dei Contenuti",
            "page": "Pagina",
            "introduction": "Introduzione",
            "key_features": "Caratteristiche Principali",
            "technical_specifications": "Specifiche Tecniche",
            "safety_information": "Informazioni sulla Sicurezza",
            "setup_instructions": "Istruzioni di Installazione",
            "operation_instructions": "Istruzioni di Funzionamento",
            "maintenance_and_care": "Manutenzione e Cura",
            "troubleshooting": "Risoluzione dei Problemi",
            "faq": "FAQ",
            "warranty_information": "Informazioni sulla Garanzia"
        }
    }
    return texts.get(language, texts["en"])

def load_and_index_pdf(pdf_path):
    """Load PDF content and create a FAISS index for RAG."""
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} documents from PDF.")
        
        if not documents:
            logger.error("No documents found in the uploaded PDF.")
            raise HTTPException(status_code=400, detail="Uploaded PDF contains no valid text.")
        
        # Split text into smaller chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(documents)
        
        if not texts:
            logger.error("Failed to split documents into chunks.")
            raise HTTPException(status_code=400, detail="Failed to process PDF content.")
        
        # Generate embeddings and create FAISS index
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vector_store = FAISS.from_documents(texts, embeddings)
        return vector_store
    except Exception as e:
        logger.error(f"Error loading and indexing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")

def retrieve_content(vector_store, query):
    """Retrieve relevant content using RAG."""
    try:
        docs = vector_store.similarity_search(query, k=5)  # Retrieve top 5 matches
        
        if not docs:
            logger.warning("No relevant content found for query: %s", query)
            return "No relevant content found."
        
        # Ensure all documents have valid `page_content`
        retrieved_content = "\n".join([doc.page_content for doc in docs if hasattr(doc, 'page_content')])
        
        if not retrieved_content.strip():
            logger.warning("Retrieved content is empty for query: %s", query)
            return "No relevant content found."
        
        return retrieved_content
    except Exception as e:
        logger.error(f"Error retrieving content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve content: {str(e)}")

def generate_content_prompts(product_data, language, retrieved_content):
    """
    Generate language-specific prompts for each section using the retrieved content 
    as additional context. This helps the language model generate more relevant output.
    """
    product_category = product_data["product_category"]
    language_texts = get_language_texts(language)
    
    # Language instruction template
    language_instruction = f"""
    You are a professional technical writer creating content in {language}.
    Instructions:
    1. Generate ALL content in {language} language.
    2. Maintain technical accuracy in the translation.
    3. Use an appropriate formal tone for user manuals in {language}.
    4. Preserve all technical terms and measurements.
    5. Keep the same structured format as the original.
    6. Ensure all headings and subheadings are in {language}.
    """
    
    # Append retrieved content for context
    context_text = f"\n\nRelevant context extracted from the provided sources:\n{retrieved_content}\n\n"
    
    return {
        language_texts["introduction"]: f"{language_instruction}{context_text}Task: Write a structured introduction in {language}.",
        language_texts["key_features"]: f"{language_instruction}{context_text}Task: Describe the key features in {language}.",
        language_texts["technical_specifications"]: f"{language_instruction}{context_text}Task: Present technical specifications in {language}.",
        language_texts["safety_information"]: f"{language_instruction}{context_text}Task: Create safety guidelines in {language}.",
        language_texts["setup_instructions"]: f"{language_instruction}{context_text}Task: Write setup instructions in {language}.",
        language_texts["operation_instructions"]: f"{language_instruction}{context_text}Task: Create operation guidelines in {language}.",
        language_texts["maintenance_and_care"]: f"{language_instruction}{context_text}Task: Write maintenance procedures in {language}.",
        language_texts["troubleshooting"]: f"{language_instruction}{context_text}Task: Create a troubleshooting guide in {language}.",
        language_texts["faq"]: f"{language_instruction}{context_text}Task: Generate FAQs in {language}.",
        language_texts["warranty_information"]: f"{language_instruction}{context_text}Task: Write warranty details in {language}."
    }

def clean_content(text):
    """Clean special characters and formatting from text."""
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'\[.*?\]|\{.*?\}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def generate_pdf(product_data, content):
    """Generate PDF document with enhanced styling and error handling."""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        styles = getSampleStyleSheet()
        language_texts = get_language_texts(product_data.get("language", "en"))
        elements = []
        
        # Title
        elements.append(Paragraph(
            f"{language_texts['title']} {product_data['product_category']}",
            styles['Title']
        ))
        elements.append(Spacer(1, 0.5 * inch))
        
        # Table of Contents
        elements.append(Paragraph(language_texts['toc'], styles['Heading1']))
        toc_data = [[language_texts['toc'], language_texts['page']]]
        page_number = 2
        for section in content.keys():
            clean_section = clean_content(section)
            toc_data.append([clean_section, str(page_number)])
            page_number += 1
        toc_table = Table(toc_data, colWidths=[400, 100])
        toc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 13),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('TOPPADDING', (0, 0), (-1, 0), 15),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(toc_table)
        elements.append(PageBreak())
        
        # Content sections
        for section, section_content in content.items():
            clean_section = clean_content(section)
            elements.append(Paragraph(clean_section, styles['Heading2']))
            cleaned_content = clean_content(section_content)
            paragraphs = cleaned_content.split('\n')
            for paragraph in paragraphs:
                if paragraph.strip():
                    elements.append(Paragraph(paragraph.strip(), styles['Normal']))
            elements.append(Spacer(1, 0.1 * inch))
            elements.append(PageBreak())
        
        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )

# --- New Helper Functions for Scraping ---

def scrape_product_data(url):
    """
    Scrape product data from the given URL using requests and BeautifulSoup.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/"
        }
        response = requests.get(url, headers=headers, verify=False)  # Disable SSL verification
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract product name
        product_name = "Unknown Product"
        h1_tag = soup.find('h1')
        if h1_tag:
            product_name = h1_tag.get_text(strip=True)

        # Extract summary (if available)
        summary = ""
        summary_div = soup.find('div', class_='product-summary')
        if summary_div:
            summary = summary_div.get_text(strip=True)

        # Extract Key Features
        key_features = []
        key_features_container = soup.find('div', class_='product-info')
        if key_features_container:
            feature_list = key_features_container.find('ul')
            if feature_list:
                features = feature_list.find_all('li')
                for feature in features:
                    key_features.append(feature.get_text(strip=True))

        # Extract Technical Specifications
        technical_specs = {}
        tech_specs_div = soup.find('div', id='tab-0')
        if tech_specs_div:
            tech_specs_table = tech_specs_div.find('table', class_='specifications-table')
            if tech_specs_table:
                for row in tech_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 4:  # Two key-value pairs per row
                        key1 = cols[0].get_text(strip=True).rstrip(":")
                        value1 = cols[1].get_text(strip=True)
                        key2 = cols[2].get_text(strip=True).rstrip(":")
                        value2 = cols[3].get_text(strip=True)
                        technical_specs[key1] = value1
                        technical_specs[key2] = value2

        # Extract General Specifications
        general_specs = {}
        general_specs_div = soup.find('div', id='tab-1')
        if general_specs_div:
            general_specs_table = general_specs_div.find('table', class_='specifications-table')
            if general_specs_table:
                for row in general_specs_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 2:  # One key-value pair per row
                        key = cols[0].get_text(strip=True).rstrip(":")
                        value = cols[1].get_text(strip=True)
                        general_specs[key] = value

        return {
            "product_name": product_name,
            "summary": summary,
            "key_features": key_features,
            "technical_specifications": technical_specs,
            "general_specifications": general_specs
        }
    except Exception as e:
        logger.error(f"Error scraping product data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape product data: {str(e)}")

def get_product_link(selected_item):
    """
    Look up the product link from the products JSON data based on the selected item.
    """
    for product in products_data.get("products", []):
        for subproduct in product.get("subproducts", []):
            for item in subproduct.get("sub_subproducts", []):
                if item.get("sub_subproduct_name") == selected_item:
                    return item.get("sub_subproduct_link")
    return None

# --- End of New Helper Functions ---

@app.post("/generate-manual")
async def generate_manual(
    product_category: str = Form(...),
    rag_source: UploadFile = File(...),
    language: str = Form(...)
):
    """Generate a user manual PDF based on product category and RAG content."""
    try:
        logger.info(f"Starting manual generation for category: {product_category} in {language}")

        # --- Step 1: Scrape product data based on the selected item ---
        product_link = get_product_link(product_category)
        if not product_link:
            logger.error("Product link not found for the selected item.")
            raise HTTPException(status_code=400, detail="Product link not found for the selected item.")
        logger.info(f"Scraping product data from: {product_link}")
        scraped_data = scrape_product_data(product_link)
        # Prepare scraped context text
        scraped_context = f"Product Name: {scraped_data['product_name']}\n"
        scraped_context += f"Summary: {scraped_data['summary']}\n"
        scraped_context += f"Key Features: {', '.join(scraped_data['key_features'])}\n"
        scraped_context += "Technical Specifications:\n"
        for key, value in scraped_data['technical_specifications'].items():
            scraped_context += f" - {key}: {value}\n"
        scraped_context += "General Specifications:\n"
        for key, value in scraped_data['general_specifications'].items():
            scraped_context += f" - {key}: {value}\n"

        # --- Step 2: Process PDF if uploaded (for additional context) ---
        pdf_retrieved_content = ""
        pdf_path = None
        if rag_source:
            pdf_path = f"temp_{rag_source.filename}"
            with open(pdf_path, "wb") as buffer:
                buffer.write(await rag_source.read())
            logger.info(f"Loading and indexing PDF from path: {pdf_path}")
            vector_store = load_and_index_pdf(pdf_path)
            query = f"User manual content for {product_category}"
            logger.info(f"Retrieving PDF content for query: {query}")
            pdf_retrieved_content = retrieve_content(vector_store, query)
            # Clean up temporary file
            os.remove(pdf_path)

        # --- Step 3: Combine contexts ---
        combined_context = scraped_context
        if pdf_retrieved_content.strip() and pdf_retrieved_content != "No relevant content found.":
            combined_context += "\nRelevant context extracted from PDF:\n" + pdf_retrieved_content

        logger.info(f"Combined context for manual generation: {combined_context}")

        # --- Step 4: Generate prompts for each section ---
        content_prompts = generate_content_prompts({
            "product_category": product_category
        }, language, combined_context)
        
        # --- Step 5: Generate content using DSPy ---
        generate_content = Predict(GenerateContent)
        generated_content = {}
        for section, prompt in content_prompts.items():
            logger.info(f"Generating content for section: {section} in {language}")
            result = generate_content(
                section_title=section,
                prompt=prompt,
                language=language,
                temperature=0.7,
                max_tokens=1000
            )
            
            if not result.output.strip():
                logger.warning(f"No content generated for section: {section}")
                generated_content[section] = "No content available."
            else:
                generated_content[section] = result.output
        
        # --- Step 6: Generate PDF ---
        pdf_buffer = generate_pdf({
            "product_category": product_category,
            "language": language
        }, generated_content)
        
        filename = f"user_manual_{product_category}_{language}.pdf"
        response = StreamingResponse(pdf_buffer, media_type="application/pdf")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error generating manual: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
PRODUCTS_FILE_PATH = os.path.join(os.path.dirname(__file__), "product_names.json")

# Load the JSON file with product data
with open(PRODUCTS_FILE_PATH, "r") as file:
    products_data = json.load(file)

# API endpoint to serve product data
@app.get("/api/products")
async def get_products():
    return JSONResponse(content={"products": products_data.get("products", [])})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app)