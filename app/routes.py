from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from google.cloud import bigquery
import json
import os
import pandas as pd

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
        # Charger les credentials
        json_data = json.loads(service_account_json)
        credentials_path = "temp_service_account.json"
        with open(credentials_path, "w") as f:
            json.dump(json_data, f)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        client = bigquery.Client()

        # Exécuter la requête SQL brute
        query_job = client.query(query)
        df = query_job.to_dataframe()
        df_json = df.to_dict(orient="records")
        df_columns = list(df.columns)

        # Détection auto d'un graphique (si 2 colonnes max avec une numérique)
        visualize = False
        chart_type = None
        x_axis = None
        y_axis = None
        title = "Visualisation"

        if len(df.columns) == 2:
            x_axis, y_axis = df.columns[0], df.columns[1]
            if pd.api.types.is_numeric_dtype(df[y_axis]):
                visualize = True
                chart_type = "bar"

        return templates.TemplateResponse("index.html", {
            "request": request,
            "openai_key": openai_key,
            "dataset_name": dataset_name,
            "query": query,
            "data": df_json,
            "columns": df_columns,
            "visualize": visualize,
            "chart_type": chart_type,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "title": title
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
