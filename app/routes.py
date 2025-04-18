from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from google.cloud import bigquery
import json
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/query")
async def process_query(
    request: Request,
    openai_key: str = Form(...),
    service_account_json: str = Form(...),
    dataset_name: str = Form(...),
    query: str = Form(...)
):
    try:
        # Configuration BigQuery
        json_data = json.loads(service_account_json)
        credentials_path = "temp_service_account.json"
        with open(credentials_path, "w") as f:
            json.dump(json_data, f)
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        
        client = bigquery.Client()
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "success": "Connexion réussie à BigQuery",
            "openai_key": openai_key,
            "dataset_name": dataset_name,
            "query": query
        })
    
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e),
            "openai_key": openai_key,
            "service_account_json": service_account_json,
            "dataset_name": dataset_name,
            "query": query
        })