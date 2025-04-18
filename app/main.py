from fastapi import FastAPI, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.cloud import bigquery
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
import json
import os
from typing import Dict
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


sessions: Dict[str, dict] = {}

def get_or_create_session(request: Request, response: Response = None) -> dict:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "step": 1,
            "client_config": None,
            "datasets": [],
            "project_name": "",
            "dataset": "",
            "tables": [],
            "api_key": ""
        }
        if response:
            response.set_cookie(key="session_id", value=session_id)
    return sessions[session_id]


def load_bigquery_config(json_data: dict) -> bigquery.Client:
    credentials_path = "temp_credentials.json"
    with open(credentials_path, "w") as f:
        json.dump(json_data, f)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    return bigquery.Client()

def get_datasets(client: bigquery.Client) -> list:
    return [dataset.dataset_id for dataset in client.list_datasets()]

def get_tables(client: bigquery.Client, dataset_id: str) -> list:
    return [table.table_id for table in client.list_tables(dataset_id)]

# Middleware
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    response = await call_next(request)
    if not request.cookies.get("session_id"):
        session_id = str(uuid.uuid4())
        response.set_cookie(key="session_id", value=session_id)
    return response

# Routes
@app.get("/", response_class=HTMLResponse)
async def step1(request: Request):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step1.html", {
        "request": request,
        "step": 1,
        "error": None,
        "session": session
    })

@app.post("/upload-json")
async def handle_json_upload(request: Request, file: UploadFile = File(...)):
    response = RedirectResponse(url="/step2", status_code=303)
    session = get_or_create_session(request, response)
    
    try:
        contents = await file.read()
        json_data = json.loads(contents)
        client = load_bigquery_config(json_data)
        
        session.update({
            "client_config": json_data,
            "datasets": get_datasets(client),
            "step": 2
        })
        
        return response
    except Exception as e:
        return templates.TemplateResponse("step1.html", {
            "request": request,
            "step": 1,
            "error": f"Erreur: {str(e)}",
            "session": session
        })

@app.get("/step2", response_class=HTMLResponse)
async def step2(request: Request):
    session = get_or_create_session(request)
    if session.get("step", 1) < 2:
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("step2.html", {
        "request": request,
        "step": 2,
        "datasets": session.get("datasets", []),
        "session": session
    })

@app.post("/select-dataset")
async def select_dataset(
    request: Request,
    project_name: str = Form(...),
    dataset: str = Form(...)
):
    response = RedirectResponse(url="/step3", status_code=303)
    session = get_or_create_session(request, response)
    
    try:
        client = load_bigquery_config(session["client_config"])
        tables = get_tables(client, dataset)
        
        session.update({
            "project_name": project_name,
            "dataset": dataset,
            "tables": tables,
            "step": 3
        })
        
        return response
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return RedirectResponse(url="/step2", status_code=303)

@app.get("/step3", response_class=HTMLResponse)
async def step3(request: Request):
    session = get_or_create_session(request)
    if session.get("step", 1) < 3:
        return RedirectResponse(url="/step2", status_code=303)
    
    return templates.TemplateResponse("step3.html", {
        "request": request,
        "step": 3,
        "session": session
    })

@app.post("/set-api-key")
async def set_api_key(request: Request, api_key: str = Form(...)):
    response = RedirectResponse(url="/step4", status_code=303)
    session = get_or_create_session(request, response)
    session.update({
        "api_key": api_key,
        "step": 4
    })
    return response

@app.get("/step4", response_class=HTMLResponse)
async def step4(request: Request):
    session = get_or_create_session(request)
    if session.get("step", 1) < 4:
        return RedirectResponse(url="/step3", status_code=303)
    
    return templates.TemplateResponse("step4.html", {
        "request": request,
        "step": 4,
        "result": None,
        "session": session
    })

@app.post("/process-query")
async def process_query(request: Request, prompt: str = Form(...)):
    session = get_or_create_session(request)
    

    if not session.get("api_key"):
        return error_response(request, "Clé API OpenAI manquante")
    
    if not session.get("dataset"):
        return error_response(request, "Aucun dataset sélectionné")

    try:
        client = load_bigquery_config(session["client_config"])
        llm = ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=session["api_key"])
        
        tables_info = []
        for table_name in get_tables(client, session["dataset"]):
            table_ref = client.dataset(session["dataset"]).table(table_name)
            table = client.get_table(table_ref)
            schema_info = {
                "name": table_name,
                "columns": [{"name": field.name, "type": field.field_type} for field in table.schema]
            }
            tables_info.append(schema_info)
        
        schema_context = "\n".join(
            f"Table {table['name']} (Colonnes: {', '.join(col['name'] for col in table['columns'])})"
            for table in tables_info
        )
        
        selection_prompt = f"""
        Contexte des tables disponibles:
        {schema_context}

        Question: '{prompt}'
        
        Quelle est la table la plus appropriée pour répondre à cette question?
        Réponds uniquement avec le nom de la table choisie.
        """
        
        selected_table = (await llm.ainvoke(selection_prompt)).content.strip()
        sqlalchemy_url = f'bigquery://{session["project_name"]}/{session["dataset"]}?credentials_path={os.getenv("GOOGLE_APPLICATION_CREDENTIALS")}'
        db = SQLDatabase.from_uri(sqlalchemy_url)
        
        agent = create_sql_agent(
            llm=llm,
            toolkit=SQLDatabaseToolkit(db=db, llm=llm),
            verbose=True
        )
        
        result = agent.invoke({"input": prompt})

        return templates.TemplateResponse("step4.html", {
            "request": request,
            "step": 4,
            "result": {
                "selected_table": selected_table,
                "tables_info": tables_info,
                "response": json.dumps(result, indent=2, ensure_ascii=False)
            },
            "session": session
        })

    except Exception as e:
        return error_response(request, f"Erreur: {str(e)}")

def error_response(request, message):
    session = get_or_create_session(request)
    return templates.TemplateResponse("step4.html", {
        "request": request,
        "step": 4,
        "error": message,
        "session": session
    })
@app.get("/api/tables")
async def get_tables_api(request: Request):
    dataset = request.query_params.get("dataset")
    session = get_or_create_session(request)
    
    if not dataset:
        return JSONResponse({"error": "Paramètre dataset manquant"}, status_code=400)
    
    try:
        client = load_bigquery_config(session["client_config"])
        tables = get_tables(client, dataset)
        return JSONResponse({"tables": tables})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)