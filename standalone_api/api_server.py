import asyncio
import logging
import os
import json
from aiohttp import web
from core.agent import Agent
from core.tools import ToolRegistry
from core.watcher import ModuleWatcher

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

async def handle_index(request):
    return web.FileResponse(os.path.join(WEB_DIR, 'index.html'))

async def handle_chat_rest(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    chat_id = data.get("chat_id", "rest_user")
    message = data.get("message", "")
    if not message:
        return web.json_response({"error": "Message is required"}, status=400)

    async with session_lock:
        if chat_id not in user_sessions:
            user_sessions[chat_id] = []
        current_history = list(user_sessions[chat_id])

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
        async with session_lock:
            user_sessions[chat_id].append({"role": "user", "content": message})
            user_sessions[chat_id].append({"role": "assistant", "content": final_response})

    return web.json_response({
        "response": final_response,
        "bot_actions": bot.actions,
        "agent_states": agent_states
    })

async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            action = data.get("action")
            chat_id = data.get("chat_id", "web_user")

            async with session_lock:
                if chat_id not in user_sessions:
                    user_sessions[chat_id] = []

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
                async with session_lock:
                    user_sessions[chat_id] = []
                await ws.send_json({"type": "bot_action", "action": "clear", "chat_id": chat_id})

            elif action == "chat":
                user_input = data.get("message", "")

                async with session_lock:
                    current_history = list(user_sessions[chat_id])

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
                    async with session_lock:
                        user_sessions[chat_id].append({"role": "user", "content": user_input})
                        user_sessions[chat_id].append({"role": "assistant", "content": final_response})

        elif msg.type == web.WSMsgType.ERROR:
            logger.error(f"WebSocket connection closed with exception {ws.exception()}")

    return ws

async def handle_history(request):
    chat_id = request.query.get("chat_id", "web_user")
    async with session_lock:
        history = user_sessions.get(chat_id, [])
    return web.json_response({"history": history})

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
    web.run_app(app, host='0.0.0.0', port=20067)
