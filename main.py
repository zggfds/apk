import flet as ft
import base64
import time
import requests
import threading
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

class HoshinoTheme:
    BG = "#12131a"
    PINK = "#ff79c6"
    CYAN = "#8be9fd"
    TEXT = "#f8f8f2"
    ACCENT = "#1c1e26"

# --- ШИФРОВАНИЕ ---
class CryptoManager:
    def __init__(self, password: str, salt: str):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)

    def encrypt(self, text: str):
        return self.cipher.encrypt(text.encode()).decode()

    def decrypt(self, ciphertext: str):
        try: return self.cipher.decrypt(ciphertext.encode()).decode()
        except: return "[Ошибка расшифровки]"

# --- СЕРВИС БАЗЫ ДАННЫХ ---
class DatabaseService:
    @staticmethod
    def hash_p(p): return hashlib.sha256(p.encode()).hexdigest()

    def register(self, nick, p):
        # ИСПРАВЛЕНИЕ: Проверяем наличие пароля, а не просто папки
        res = requests.get(f"{DB_URL}/users/{nick}/pass.json").json()
        if res is not None: 
            return False # Если пароль уже есть, ник точно занят
        
        # Создаем или обновляем запись пользователя (добавляем пароль)
        requests.put(f"{DB_URL}/users/{nick}/pass.json", json=self.hash_p(p))
        return True

    def login(self, nick, p):
        res = requests.get(f"{DB_URL}/users/{nick}/pass.json").json()
        return res and res == self.hash_p(p)

    def create_room(self, room_id, owner):
        requests.put(f"{DB_URL}/rooms/{room_id}/meta.json", json={"owner": owner})
        self.add_to_member_list(room_id, owner)

    def add_to_member_list(self, room_id, nick):
        requests.put(f"{DB_URL}/users/{nick}/my_rooms/{room_id}.json", json=True)

    def invite_user(self, room_id, target_nick):
        # Переносим инвайты в отдельную ветку, чтобы не засорять /users/
        requests.put(f"{DB_URL}/pending_invites/{target_nick}/{room_id}.json", json=True)

    def get_my_rooms(self, nick):
        res = requests.get(f"{DB_URL}/users/{nick}/my_rooms.json").json()
        return list(res.keys()) if res else []

    def get_invites(self, nick):
        # Проверяем новую ветку инвайтов
        res = requests.get(f"{DB_URL}/pending_invites/{nick}.json").json()
        return list(res.keys()) if res else []

    def accept_invite(self, nick, room_id):
        self.add_to_member_list(room_id, nick)
        # Удаляем из ожидающих
        requests.delete(f"{DB_URL}/pending_invites/{nick}/{room_id}.json")

