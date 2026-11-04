from datetime import datetime, timezone, timedelta
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

# UTC+8 timezone definition for static timestamps
UTC_8 = timezone(timedelta(hours=8))

# In-memory database storing forum posts & threaded comments
posts_db: List[Dict] = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/post/{post_id}", response_class=HTMLResponse)
async def get_single_post(post_id: int):
    post = next((p for p in posts_db if p["id"] == post_id), None)
    if not post:
        return RedirectResponse(url="/", status_code=303)
    
    with open("post_detail.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    post_url = f"https://syber-community.onrender.com/post/{post_id}"
    safe_text = post['text'].replace('"', '&quot;')[:160]
    
    html_content = html_content.replace("<!--OG_TITLE_PLACEHOLDER-->", f"Post by {post['username']} | Syber Community")
    html_content = html_content.replace("<!--OG_DESC_PLACEHOLDER-->", safe_text)
    html_content = html_content.replace("<!--OG_URL_PLACEHOLDER-->", post_url)
    
    return HTMLResponse(content=html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "INIT_DATA", "posts": posts_db})
        while True:
            data = await websocket.receive_json()
            action_type = data.get("type")

            if action_type == "NEW_POST":
                new_post = {
                    "id": len(posts_db) + 1,
                    "username": data.get("username", "Executive_User"),
                    "text": data.get("text", ""),
                    "timestamp": datetime.now(UTC_8).strftime("%Y-%m-%d %H:%M:%S UTC+8"),
                    "comments": []
                }
                posts_db.insert(0, new_post)
                await manager.broadcast({"type": "UPDATE_POSTS", "posts": posts_db})

            elif action_type == "NEW_COMMENT":
                post_id = data.get("post_id")
                for post in posts_db:
                    if post["id"] == post_id:
                        post["comments"].append({
                            "username": data.get("username", "Executive_User"),
                            "text": data.get("text", ""),
                            "timestamp": datetime.now(UTC_8).strftime("%Y-%m-%d %H:%M:%S UTC+8")
                        })
                        break
                await manager.broadcast({"type": "UPDATE_POSTS", "posts": posts_db})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
