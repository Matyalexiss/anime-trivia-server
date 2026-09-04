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

@sio.event
async def connect(sid, environ):
    print(f"Usuario conectado: {sid}")

@sio.event
async def register(sid, data):
    global host_sid, guest_sid, guest_name
    role = data.get("role")
    
    if role == "host":
        host_sid = sid
        print("Anfitrión (Briff) registrado.")
        if guest_sid and guest_name:
            await sio.emit("guest_waiting", {"name": guest_name}, to=host_sid)
        if guest_cameras_data:
            await sio.emit("camera_list", guest_cameras_data, to=host_sid)
            
    elif role == "guest":
        guest_sid = sid
        guest_name = data.get("name")
        print(f"Participante esperando: {guest_name}")
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
    if sid == host_sid and guest_sid:
        await sio.emit("sync_game", data, to=target)

# ⭐ NUEVO: Fuerza al participante a configurar su cámara individualmente
@sio.event
async def request_guest_camera_setup(sid, data):
    if guest_sid:
        await sio.emit("open_camera_setup", data, to=guest_sid)

@sio.event
async def disconnect(sid):
    global host_sid, guest_sid, guest_name, guest_cameras_data
    if sid == host_sid: host_sid = None
    if sid == guest_sid: 
        guest_sid = None; guest_name = ""; guest_cameras_data = None

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    web.run_app(app, host='0.0.0.0', port=port)