from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        # Mapeia: tenant_id -> user_id -> WebSocket
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str, user_id: str):
        # O handshake (await websocket.accept()) agora é feito na rota antes da validação JWT
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = {}
        self.active_connections[tenant_id][user_id] = websocket

    def disconnect(self, tenant_id: str, user_id: str):
        if tenant_id in self.active_connections:
            if user_id in self.active_connections[tenant_id]:
                del self.active_connections[tenant_id][user_id]
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def send_personal_message(self, message: dict, tenant_id: str, receiver_id: str):
        if tenant_id in self.active_connections and receiver_id in self.active_connections[tenant_id]:
            websocket = self.active_connections[tenant_id][receiver_id]
            await websocket.send_json(message)

manager = ConnectionManager()
