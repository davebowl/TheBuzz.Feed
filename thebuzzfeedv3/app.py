import os
import shutil
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (
    FastAPI,
    Request,
    Form,
    UploadFile,
    File,
    Cookie,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Basic setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(title="thebuzz.feed v1.3 (neon)")

# mount static files and uploaded videos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- In-memory stores (dev only) ---
USERS = {"admin": "password123"}
SESSIONS = {}  # cookie -> username
VIDEOS = []  # list of dicts: {id, title, filename, uploader, uploaded_at}
CHANNELS = {"general": []}  # mapping channel->chat history (list) - for display (not persisted)

# --- Helper ---
def get_username_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get("user")


# -------------------- ROUTES --------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # show login page
    return templates.TemplateResponse("index.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    pw = USERS.get(username)
    if pw and pw == password:
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie("user", username, httponly=True)
        SESSIONS[username] = True
        return resp
    # wrong credentials -> show login with error
    return templates.TemplateResponse("index.html", {"request": request, "error": "Invalid username or password"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_username_from_cookie(request)
    if not user or user not in SESSIONS:
        return RedirectResponse(url="/", status_code=303)
    # show uploaded videos
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "username": user, "videos": VIDEOS, "channels": list(CHANNELS.keys())},
    )


@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request):
    user = get_username_from_cookie(request)
    if not user or user not in SESSIONS:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("upload.html", {"request": request, "username": user})


@app.post("/upload")
async def do_upload(request: Request, title: str = Form(...), file: UploadFile = File(...)):
    user = get_username_from_cookie(request)
    if not user or user not in SESSIONS:
        return RedirectResponse(url="/", status_code=303)

    # sanitize and create unique filename
    original_name = os.path.basename(file.filename)
    unique = f"{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex}_{original_name}"
    dest = os.path.join(UPLOADS_DIR, unique)

    # write file
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    vid = {
        "id": unique,
        "title": title or original_name,
        "filename": unique,
        "uploader": user,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    VIDEOS.insert(0, vid)  # newest first

    # redirect to watch page
    return RedirectResponse(url=f"/watch/{unique}", status_code=303)


@app.get("/watch/{video_id}", response_class=HTMLResponse)
async def watch(request: Request, video_id: str):
    user = get_username_from_cookie(request)
    if not user or user not in SESSIONS:
        return RedirectResponse(url="/", status_code=303)
    video = next((v for v in VIDEOS if v["id"] == video_id), None)
    if not video:
        return HTMLResponse("<h3>Video not found</h3>", status_code=404)
    return templates.TemplateResponse("watch.html", {"request": request, "video": video, "username": user})


@app.get("/logout")
async def logout(request: Request):
    user = get_username_from_cookie(request)
    if user and user in SESSIONS:
        del SESSIONS[user]
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("user")
    return resp


# Serve raw uploaded file via explicit endpoint (optional — StaticFiles already mounted at /uploads)
@app.get("/raw_uploads/{filename}")
async def serve_raw(filename: str):
    path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(path):
        return HTMLResponse("File not found", status_code=404)
    # let StaticFiles handle range requests, but FileResponse with media_type works too
    return FileResponse(path, media_type="video/mp4")


# -------------------- WEBSOCKETS --------------------
class ConnectionManager:
    def __init__(self):
        # map channel -> set of websockets
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(channel, set()).add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        conns = self.active.get(channel)
        if conns and websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, channel: str, message: dict):
        conns = list(self.active.get(channel, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                # drop broken connection
                self.disconnect(channel, ws)


manager = ConnectionManager()

@app.websocket("/ws/{channel}")
async def websocket_endpoint(websocket: WebSocket, channel: str):
    # This websocket expects JSON messages like { user: "...", text: "..." }
    await manager.connect(channel, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            user = data.get("user", "anon")
            text = data.get("text", "")
            msg = {"user": user, "text": text, "time": datetime.utcnow().strftime("%H:%M:%S")}
            # save to history
            CHANNELS.setdefault(channel, []).append(msg)
            await manager.broadcast(channel, msg)
    except WebSocketDisconnect:
        manager.disconnect(channel, websocket)
    except Exception:
        # ensure removal on other errors
        manager.disconnect(channel, websocket)


# -------------------- RUN --------------------
# Note: use `uvicorn app:app --reload` to run
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
