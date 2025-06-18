from fastapi import APIRouter, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.services.session_service import get_or_create_session
from app.services.bigquery_service import BigQueryService
from app.services.llm_service import LLMService
import json
import logging

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("/", response_class=HTMLResponse)
async def step1(request: Request):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step1.html", {"request": request, "step": 1, "session": session})


@router.post("/upload-json")
async def upload_json(request: Request, file: UploadFile = File(...)):
    response = RedirectResponse("/step2", status_code=303)
    session = get_or_create_session(request, response)  # ✅ Important

    try:
        json_data = json.loads(await file.read())
        bq = BigQueryService(json_data)
        datasets = bq.get_datasets()
        default_dataset = datasets[0] if datasets else ""
        tables = bq.get_tables(default_dataset) if default_dataset else []

        session.update({
            "client_config": json_data,
            "datasets": datasets,
            "dataset": default_dataset,
            "tables": tables,
            "selected_table": tables[0] if tables else "",
            "step": 2
        })

        logger.info(f"✅ Datasets chargés : {datasets}")
        logger.info(f"📄 Tables pour {default_dataset} : {tables}")
        return response

    except Exception as e:
        logger.error(f"❌ Erreur dans upload-json : {e}")
        return templates.TemplateResponse("step1.html", {
            "request": request,
            "error": str(e),
            "step": 1,
            "session": session
        })


@router.get("/step2", response_class=HTMLResponse)
async def step2(request: Request):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step2.html", {
        "request": request,
        "step": 2,
        "datasets": session.get("datasets", []),
        "tables": session.get("tables", []),
        "selected_dataset": session.get("dataset", ""),
        "selected_table": session.get("selected_table", ""),
        "project_name": session.get("project_name", "")
    })


@router.get("/api/tables")
async def get_tables_api(request: Request):
    session = get_or_create_session(request)
    dataset = request.query_params.get("dataset")

    if not dataset:
        return JSONResponse({"error": "Paramètre dataset manquant"}, status_code=400)

    try:
        bq = BigQueryService(session["client_config"])
        tables = bq.get_tables(dataset)
        session["tables"] = tables
        return JSONResponse({"tables": tables})
    except Exception as e:
        logger.error(f"❌ Erreur API /api/tables : {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/select-dataset")
async def select_dataset(
    request: Request,
    project_name: str = Form(...),
    dataset: str = Form(...),
    table: str = Form(...)
):
    session = get_or_create_session(request)
    try:
        bq = BigQueryService(session["client_config"])
        tables = bq.get_tables(dataset)

        session.update({
            "project_name": project_name,
            "dataset": dataset,
            "tables": tables,
            "selected_table": table,
            "step": 3
        })

        logger.info(f"✅ Dataset sélectionné : {dataset}")
        logger.info(f"📄 Tables disponibles : {tables}")
        return RedirectResponse("/step3", status_code=303)

    except Exception as e:
        logger.error(f"❌ Erreur dans select-dataset : {e}")
        return RedirectResponse("/step2", status_code=303)


@router.get("/step3", response_class=HTMLResponse)
async def step3(request: Request):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step3.html", {
        "request": request,
        "step": 3,
        "session": session
    })


@router.post("/set-api-key")
async def set_api_key(request: Request, api_key: str = Form(...)):
    session = get_or_create_session(request)
    session.update({"api_key": api_key, "step": 4})
    return RedirectResponse("/step4", status_code=303)


@router.get("/step4", response_class=HTMLResponse)
async def step4(request: Request):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step4.html", {
        "request": request,
        "step": 4,
        "session": session
    })


@router.post("/process-query")
async def process_query(request: Request, prompt: str = Form(...)):
    session = get_or_create_session(request)
    try:
        bq = BigQueryService(session["client_config"])
        llm = LLMService(session["api_key"])
        selected_table = session.get("selected_table")
        tables_schema = bq.describe_schema(session["dataset"])

        structured_prompt = llm.build_prompt(
            prompt,
            session["dataset"],
            tables_schema,
            selected_table  # ✅ table sélectionnée imposée
        )

       # logger.info(f"🧠 Prompt structuré :\n{structured_prompt}")

        response_json = llm.query(structured_prompt)

        logger.info(f"\n\n📊 Requête SQL générée :\n {response_json.get('query')}")

        df = bq.run_query(response_json["query"])

        return templates.TemplateResponse("step4.html", {
            "request": request,
            "result": {
                "query": response_json["query"],
                "data": df.to_dict(orient="records"),
                "columns": list(df.columns)
                # ❌ plus besoin de visualize/chart_type/axes
            },
            "step": 4,
            "session": session
        })
    except Exception as e:
        logger.error(f"❌ Erreur dans process-query : {e}")
        return templates.TemplateResponse("step4.html", {
            "request": request,
            "error": str(e),
            "step": 4,
            "session": session
        })
