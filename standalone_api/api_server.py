import asyncio
import logging
import os
import json
from aiohttp import web
from core.agent import Agent
from core.tools import ToolRegistry
from core.watcher import ModuleWatcher
import auth
from database import generate_access_codes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads')

if not os.path.exists(WEB_DIR):
    os.makedirs(WEB_DIR)
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Initialize Agent components
registry = ToolRegistry()
registry.load_modules()
watcher = ModuleWatcher(registry)
watcher.start()
agent = Agent(registry)

app = web.Application()
user_sessions = {}
session_lock = asyncio.Lock()

# Authentication Middleware
@web.middleware
async def auth_middleware(request, handler):
    # Public routes
    public_routes = ['/', '/static/', '/auth/register', '/auth/login']

    # We make downloads public so media links work easily inside markdown/chat logs
    # without needing complex header injections in all potential clients.
    if request.path in public_routes or request.path.startswith('/static/') or request.path.startswith('/auth/') or request.path.startswith('/download/'):
        return await handler(request)

    # Optional auth for OPTIONS (CORS)
    if request.method == "OPTIONS":
        return await handler(request)

    # Get token from headers or query params
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ")[1]
    else:
        token = request.query.get("token")

    if not token:
        # WebSocket exception handling
        if request.path == '/ws':
             return web.Response(status=401, text="Unauthorized: Token required")
        return web.json_response({"error": "Unauthorized: Token required"}, status=401)

    is_valid, user = auth.verify_token(token)
    if not is_valid:
        if request.path == '/ws':
            return web.Response(status=401, text="Unauthorized: Invalid token")
        return web.json_response({"error": "Unauthorized: Invalid token"}, status=401)

    if not user['has_access'] and request.path != '/auth/link_code':
        if request.path == '/ws':
             return web.Response(status=403, text="Forbidden: Access code required")
        return web.json_response({"error": "Forbidden: Access code required. Please link a valid code.", "needs_code": True}, status=403)

    request['user'] = user
    return await handler(request)

app.middlewares.insert(0, auth_middleware)

