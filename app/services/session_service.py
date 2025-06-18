from fastapi import Request, Response
import uuid
sessions = {}

def get_or_create_session(request: Request, response: Response = None):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"step": 1, "datasets": [], "tables": []}
        if response:
            response.set_cookie(key="session_id", value=session_id)
    return sessions[session_id]
