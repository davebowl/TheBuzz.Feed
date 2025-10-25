from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

users = {"admin": "password123"}
active_sessions = {}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users and users[username] == password:
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="user", value=username)
        active_sessions[username] = True
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: str = Cookie(default=None)):
    if not user or user not in active_sessions:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": user})

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, user: str = Cookie(default=None)):
    if not user or user not in active_sessions:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("upload.html", {"request": request, "username": user})

@app.get("/chat", response_class=HTMLResponse)
async def chat_room(request: Request, user: str = Cookie(default=None)):
    if not user or user not in active_sessions:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("chat_room.html", {"request": request, "username": user})

@app.get("/logout")
async def logout(user: str = Cookie(default=None)):
    if user in active_sessions:
        del active_sessions[user]
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user")
    return response

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