# --- Authentication Routes ---
async def handle_register(request):
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return web.json_response({"error": "Username and password required"}, status=400)

        success, msg = auth.register_user(username, password)
        if success:
            return web.json_response({"message": msg})
        else:
            return web.json_response({"error": msg}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_login(request):
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return web.json_response({"error": "Username and password required"}, status=400)

        success, msg, token, has_access = auth.login_user(username, password)
        if success:
            return web.json_response({"message": msg, "token": token, "has_access": has_access})
        else:
            return web.json_response({"error": msg}, status=401)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_link_code(request):
    try:
        data = await request.json()
        code = data.get("code")

        token = request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token.split(" ")[1]

        if not code or not token:
            return web.json_response({"error": "Code and valid session required"}, status=400)

        success, msg = auth.link_access_code(token, code)
        if success:
            return web.json_response({"message": msg})
        else:
            return web.json_response({"error": msg}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

app.router.add_post('/auth/register', handle_register)
app.router.add_post('/auth/login', handle_login)
app.router.add_post('/auth/link_code', handle_link_code)

# --- Chat API with DB ---
async def handle_get_chats(request):
    user = request['user']
    chats = auth.get_user_chats(user['id'])
    return web.json_response({"chats": chats})

async def handle_create_chat(request):
    try:
        user = request['user']
        data = await request.json()
        title = data.get("title", "New Chat")

        chat_id = auth.create_chat(user['id'], title)
        return web.json_response({"chat_id": chat_id, "title": title})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_get_chat_history(request):
    user = request['user']
    chat_id = request.match_info.get("chat_id")

    if not chat_id:
        return web.json_response({"error": "chat_id required"}, status=400)

    messages = auth.get_chat_history(chat_id, user['id'])
    if messages is None:
         return web.json_response({"error": "Chat not found or unauthorized"}, status=404)

    return web.json_response({"messages": messages})

app.router.add_get('/api/chats', handle_get_chats)
app.router.add_post('/api/chats', handle_create_chat)
app.router.add_get('/api/chats/{chat_id}', handle_get_chat_history)

async def handle_index(request):
    return web.FileResponse(os.path.join(WEB_DIR, 'index.html'))

async def handle_chat_rest(request):
    user = request['user']
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    chat_id = data.get("chat_id")
    message = data.get("message", "")

    if not message:
        return web.json_response({"error": "Message is required"}, status=400)

    if not chat_id:
        chat_id = auth.create_chat(user['id'], title=message[:30] + '...')

    # Init history from DB
    db_history = auth.get_chat_history(chat_id, user['id'])
    if db_history is None:
         return web.json_response({"error": "Chat not found or unauthorized"}, status=404)

    current_history = [{"role": m["role"], "content": m["content"]} for m in db_history]

    # RESTBot collects actions to return them in the response
    class RESTBot:
        def __init__(self):
            self.actions = []
        async def send_message(self, chat_id, text, **kwargs):
            self.actions.append({"action": "send_message", "text": text})
        async def send_document(self, chat_id, document, **kwargs):
            self.actions.append({"action": "send_document", "filename": os.path.basename(document.name)})
        async def send_photo(self, chat_id, photo, caption=None, **kwargs):
            self.actions.append({"action": "send_photo", "filename": os.path.basename(photo.name), "caption": caption})
        async def send_video(self, chat_id, video, caption=None, **kwargs):
            self.actions.append({"action": "send_video", "filename": os.path.basename(video.name), "caption": caption})
        async def send_audio(self, chat_id, audio, caption=None, **kwargs):
            self.actions.append({"action": "send_audio", "filename": os.path.basename(audio.name), "caption": caption})
        async def send_voice(self, chat_id, voice, caption=None, **kwargs):
            self.actions.append({"action": "send_voice", "filename": os.path.basename(voice.name), "caption": caption})
        async def send_file(self, chat_id, file, caption=None, **kwargs):
            self.actions.append({"action": "send_file", "filename": os.path.basename(file.name), "caption": caption})

    bot = RESTBot()
    tool_ctx = {
        "bot": bot,
        "chat_id": chat_id,
        "registry": registry,
        "job_queue": None,
        "agent_runner": None,
    }

    final_response = ""
    agent_states = []
    try:
        async for update_data in agent.run(
            message, history=current_history, tool_context=tool_ctx, plan_mode=True
        ):
            agent_states.append(update_data)
            status = update_data.get("status")
            if status == "final":
                final_response = update_data.get("content")
    except Exception as e:
        logger.error(f"REST Agent loop error: {e}")
        return web.json_response({"error": str(e)}, status=500)

    if final_response:
        # Save to DB instead of in-memory dictionary
        auth.add_message(chat_id, "user", message)
        auth.add_message(chat_id, "assistant", final_response)

    return web.json_response({
        "chat_id": chat_id,
        "response": final_response,
        "bot_actions": bot.actions,
        "agent_states": agent_states
    })

async def handle_ws(request):
    user = request['user']
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            action = data.get("action")
            chat_id = data.get("chat_id")

            if not chat_id and action == "chat":
                 chat_id = auth.create_chat(user['id'], title=data.get("message", "New Chat")[:30])
                 await ws.send_json({"type": "system", "action": "chat_created", "chat_id": chat_id})

            # WsBot acts as a proxy, sending tool outputs (like files) back to the client
            class WsBot:
                async def send_message(self, chat_id, text, **kwargs):
                    await ws.send_json({"type": "bot_action", "action": "send_message", "chat_id": chat_id, "text": text})
                async def send_document(self, chat_id, document, **kwargs):
                    try:
                        filepath = document.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_document", "chat_id": chat_id, "filename": filename})
                    except Exception as e:
                        logger.error(f"WsBot send_document error: {e}")
                async def send_photo(self, chat_id, photo, caption=None, **kwargs):
                    try:
                        filepath = photo.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_photo", "chat_id": chat_id, "filename": filename, "caption": caption})
                    except Exception as e:
                        logger.error(f"WsBot send_photo error: {e}")
                async def send_video(self, chat_id, video, caption=None, **kwargs):
                    try:
                        filepath = video.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_video", "chat_id": chat_id, "filename": filename, "caption": caption})
                    except Exception as e:
                        logger.error(f"WsBot send_video error: {e}")
                async def send_audio(self, chat_id, audio, caption=None, **kwargs):
                    try:
                        filepath = audio.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_audio", "chat_id": chat_id, "filename": filename, "caption": caption})
                    except Exception as e:
                        logger.error(f"WsBot send_audio error: {e}")
                async def send_voice(self, chat_id, voice, caption=None, **kwargs):
                    try:
                        filepath = voice.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_voice", "chat_id": chat_id, "filename": filename, "caption": caption})
                    except Exception as e:
                        logger.error(f"WsBot send_voice error: {e}")
                async def send_file(self, chat_id, file, caption=None, **kwargs):
                    try:
                        filepath = file.name
                        filename = os.path.basename(filepath)
                        await ws.send_json({"type": "bot_action", "action": "send_file", "chat_id": chat_id, "filename": filename, "caption": caption})
                    except Exception as e:
                        logger.error(f"WsBot send_file error: {e}")

            tool_ctx = {
                "bot": WsBot(),
                "chat_id": chat_id,
                "registry": registry,
                "job_queue": None,
                "agent_runner": None,
            }

            if action == "clear":
                pass # Clearing handled client-side or by creating a new chat now.

            elif action == "chat":
                user_input = data.get("message", "")

                db_history = auth.get_chat_history(chat_id, user['id'])
                if db_history is None:
                     await ws.send_json({"type": "error", "message": "Invalid chat_id"})
                     continue

                current_history = [{"role": m["role"], "content": m["content"]} for m in db_history]

                final_response = ""
                try:
                    async for update_data in agent.run(
                        user_input, history=current_history, tool_context=tool_ctx, plan_mode=True
                    ):
                        # Forward agent state directly to the websocket client
                        await ws.send_json({"type": "agent_state", "data": update_data})

                        status = update_data.get("status")
                        if status == "final":
                            final_response = update_data.get("content")

                except Exception as e:
                    logger.error(f"Agent loop error: {e}")
                    await ws.send_json({"type": "error", "message": str(e)})
                    final_response = f"Ошибка: {str(e)}"

                if final_response:
                    auth.add_message(chat_id, "user", user_input)
                    auth.add_message(chat_id, "assistant", final_response)

        elif msg.type == web.WSMsgType.ERROR:
            logger.error(f"WebSocket connection closed with exception {ws.exception()}")

    return ws

# Deprecated, handled by REST /api/chats/{chat_id} now
async def handle_history(request):
    return web.json_response({"history": []})

async def handle_download(request):
    filename = request.match_info.get("filename", "")
    # Sanitize the filename to prevent path traversal
    filename = os.path.basename(filename)
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    if os.path.exists(filepath):
        return web.FileResponse(filepath)
    return web.Response(status=404, text="File not found")

async def handle_upload(request):
    reader = await request.multipart()
    field = await reader.next()

    if field is None:
        return web.json_response({"error": "No file uploaded"}, status=400)

    filename = field.filename
    if not filename:
        return web.json_response({"error": "No filename"}, status=400)

    # Sanitize the filename to prevent path traversal
    filename = os.path.basename(filename)
    filepath = os.path.join(DOWNLOADS_DIR, filename)

    with open(filepath, 'wb') as f:
        while True:
            chunk = await field.read_chunk()
            if not chunk:
                break
            f.write(chunk)

    return web.json_response({"filepath": filepath, "filename": filename})

# Middleware to handle CORS
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        response = await handler(request)

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

app.middlewares.append(cors_middleware)

app.router.add_get('/', handle_index)
app.router.add_get('/ws', handle_ws)
app.router.add_post('/chat', handle_chat_rest)
app.router.add_get('/history', handle_history)
app.router.add_get('/download/{filename}', handle_download)
app.router.add_post('/upload', handle_upload)
app.router.add_static('/static', WEB_DIR)

if __name__ == '__main__':
    # Generate startup access codes
    codes = generate_access_codes(5)
    print(f"[*] Generated 5 new access codes. Saved to коды_доступа.txt")
    print(f"[*] Recent codes: {', '.join(codes)}")

    web.run_app(app, host='0.0.0.0', port=20067)
