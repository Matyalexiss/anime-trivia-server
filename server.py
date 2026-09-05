import os
import socketio
import base64
import json
from aiohttp import web
import aiohttp

sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
app = web.Application()
sio.attach(app)

host_sid = None
guest_sid = None
guest_name = ""
guest_cameras_data = None

# ⭐ CONFIGURACIÓN GITHUB API
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "Matyalexiss"
REPO_NAME = "anime-trivia-server"
FILE_PATH = "database/questions.json"

# ⭐ ENDPOINT RAÍZ
async def index(request):
    return web.Response(
        text="🎮 Anime Trivia Server is running. Conecta el cliente con socket.io.",
        content_type='text/plain'
    )

async def health(request):
    return web.json_response({
        "status": "ok",
        "host_connected": host_sid is not None,
        "guest_connected": guest_sid is not None,
        "guest_name": guest_name or None,
    })

app.router.add_get('/', index)
app.router.add_get('/health', health)

# ===== EVENTOS SOCKET.IO =====

@sio.event
async def connect(sid, environ):
    print(f"🔌 Usuario conectado: {sid}")

@sio.event
async def disconnect(sid):
    global host_sid, guest_sid, guest_name, guest_cameras_data
    print(f"❌ Usuario desconectado: {sid}")
    if sid == host_sid:
        host_sid = None
    if sid == guest_sid:
        guest_sid = None
        guest_name = ""
        guest_cameras_data = None

@sio.event
async def register(sid, data):
    global host_sid, guest_sid, guest_name
    role = data.get("role")

    if role == "host":
        host_sid = sid
        print(f"👑 Anfitrión (Briff) registrado: {sid}")
        if guest_sid and guest_name:
            await sio.emit("guest_waiting", {"name": guest_name}, to=host_sid)
        if guest_cameras_data:
            await sio.emit("camera_list", guest_cameras_data, to=host_sid)

    elif role == "guest":
        guest_sid = sid
        guest_name = data.get("name", "Participante")
        print(f"👤 Participante esperando: {guest_name} ({sid})")
        if host_sid:
            await sio.emit("guest_waiting", {"name": guest_name}, to=host_sid)

@sio.event
async def send_camera_list(sid, data):
    global guest_cameras_data
    guest_cameras_data = data
    if host_sid:
        await sio.emit("camera_list", data, to=host_sid)

@sio.event
async def select_camera(sid, data):
    if guest_sid:
        await sio.emit("start_camera", data, to=guest_sid)

@sio.event
async def sync_view(sid, data):
    if sid == host_sid and guest_sid:
        await sio.emit("sync_view", data, to=guest_sid)

@sio.event
async def sync_cursor(sid, data):
    target = guest_sid if sid == host_sid else host_sid
    if target:
        await sio.emit("sync_cursor", data, to=target)

@sio.event
async def sync_game(sid, data):
    target = guest_sid if sid == host_sid else host_sid
    if target:
        if sid == guest_sid and isinstance(data, dict):
            action = data.get("action")
            if action in ("guest_camera_ready", "guest_camera_reset"):
                data = dict(data)
                data["guestName"] = guest_name
        await sio.emit("sync_game", data, to=target)

@sio.event
async def request_guest_camera_setup(sid, data):
    if guest_sid:
        await sio.emit("open_camera_setup", data, to=guest_sid)

# ⭐ NUEVO EVENTO: SUBIDA DE LA BASE DE DATOS A GITHUB VIA API
@sio.event
async def upload_database(sid, data):
    if not GITHUB_TOKEN:
        await sio.emit("upload_status", {"status": "error", "msg": "❌ Falta la variable GITHUB_TOKEN en Render."}, to=sid)
        return
        
    try:
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}", 
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        async with aiohttp.ClientSession() as session:
            # 1. Obtener el SHA actual del archivo (requerido por GitHub para actualizar)
            async with session.get(api_url, headers=headers) as resp:
                sha = None
                if resp.status == 200:
                    resp_data = await resp.json()
                    sha = resp_data.get("sha")

            # 2. Subir el archivo modificado
            content_str = json.dumps(data, ensure_ascii=False, indent=2)
            content_b64 = base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
            
            payload = {
                "message": "📝 BD actualizada desde la App Cliente",
                "content": content_b64,
                "branch": "main"
            }
            if sha: 
                payload["sha"] = sha

            async with session.put(api_url, headers=headers, json=payload) as resp:
                if resp.status in (200, 201):
                    await sio.emit("upload_status", {"status": "success", "msg": "✅ ¡Base de datos guardada en la nube!"}, to=sid)
                else:
                    err_txt = await resp.text()
                    await sio.emit("upload_status", {"status": "error", "msg": f"❌ Error GitHub API: {resp.status} - Verifica tus permisos del Token."}, to=sid)
                    
    except Exception as e:
        await sio.emit("upload_status", {"status": "error", "msg": f"❌ Error de servidor: {e}"}, to=sid)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    web.run_app(app, host='0.0.0.0', port=port)