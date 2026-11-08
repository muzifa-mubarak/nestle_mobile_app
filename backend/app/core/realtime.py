from fastapi import WebSocket


class RealtimeHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        self._clients.add(socket)

    def disconnect(self, socket: WebSocket) -> None:
        self._clients.discard(socket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for socket in list(self._clients):
            try:
                await socket.send_json(message)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


hub = RealtimeHub()
