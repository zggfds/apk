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

# --- ЧИСТЫЙ PYTHON: СЕТЕВЫЕ ЗАПРОСЫ (Вместо requests) ---
def firebase_req(path, method="GET", data=None):
    url = f"{DB_URL}{path}.json"
    try:
        req = urllib.request.Request(url, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
            json_data = json.dumps(data).encode('utf-8')
        else:
            json_data = None
        
        with urllib.request.urlopen(req, data=json_data, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Network error: {e}")
        return None

# --- ЧИСТЫЙ PYTHON: ШИФРОВАНИЕ (Вместо cryptography) ---
def hoshino_crypt(text, key, decrypt=False):
    try:
        # Генерируем 32-байтный ключ из пароля
        k = hashlib.sha256(key.encode()).digest()
        if decrypt:
            raw_data = base64.b64decode(text)
        else:
            raw_data = text.encode('utf-8')
        
        # XOR шифрование
        res = bytes([b ^ k[i % len(k)] for i, b in enumerate(raw_data)])
        
        if decrypt:
            return res.decode('utf-8', errors='ignore')
        return base64.b64encode(res).decode('utf-8')
    except:
        return "[Ошибка данных]"

# --- ПРИЛОЖЕНИЕ ---
def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    
    state = {
        "nick": page.client_storage.get("nick"),
        "room": None,
        "key": ""
    }

    def show_toast(text):
        page.open(ft.SnackBar(ft.Text(text)))

    # --- ЭКРАН 1: ВХОД / РЕГИСТРАЦИЯ ---
    def view_auth():
        page.clean()
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN, border_radius=15)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.PINK, border_radius=15)

        def on_login(e):
            res = firebase_req(f"/users/{nick_f.value}/pass")
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            if res and res == hp:
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                view_home()
            else:
                show_toast("Неверный вход")

        def on_reg(e):
            if not nick_f.value or not pass_f.value: return
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            firebase_req(f"/users/{nick_f.value}/pass", method="PUT", data=hp)
            show_toast("Готово! Теперь войдите")

        page.add(ft.Container(
            content=ft.Column([
                ft.Text("HOSHINO", size=50, weight="bold", color=HoshinoTheme.PINK),
                ft.Text("Standard Library Build", size=12, color=HoshinoTheme.CYAN),
                ft.Divider(height=20, color="transparent"),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=on_login, bgcolor=HoshinoTheme.PINK, color="white", width=200),
                ft.TextButton("РЕГИСТРАЦИЯ", on_click=on_reg)
            ], horizontal_alignment="center"),
            padding=40, expand=True, alignment=ft.alignment.center
        ))

    # --- ЭКРАН 2: СПИСОК ЧАТОВ ---
    def view_home():
        page.clean()
        rooms_list = ft.Column(scroll="auto", expand=True)

        def load_rooms():
            data = firebase_req(f"/users/{state['nick']}/my_rooms")
            rooms_list.controls.clear()
            if data:
                for r_id in data.keys():
                    rooms_list.controls.append(ft.Container(
                        content=ft.ListTile(
                            title=ft.Text(r_id, weight="bold"),
                            leading=ft.Icon(ft.icons.CHAT_BUBBLE, color=HoshinoTheme.CYAN),
                            on_click=lambda _, rid=r_id: show_join_dialog(rid)
                        ), bgcolor=HoshinoTheme.ACCENT, border_radius=10
                    ))
            page.update()

        def show_join_dialog(rid):
            k_f = ft.TextField(label="Ключ шифрования", password=True)
            def confirm(e):
                state["room"] = rid
                state["key"] = k_f.value
                view_chat()
                page.dialog.open = False
            page.dialog = ft.AlertDialog(title=ft.Text(f"Вход в {rid}"), content=k_f, actions=[ft.TextButton("ОК", on_click=confirm)])
            page.dialog.open = True
            page.update()

        def create_chat(e):
            name_f = ft.TextField(label="Имя чата")
            def save(e):
                firebase_req(f"/users/{state['nick']}/my_rooms/{name_f.value}", method="PUT", data=True)
                page.dialog.open = False
                load_rooms()
            page.dialog = ft.AlertDialog(title=ft.Text("Новый чат"), content=name_f, actions=[ft.TextButton("СОЗДАТЬ", on_click=save)])
            page.dialog.open = True
            page.update()

        page.add(
            ft.AppBar(title=ft.Text(f"Чаты: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT, 
                      actions=[ft.IconButton(ft.icons.LOGOUT, on_click=lambda _: (page.client_storage.remove("nick"), view_auth()))]),
            ft.Container(content=rooms_list, padding=20, expand=True),
            ft.FloatingActionButton(icon=ft.icons.ADD, bgcolor=HoshinoTheme.PINK, on_click=create_chat)
        )
        load_rooms()

    # --- ЭКРАН 3: ЧАТ ---
    def view_chat():
        page.clean()
        msg_col = ft.Column(scroll="always", expand=True)
        inp = ft.TextField(hint_text="Сообщение...", expand=True, border_radius=20)

        def send(e):
            if inp.value:
                enc = hoshino_crypt(inp.value, state["key"])
                firebase_req(f"/rooms/{state['room']}/m", method="POST", data={
                    "u": state["nick"], "t": enc, "ts": time.time()
                })
                inp.value = ""
                page.update()

        def sync():
            while state["room"] and page.route == "/chat":
                data = firebase_req(f"/rooms/{state['room']}/m")
                if data:
                    msg_col.controls.clear()
                    for k in sorted(data.keys(), key=lambda x: data[x]['ts']):
                        m = data[k]
                        is_me = m['u'] == state['nick']
                        txt = hoshino_crypt(m['t'], state["key"], decrypt=True)
                        msg_col.controls.append(ft.Row([
                            ft.Container(
                                content=ft.Text(f"{m['u']}: {txt}"),
                                bgcolor=HoshinoTheme.ACCENT, padding=10, border_radius=10,
                                border=ft.border.all(1, HoshinoTheme.PINK if is_me else HoshinoTheme.CYAN)
                            )
                        ], alignment="end" if is_me else "start"))
                    page.update()
                time.sleep(3)

        page.route = "/chat"
        page.add(
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: (setattr(page, 'route', '/home'), view_home()))),
            ft.Container(content=msg_col, expand=True, padding=15),
            ft.Container(content=ft.Row([inp, ft.IconButton(ft.icons.SEND, on_click=send)]), padding=10, bgcolor=HoshinoTheme.ACCENT)
        )
        threading.Thread(target=sync, daemon=True).start()

    # СТАРТ
    if state["nick"]: view_home()
    else: view_auth()

ft.app(target=main)