import flet as ft
import json
import time
import hashlib
import base64
import asyncio
import urllib.request

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

class HoshinoTheme:
    BG = "#12131a"
    PINK = "#ff79c6"
    CYAN = "#8be9fd"
    TEXT = "#f8f8f2"
    ACCENT = "#1c1e26"

# --- СЕТЕВЫЕ ЗАПРОСЫ (Через асинхронный запуск urllib) ---
async def firebase_req(path, method="GET", data=None):
    url = f"{DB_URL}{path}.json"
    loop = asyncio.get_event_loop()
    try:
        def sync_req():
            req = urllib.request.Request(url, method=method)
            if data is not None:
                req.add_header('Content-Type', 'application/json')
                body = json.dumps(data).encode('utf-8')
            else:
                body = None
            with urllib.request.urlopen(req, data=body, timeout=7) as r:
                return json.loads(r.read().decode('utf-8'))
        
        return await loop.run_in_executor(None, sync_req)
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

# --- ГЛАВНАЯ ЛОГИКА ---
async def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    
    # Состояние приложения
    state = {
        "nick": page.client_storage.get("nick"),
        "room": None,
        "key": "",
        "active_sync": False
    }

    async def show_toast(text):
        page.snack_bar = ft.SnackBar(ft.Text(text))
        page.snack_bar.open = True
        await page.update_async()

    # --- ЭКРАН: ВХОД ---
    async def view_auth():
        state["active_sync"] = False
        page.clean()
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN, border_radius=15)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.PINK, border_radius=15)

        async def login(e):
            res = await firebase_req(f"/users/{nick_f.value}/p")
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            if res == hp:
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                await view_home()
            else:
                await show_toast("Ошибка входа")

        async def register(e):
            if not nick_f.value: return
            hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
            await firebase_req(f"/users/{nick_f.value}/p", method="PUT", data=hp)
            await show_toast("Регистрация успешна!")

        await page.add_async(ft.Container(
            content=ft.Column([
                ft.Text("HOSHINO", size=55, weight="bold", color=HoshinoTheme.PINK),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=login, bgcolor=HoshinoTheme.PINK, color="white", width=250),
                ft.TextButton("РЕГИСТРАЦИЯ", on_click=register, color=HoshinoTheme.CYAN)
            ], horizontal_alignment="center", alignment="center"),
            expand=True, padding=40
        ))

    # --- ЭКРАН: СПИСОК ЧАТОВ ---
    async def view_home():
        state["active_sync"] = False
        page.clean()
        rooms_col = ft.Column(scroll="auto", expand=True)

        async def refresh_rooms():
            data = await firebase_req(f"/users/{state['nick']}/rooms")
            rooms_col.controls.clear()
            if data:
                for rid in data.keys():
                    rooms_col.controls.append(ft.Container(
                        content=ft.ListTile(title=ft.Text(rid, weight="bold"), on_click=lambda _, r=rid: open_chat_dialog(r)),
                        bgcolor=HoshinoTheme.ACCENT, border_radius=12
                    ))
            await page.update_async()

        def open_chat_dialog(rid):
            k_f = ft.TextField(label="Пароль чата", password=True)
            async def go(e):
                state["room"] = rid
                state["key"] = k_f.value
                page.dialog.open = False
                await view_chat()
            page.dialog = ft.AlertDialog(title=ft.Text(f"Вход в {rid}"), content=k_f, actions=[ft.TextButton("ОК", on_click=go)])
            page.dialog.open = True
            page.update()

        async def add_chat(e):
            n_f = ft.TextField(label="Имя чата")
            async def save(e):
                await firebase_req(f"/users/{state['nick']}/rooms/{n_f.value}", method="PUT", data=True)
                page.dialog.open = False
                await refresh_rooms()
            page.dialog = ft.AlertDialog(title=ft.Text("Новый чат"), content=name_f, actions=[ft.TextButton("ОК", on_click=save)])
            # (Для краткости: тут вызов диалога аналогично входу)
            pass 

        await page.add_async(
            ft.AppBar(title=ft.Text(f"Чаты: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT,
                      actions=[ft.IconButton(ft.icons.LOGOUT, on_click=lambda _: view_auth())]),
            ft.Container(content=rooms_col, padding=20, expand=True),
            ft.FloatingActionButton(icon=ft.icons.ADD, bgcolor=HoshinoTheme.PINK, on_click=lambda _: show_toast("Создайте чат через БД или диалог"))
        )
        await refresh_rooms()

    # --- ЭКРАН: ЧАТ ---
    async def view_chat():
        page.clean()
        state["active_sync"] = True
        msg_list = ft.Column(scroll="always", expand=True, spacing=10)
        inp = ft.TextField(hint_text="Сообщение...", expand=True, border_radius=25)

        async def send(e):
            if inp.value:
                txt = h_crypt(inp.value, state["key"])
                await firebase_req(f"/rooms/{state['room']}/m", method="POST", data={"u": state["nick"], "t": txt, "ts": time.time()})
                inp.value = ""
                await page.update_async()

        async def sync_loop():
            while state["active_sync"]:
                data = await firebase_req(f"/rooms/{state['room']}/m")
                if data:
                    msg_list.controls.clear()
                    for k in sorted(data.keys(), key=lambda x: data[x]['ts']):
                        m = data[k]
                        is_me = m['u'] == state['nick']
                        dec = h_crypt(m['t'], state["key"], decrypt=True)
                        msg_list.controls.append(ft.Row([
                            ft.Container(
                                content=ft.Text(f"{m['u']}: {dec}"),
                                bgcolor=HoshinoTheme.ACCENT if not is_me else "#2d1b2e",
                                padding=12, border_radius=15,
                                border=ft.border.all(1, HoshinoTheme.PINK if is_me else HoshinoTheme.CYAN)
                            )
                        ], alignment="end" if is_me else "start"))
                    await page.update_async()
                await asyncio.sleep(3)

        await page.add_async(
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: view_home())),
            ft.Container(content=msg_list, expand=True, padding=15),
            ft.Container(content=ft.Row([inp, ft.IconButton(ft.icons.SEND, on_click=send)]), padding=10, bgcolor=HoshinoTheme.ACCENT)
        )
        asyncio.create_task(sync_loop())

    # ЗАПУСК
    if state["nick"]: await view_home()
    else: await view_auth()

ft.app(target=main)