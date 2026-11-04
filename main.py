import datetime
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

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
        return HTMLResponse("Post not found", status_code=404)
    
    # Dedicated single-post page with Open Graph metadata for social sharing
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{post['username']}'s Post - Syber Community</title>
        <meta property="og:title" content="Post by {post['username']} | Syber Forum" />
        <meta property="og:description" content="{post['text'][:150]}..." />
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .back-link {{ display: inline-block; margin-bottom: 15px; color: #0066ff; text-decoration: none; font-weight: bold; font-size: 0.9em; }}
            .back-link:hover {{ text-decoration: underline; }}
            .post-card {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 16px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .post-header {{ display: flex; justify-content: space-between; font-size: 0.85em; color: #64748b; margin-bottom: 8px; }}
            .post-author {{ font-weight: bold; color: #0f172a; }}
            .post-text {{ font-size: 1.05em; color: #334155; margin-bottom: 16px; white-space: pre-line; line-height: 1.5; }}
            .comments-section {{ background: #f8fafc; padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid #e2e8f0; }}
            .comment-item {{ font-size: 0.9em; padding: 8px 0; border-bottom: 1px solid #e2e8f0; }}
            .comment-item:last-child {{ border-bottom: none; }}
            .comment-author {{ font-weight: bold; color: #1e293b; }}
            .comment-time {{ font-size: 0.8em; color: #94a3b8; float: right; }}
            input, button {{ width: 100%; padding: 10px; margin-top: 8px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; }}
            button {{ background-color: #0066ff; color: white; border: none; font-weight: bold; cursor: pointer; }}
            button:hover {{ background-color: #0052cc; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a class="back-link" href="/">← Back to Main Feed</a>
            <div class="post-card">
                <div class="post-header">
                    <span class="post-author">{post['username']}</span>
                    <span>{post['timestamp']}</span>
                </div>
                <div class="post-text">{post['text']}</div>
                
                <div class="comments-section">
                    <b>Discussion ({len(post['comments'])}):</b>
                    <div id="commentsList">
                        {"".join([f'<div class="comment-item"><span class="comment-author">{c["username"]}:</span> {c["text"]}<span class="comment-time">{c["timestamp"]}</span></div>' for c in post['comments']]) or '<p style="font-size:0.85em; color:#94a3b8; margin:4px 0;">No comments yet.</p>'}
                    </div>
                    <div style="margin-top: 12px;">
                        <input type="text" id="commentUser" placeholder="Your Name" value="Executive_User">
                        <input type="text" id="commentText" placeholder="Write a response...">
                        <button onclick="submitComment({post['id']})">Post Reply</button>
                    </div>
                </div>
            </div>
        </div>
        <script>
            const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            const socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);

            function submitComment(postId) {
                const username = document.getElementById("commentUser").value.trim() || "Anonymous";
                const text = document.getElementById("commentText").value.trim();
                if (!text) return alert("Comment cannot be empty.");
                socket.send(JSON.stringify({ type: "NEW_COMMENT", post_id: postId, username: username, text: text }));
                document.getElementById("commentText").value = "";
            }

            socket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === "UPDATE_POSTS") {
                    const updatedPost = data.posts.find(p => p.id === postId);
                    if (updatedPost) {
                        const list = document.getElementById("commentsList");
                        if (updatedPost.comments.length === 0) {
                            list.innerHTML = '<p style="font-size:0.85em; color:#94a3b8; margin:4px 0;">No comments yet.</p>';
                        } else {
                            list.innerHTML = updatedPost.comments.map(c => `
                                <div class="comment-item">
                                    <span class="comment-author">${c.username}:</span> ${c.text}
                                    <span class="comment-time">${c.timestamp}</span>
                                </div>
                            `).join('');
                        }
                    }
                }
            };
        </script>
    </body>
    </html>
    """
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
