import flet as ft
import base64
import time
import requests
import threading
import hashlib

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

class HoshinoTheme:
    BG = "#12131a"
    PINK = "#ff79c6"
    CYAN = "#8be9fd"
    TEXT = "#f8f8f2"
    ACCENT = "#1c1e26"

# --- ПРОСТОЕ ШИФРОВАНИЕ (БЕЗ ТЯЖЕЛЫХ БИБЛИОТЕК) ---
# Чтобы избежать черного экрана из-за ошибок компиляции cryptography
def simple_crypt(text, key, decrypt=False):
    # Упрощенный XOR-алгоритм для теста стабильности
    k = hashlib.sha256(key.encode()).digest()
    res = []
    for i, char in enumerate(text.encode() if not decrypt else base64.b64decode(text)):
        res.append(char ^ k[i % len(k)])
    if decrypt:
        return bytes(res).decode('utf-8', errors='ignore')
    return base64.b64encode(bytes(res)).decode()

# --- ЛОГИКА БД ---
class DB:
    @staticmethod
    def reg(n, p):
        try:
            hp = hashlib.sha256(p.encode()).hexdigest()
            requests.put(f"{DB_URL}/users/{n}/pass.json", json=hp, timeout=5)
            return True
        except: return False

    @staticmethod
    def login(n, p):
        try:
            res = requests.get(f"{DB_URL}/users/{n}/pass.json", timeout=5).json()
            return res == hashlib.sha256(p.encode()).hexdigest()
        except: return False

# --- ИНТЕРФЕЙС ---
def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10
    
    # Состояние
    state = {"nick": page.client_storage.get("nick"), "room": None, "key": ""}

    def show_auth():
        page.clean()
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.PINK)

        def on_login(e):
            if DB.login(nick_f.value, pass_f.value):
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                show_home()
            else:
                page.open(ft.SnackBar(ft.Text("Ошибка входа")))

        page.add(
            ft.Column([
                ft.Text("HOSHINO", size=50, color=HoshinoTheme.PINK, weight="bold"),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=on_login, bgcolor=HoshinoTheme.PINK, color="white"),
                ft.TextButton("РЕГИСТРАЦИЯ", on_click=lambda _: DB.reg(nick_f.value, pass_f.value))
            ], horizontal_alignment="center", alignment="center", expand=True)
        )

    def show_home():
        page.clean()
        room_f = ft.TextField(label="ID Чата", border_color=HoshinoTheme.CYAN)
        key_f = ft.TextField(label="Ключ чата", password=True, border_color=HoshinoTheme.PINK)

        def on_join(e):
            state["room"] = room_f.value
            state["key"] = key_f.value
            show_chat()

        page.add(
            ft.AppBar(title=ft.Text(f"Аккаунт: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT),
            ft.Column([
                room_f, key_f,
                ft.ElevatedButton("В ЧАТ", on_click=on_join, bgcolor=HoshinoTheme.CYAN, color="black")
            ], spacing=20),
            ft.FloatingActionButton(icon=ft.icons.LOGOUT, on_click=lambda _: (page.client_storage.remove("nick"), show_auth()))
        )

    def show_chat():
        page.clean()
        messages = ft.Column(scroll="always", expand=True)
        msg_input = ft.TextField(hint_text="Сообщение...", expand=True)

        def send(e):
            if msg_input.value:
                enc = simple_crypt(msg_input.value, state["key"])
                requests.post(f"{DB_URL}/rooms/{state['room']}/m.json", json={
                    "u": state["nick"], "t": enc, "ts": time.time()
                })
                msg_input.value = ""
                page.update()

        def sync():
            while state["room"]:
                try:
                    res = requests.get(f"{DB_URL}/rooms/{state['room']}/m.json").json()
                    if res:
                        messages.controls.clear()
                        for k in sorted(res.keys(), key=lambda x: res[x]['ts']):
                            m = res[k]
                            txt = simple_crypt(m['t'], state["key"], decrypt=True)
                            messages.controls.append(ft.Text(f"{m['u']}: {txt}"))
                        page.update()
                except: pass
                time.sleep(3)

        page.add(
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: show_home())),
            messages,
            ft.Row([msg_input, ft.IconButton(ft.icons.SEND, on_click=send)])
        )
        threading.Thread(target=sync, daemon=True).start()

    # Точка старта
    if state["nick"]: show_home()
    else: show_auth()

ft.app(target=main)