import os
import socketio
from aiohttp import web

sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='aiohttp')
app = web.Application()
sio.attach(app)

host_sid = None
guest_sid = None
guest_name = ""
guest_cameras_data = None


# ⭐ ENDPOINT RAÍZ (clave para Render y para el wakeup HTTP del cliente)
async def index(request):
    return web.Response(
        text="🎮 Anime Trivia Server is running. Conecta el cliente con socket.io.",
        content_type='text/plain'
    )

async def health(request):
    """Health check que Render usa para verificar que el servidor está vivo."""
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
    """Sync de juego bidireccional. Inyecta guestName si es un evento del invitado."""
    target = guest_sid if sid == host_sid else host_sid
    if target:
        # ⭐ Si el evento viene del guest y es de cámara, asegúrate de incluir su nombre
        if sid == guest_sid and isinstance(data, dict):
            action = data.get("action")
            if action in ("guest_camera_ready", "guest_camera_reset"):
                data = dict(data)  # copia para no mutar el original
                data["guestName"] = guest_name
        await sio.emit("sync_game", data, to=target)


@sio.event
async def request_guest_camera_setup(sid, data):
    if guest_sid:
        await sio.emit("open_camera_setup", data, to=guest_sid)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor corriendo en puerto {port}")
    web.run_app(app, host='0.0.0.0', port=port)