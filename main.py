import flet as ft
import json
import time
import hashlib
import base64
import threading
import urllib.request

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

class HoshinoTheme:
    BG = "#12131a"
    PINK = "#ff79c6"
    CYAN = "#8be9fd"
    TEXT = "#f8f8f2"
    ACCENT = "#1c1e26"

# --- СЕТЕВЫЕ ЗАПРОСЫ (Синхронные, чистый Python) ---
def firebase_req(path, method="GET", data=None):
    url = f"{DB_URL}{path}.json"
    try:
        req = urllib.request.Request(url, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
            body = json.dumps(data).encode('utf-8')
        else:
            body = None
        with urllib.request.urlopen(req, data=body, timeout=5) as r:
            return json.loads(r.read().decode('utf-8'))
    except:
        return None

# --- ШИФРОВАНИЕ (Чистый Python) ---
def h_crypt(text, key, decrypt=False):
    try:
        k = hashlib.sha256(key.encode()).digest()
        raw = base64.b64decode(text) if decrypt else text.encode('utf-8')
        res = bytes([b ^ k[i % len(k)] for i, b in enumerate(raw)])
        return res.decode('utf-8', errors='ignore') if decrypt else base64.b64encode(res).decode('utf-8')
    except:
        return "[Ошибка]"

def main(page: ft.Page):
    # 1. МГНОВЕННАЯ НАСТРОЙКА (До любого кода)
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.update() # Принудительно отрисовываем фон

    # 2. СОСТОЯНИЕ
    state = {
        "nick": page.client_storage.get("nick"),
        "room": None,
        "key": ""
    }

    # --- ЭКРАН: ВХОД ---
    def view_auth():
        page.clean()
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN, border_radius=15)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.PINK, border_radius=15)

        def login(e):
            page.open(ft.SnackBar(ft.Text("Вход...")))
            res = firebase_req(f"/users/{nick_f.value}/p")
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            if res == hp:
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                view_home()
            else:
                page.open(ft.SnackBar(ft.Text("Ошибка данных")))

        def register(e):
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            firebase_req(f"/users/{nick_f.value}/p", method="PUT", data=hp)
            page.open(ft.SnackBar(ft.Text("Готово! Войдите")))

        page.add(
            ft.Column([
                ft.Text("HOSHINO", size=50, weight="bold", color=HoshinoTheme.PINK),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=login, bgcolor=HoshinoTheme.PINK, color="white", width=200),
                ft.TextButton("РЕГИСТРАЦИЯ", on_click=register, color=HoshinoTheme.CYAN)
            ], horizontal_alignment="center", spacing=20)
        )

    # --- ЭКРАН: СПИСОК ЧАТОВ ---
    def view_home():
        page.clean()
        rooms_col = ft.Column(scroll="auto", expand=True)

        def create_chat(e):
            d = ft.TextField(label="Имя чата")
            def save(e):
                firebase_req(f"/users/{state['nick']}/rooms/{d.value}", method="PUT", data=True)
                page.dialog.open = False
                view_home()
            page.dialog = ft.AlertDialog(title=ft.Text("Новый чат"), content=d, actions=[ft.TextButton("ОК", on_click=save)])
            page.dialog.open = True
            page.update()

        def enter_chat(r_id):
            k = ft.TextField(label="Пароль чата", password=True)
            def go(e):
                state["room"] = r_id
                state["key"] = k.value
                page.dialog.open = False
                view_chat()
            page.dialog = ft.AlertDialog(title=ft.Text(f"Вход в {r_id}"), content=k, actions=[ft.TextButton("ВХОД", on_click=go)])
            page.dialog.open = True
            page.update()

        # Грузим чаты
        data = firebase_req(f"/users/{state['nick']}/rooms")
        if data:
            for r in data.keys():
                rooms_col.controls.append(ft.ListTile(title=ft.Text(r), on_click=lambda _, r=r: enter_chat(r)))

        page.add(
            ft.AppBar(title=ft.Text(f"Аккаунт: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT),
            rooms_col,
            ft.FloatingActionButton(icon=ft.icons.ADD, on_click=create_chat, bgcolor=HoshinoTheme.PINK)
        )

    # --- ЭКРАН: ЧАТ ---
    def view_chat():
        page.clean()
        msg_list = ft.Column(scroll="always", expand=True)
        inp = ft.TextField(hint_text="Сообщение...", expand=True)

        def send(e):
            if inp.value:
                enc = h_crypt(inp.value, state["key"])
                firebase_req(f"/rooms/{state['room']}/m", method="POST", data={"u": state["nick"], "t": enc, "ts": time.time()})
                inp.value = ""
                page.update()

        def sync():
            while state["room"]:
                res = firebase_req(f"/rooms/{state['room']}/m")
                if res:
                    msg_list.controls.clear()
                    for k in sorted(res.keys(), key=lambda x: res[x]['ts']):
                        m = res[k]
                        txt = h_crypt(m['t'], state["key"], decrypt=True)
                        msg_list.controls.append(ft.Text(f"{m['u']}: {txt}"))
                    page.update()
                time.sleep(3)

        page.add(
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: view_home())),
            msg_list,
            ft.Row([inp, ft.IconButton(ft.icons.SEND, on_click=send)])
        )
        threading.Thread(target=sync, daemon=True).start()

    # СТАРТ (Без таймеров!)
    if state["nick"]:
        view_home()
    else:
        view_auth()

ft.app(target=main)