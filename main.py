import asyncio
import sqlite3
import hashlib

from datetime import datetime, timedelta
from json import loads, dumps


conn = sqlite3.connect("database.db")
cur = conn.cursor()


class User:
    def __init__(self,
                 id: str,
                 first_name: str,
                 last_name: str,
                 nickname: str,
                 phone_number: str):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.nickname = nickname
        self.phone_number = phone_number

    def __repr__(self):
        return f"User(id: {self.id}, first_name: {self.first_name}, last_name: {self.last_name}, " \
               f"nickname: {self.nickname}, phone_number: {self.phone_number})"


class Utils:
    @staticmethod
    def create_db():
        cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            nickname TEXT,
            phone_number TEXT,
            password TEXT
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token TEXT,
            id INT,
            expires_in TEXT
        )""")

        conn.commit()

    @staticmethod
    def register_user(first_name: str, last_name: str, nickname: str, phone_number: str, password: str) -> dict:
        cur.execute("SELECT COUNT(*) FROM users WHERE nickname = ?", (nickname, ))
        nickname_is_used = cur.fetchone()[0] > 0

        cur.execute("SELECT COUNT(*) FROM users WHERE phone_number = ?", (phone_number, ))
        phone_number_is_used = cur.fetchone()[0] > 0

        if nickname_is_used:
            return {"ok": False, "message": "This nickname is already in use"}

        if phone_number_is_used:
            return {"ok": False, "message": "This phone number is already in use"}

        password = hashlib.sha256(password.encode("utf-8")).hexdigest()

        cur.execute(
            "INSERT INTO users(first_name, last_name, nickname, phone_number, password) VALUES (?, ?, ?, ?, ?)",
            (first_name, last_name, nickname, phone_number, password)
        )
        conn.commit()

        print(f"[CLIENT] info: Registered {nickname}")
        return {"ok": True}

    @staticmethod
    def login_user(phone_number: str, password: str) -> dict:
        cur.execute("SELECT password FROM users WHERE phone_number = ?", (phone_number, ))
        password_to_check = cur.fetchone()

        if not password_to_check:
            return {"ok": False, "message": "Wrong phone number"}

        password = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if password_to_check[0] != password:
            return {"ok": False, "message": "Wrong password"}

        cur.execute("SELECT id, first_name, last_name, nickname FROM users WHERE phone_number = ?", (phone_number, ))
        user_id, first_name, last_name, nickname = cur.fetchone()

        time = datetime.now()
        str_time = time.strftime("%Y.%m.%d %H:%M:%S.%f")
        token = hashlib.sha256(f"{user_id} {str_time}".encode("utf-8")).hexdigest()
        expires_in = (time + timedelta(days=7.0)).strftime("%Y.%m.%d %H:%M:%S.%f")

        cur.execute("INSERT INTO sessions(token, id, expires_in) VALUES (?, ?, ?)", (token, user_id, expires_in))
        conn.commit()

        print(f"[CLIENT] info: Logged in {nickname}")
        return {
            "ok": True,
            "data": {
                "token": token,
                "id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "nickname": nickname
            }
        }


class Processor:
    def __init__(self, data: dict):
        self.data = data
        self.result: dict = {}

        try:
            getattr(self, data["type"])()
        except AttributeError:
            self.result = {"ok": False, "message": "Wrong operation"}

    def register(self):
        for key in self.data["data"]:
            if self.data["data"][key] == "":
                self.result = {"ok": False, "message": "Fields must be not null"}
                return

        first_name = str(self.data["data"]["first_name"])
        last_name = str(self.data["data"]["last_name"])
        nickname = str(self.data["data"]["nickname"])
        phone_number = str(self.data["data"]["phone_number"])
        password = str(self.data["data"]["password"])

        self.result = Utils.register_user(first_name, last_name, nickname, phone_number, password)

    def login(self):
        for key in self.data["data"]:
            if self.data["data"][key] == "":
                self.result = {"ok": False, "message": "Fields must be not null"}
                return

        phone_number = str(self.data["data"]["phone_number"])
        password = str(self.data["data"]["password"])

        self.result = Utils.login_user(phone_number, password)


class ClientHandler(asyncio.Protocol):
    def __init__(self):
        self.transport = ...
        self.host, self.port = ..., ...

    @staticmethod
    def pack(data: dict) -> bytes:
        return dumps(data).encode("utf-8")

    @staticmethod
    def unpack(data: bytes) -> dict:
        return loads(data.decode("utf-8"))

    def connection_made(self, transport):
        self.transport = transport

        self.host, self.port = self.transport.get_extra_info('peername')
        print(f"[CLIENT] info: New connection {self.host}:{self.port}")

    def data_received(self, data):
        data = loads(data.decode("utf-8"))
        process = Processor(data)

        self.transport.write(self.pack(process.result))

    def connection_lost(self, exc):
        self.transport.close()
        print(f"[CLIENT] info: Disconnected {self.host}:{self.port}")


class Server:
    def __init__(self, host: str = "127.0.0.1", port: int = 25565, loop: asyncio.AbstractEventLoop = None):
        self.host = host
        self.port = port

        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop

        self.server = ...

    async def run(self):
        server = await self.loop.create_server(ClientHandler, self.host, self.port)

        print("[SERVER] log: Started!")

        async with server:
            await server.serve_forever()


def main():
    Utils.create_db()

    loop = asyncio.new_event_loop()
    server = Server(loop=loop)

    loop.create_task(server.run())
    loop.run_forever()

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
