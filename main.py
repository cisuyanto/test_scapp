import datetime
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# In-memory storage for posts and comments
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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send existing posts upon connection
        await websocket.send_json({"type": "INIT_DATA", "posts": posts_db})

        while True:
            data = await websocket.receive_json()
            action_type = data.get("type")

            if action_type == "NEW_POST":
                new_post = {
                    "id": len(posts_db) + 1,
                    "username": data.get("username", "Anonymous"),
                    "text": data.get("text", ""),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "comments": []
                }
                posts_db.insert(0, new_post)
                await manager.broadcast({"type": "UPDATE_POSTS", "posts": posts_db})

            elif action_type == "NEW_COMMENT":
                post_id = data.get("post_id")
                for post in posts_db:
                    if post["id"] == post_id:
                        post["comments"].append({
                            "username": data.get("username", "Anonymous"),
                            "text": data.get("text", ""),
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                        })
                        break
                await manager.broadcast({"type": "UPDATE_POSTS", "posts": posts_db})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