# --- ИНТЕРФЕЙС ---
def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    
    db = DatabaseService()
    crypto = None
    state = {"nick": page.client_storage.get("nick"), "room": None}

    def show_msg(text):
        page.open(ft.SnackBar(ft.Text(text)))

    # --- ЭКРАН АВТОРИЗАЦИИ ---
    def show_auth(e=None):
        page.views.clear()
        page.route = "/auth"
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN, border_radius=15)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.CYAN, border_radius=15)

        def login_action(e):
            if db.login(nick_f.value, pass_f.value):
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                show_home()
            else: show_msg("Ошибка входа: неверный ник или пароль!")

        def reg_action(e):
            if not nick_f.value or not pass_f.value:
                show_msg("Заполните все поля!")
                return
            if db.register(nick_f.value, pass_f.value): 
                show_msg("Успешно! Теперь нажмите ВОЙТИ.")
            else: 
                show_msg("Этот никнейм уже занят!")

        page.views.append(ft.View("/auth", [
            ft.Container(content=ft.Column([
                ft.Text("HOSHINO", size=50, weight="bold", color=HoshinoTheme.PINK),
                ft.Text("Secure Messenger", color=HoshinoTheme.CYAN),
                ft.Divider(height=20, color="transparent"),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=login_action, bgcolor=HoshinoTheme.PINK, color="white", width=200),
                ft.TextButton("ЗАРЕГИСТРИРОВАТЬСЯ", on_click=reg_action)
            ], horizontal_alignment="center", spacing=15), padding=40, alignment=ft.alignment.center, expand=True)
        ]))
        page.update()

    # --- ГЛАВНЫЙ ЭКРАН ---
    def show_home(e=None):
        page.views.clear()
        page.route = "/home"
        rooms_col = ft.Column(spacing=10, scroll="auto")
        invites_col = ft.Column(spacing=10)

        def logout(e):
            page.client_storage.remove("nick")
            state["nick"] = None
            show_auth()

        def sync_home():
            while page.route == "/home":
                # Проверка инвайтов
                invs = db.get_invites(state["nick"])
                invites_col.controls.clear()
                for i in invs:
                    invites_col.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Text(f"Приглашение в: {i}", color="black", weight="bold"),
                            ft.IconButton(ft.icons.CHECK, icon_color="black", on_click=lambda _, r=i: (db.accept_invite(state['nick'], r), show_home()))
                        ], alignment="spaceBetween"), bgcolor=HoshinoTheme.CYAN, padding=10, border_radius=10
                    ))
                
                # Список чатов
                my_rms = db.get_my_rooms(state["nick"])
                rooms_col.controls.clear()
                for r in my_rms:
                    rooms_col.controls.append(ft.Container(
                        content=ft.ListTile(
                            title=ft.Text(r, weight="bold"), leading=ft.Icon(ft.icons.CHAT, color=HoshinoTheme.PINK),
                            on_click=lambda _, r=r: show_enter_key(r)
                        ), bgcolor=HoshinoTheme.ACCENT, border_radius=15
                    ))
                page.update()
                time.sleep(4)

        def show_enter_key(room_id):
            key_f = ft.TextField(label="Ключ чата", password=True)
            def join(e):
                nonlocal crypto
                state["room"] = room_id
                crypto = CryptoManager(key_f.value, room_id)
                show_chat()
                page.dialog.open = False
            page.dialog = ft.AlertDialog(title=ft.Text(f"Вход в {room_id}"), content=key_f, actions=[ft.TextButton("OK", on_click=join)])
            page.dialog.open = True
            page.update()

        def create_room_dialog(e):
            name_f = ft.TextField(label="Название чата")
            def save(e):
                if name_f.value:
                    db.create_room(name_f.value, state["nick"])
                    page.dialog.open = False
                    show_home()
            page.dialog = ft.AlertDialog(title=ft.Text("Новый чат"), content=name_f, actions=[ft.TextButton("СОЗДАТЬ", on_click=save)])
            page.dialog.open = True
            page.update()

        page.views.append(ft.View("/home", [
            ft.AppBar(title=ft.Text(f"Профиль: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT, actions=[ft.IconButton(ft.icons.LOGOUT, on_click=logout)]),
            ft.Container(content=ft.Column([
                invites_col,
                ft.Text("ВАШИ ЧАТЫ", size=12, weight="bold", color=HoshinoTheme.PINK),
                rooms_col
            ]), padding=20, expand=True),
            ft.FloatingActionButton(icon=ft.icons.ADD, bgcolor=HoshinoTheme.PINK, on_click=create_room_dialog)
        ]))
        threading.Thread(target=sync_home, daemon=True).start()
        page.update()

    # --- ЭКРАН ЧАТА ---
    def show_chat():
        page.views.clear()
        page.route = "/chat"
        chat_col = ft.Column(scroll="always", expand=True)
        msg_f = ft.TextField(hint_text="Сообщение...", expand=True, border_radius=25)

        def invite_user_dialog(e):
            u_f = ft.TextField(label="Кому отправить инвайт?")
            def do_inv(e):
                db.invite_user(state["room"], u_f.value)
                page.dialog.open = False
                show_msg("Инвайт отправлен!")
            page.dialog = ft.AlertDialog(title=ft.Text("Инвайт"), content=u_f, actions=[ft.TextButton("ОК", on_click=do_inv)])
            page.dialog.open = True
            page.update()

        def send_message(e):
            if msg_f.value:
                requests.post(f"{DB_URL}/rooms/{state['room']}/messages.json", json={
                    "u": state["nick"], "t": crypto.encrypt(msg_f.value), "ts": time.time()
                })
                msg_f.value = ""
                page.update()

        def sync_chat():
            while page.route == "/chat":
                res = requests.get(f"{DB_URL}/rooms/{state['room']}/messages.json").json()
                if res:
                    chat_col.controls.clear()
                    for k in sorted(res.keys(), key=lambda x: res[x]['ts']):
                        m = res[k]
                        is_me = m['u'] == state['nick']
                        chat_col.controls.append(ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Text(m['u'], size=10, weight="bold", color=HoshinoTheme.PINK if is_me else HoshinoTheme.CYAN),
                                    ft.Text(crypto.decrypt(m['t']), color=HoshinoTheme.TEXT)
                                ], spacing=2),
                                bgcolor=HoshinoTheme.ACCENT, padding=12, border_radius=15,
                                border=ft.border.all(1, HoshinoTheme.PINK if is_me else HoshinoTheme.CYAN),
                                width=260
                            )
                        ], alignment="end" if is_me else "start"))
                    page.update()
                time.sleep(3)

        page.views.append(ft.View("/chat", [
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: show_home()), 
                      actions=[ft.IconButton(ft.icons.PERSON_ADD, on_click=invite_user_dialog)]),
            ft.Container(content=chat_col, expand=True, padding=15),
            ft.Container(content=ft.Row([msg_f, ft.IconButton(ft.icons.SEND, icon_color=HoshinoTheme.PINK, on_click=send_message)]), padding=10, bgcolor=HoshinoTheme.ACCENT)
        ]))
        threading.Thread(target=sync_chat, daemon=True).start()
        page.update()

    if state["nick"]: show_home()
    else: show_auth()

ft.app(target=main)