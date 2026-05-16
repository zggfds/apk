import flet as ft
import base64
import time
import requests
import threading
import hashlib

# Пробуем импортировать криптографию, если нет - выведем ошибку на экран
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError as e:
    CRYPTO_AVAILABLE = False
    IMPORT_ERROR_MSG = str(e)

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
        if not CRYPTO_AVAILABLE:
            return
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
        try:
            res = requests.get(f"{DB_URL}/users/{nick}/pass.json", timeout=5).json()
            if res is not None: return False
            requests.put(f"{DB_URL}/users/{nick}/pass.json", json=self.hash_p(p), timeout=5)
            return True
        except: return False

    def login(self, nick, p):
        try:
            res = requests.get(f"{DB_URL}/users/{nick}/pass.json", timeout=5).json()
            return res and res == self.hash_p(p)
        except: return False

    def create_room(self, room_id, owner):
        requests.put(f"{DB_URL}/rooms/{room_id}/meta.json", json={"owner": owner})
        requests.put(f"{DB_URL}/users/{owner}/my_rooms/{room_id}.json", json=True)

    def invite_user(self, room_id, target_nick):
        requests.put(f"{DB_URL}/pending_invites/{target_nick}/{room_id}.json", json=True)

# --- ИНТЕРФЕЙС ---
def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    
    # Проверка на ошибку импорта
    if not CRYPTO_AVAILABLE:
        page.add(ft.Text(f"Ошибка загрузки модулей:\n{IMPORT_ERROR_MSG}\n\nУбедитесь, что cryptography есть в requirements.txt", color="red"))
        page.update()
        return

    db = DatabaseService()
    state = {"nick": None, "room": None}
    crypto = None

    # Показ загрузки пока читаем память
    loading_screen = ft.Container(
        content=ft.Column([
            ft.ProgressRing(color=HoshinoTheme.PINK),
            ft.Text("Загрузка Hoshino Messenger...", color=HoshinoTheme.CYAN)
        ], horizontal_alignment="center", alignment="center"),
        expand=True
    )
    page.add(loading_screen)
    page.update()

    # Пробуем прочитать ник из памяти
    try:
        state["nick"] = page.client_storage.get("nick")
    except:
        state["nick"] = None

    def show_msg(text):
        page.open(ft.SnackBar(ft.Text(text)))

    # Экраны (упрощенная навигация без views.clear для стабильности)
    def navigate_to_auth():
        page.clean()
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.CYAN)

        def login_click(e):
            if db.login(nick_f.value, pass_f.value):
                state["nick"] = nick_f.value
                page.client_storage.set("nick", nick_f.value)
                navigate_to_home()
            else: show_msg("Ошибка входа!")

        def reg_click(e):
            if db.register(nick_f.value, pass_f.value): show_msg("Успех! Теперь войдите")
            else: show_msg("Ник занят!")

        page.add(ft.Container(content=ft.Column([
            ft.Text("HOSHINO", size=40, weight="bold", color=HoshinoTheme.PINK),
            nick_f, pass_f,
            ft.ElevatedButton("ВОЙТИ", on_click=login_click, bgcolor=HoshinoTheme.PINK, color="white"),
            ft.TextButton("РЕГИСТРАЦИЯ", on_click=reg_click)
        ], horizontal_alignment="center"), padding=40, alignment=ft.alignment.center, expand=True))
        page.update()

    def navigate_to_home():
        page.clean()
        rooms_col = ft.Column(spacing=10, scroll="auto")
        
        def create_room(e):
            d = ft.TextField(label="Название чата")
            def save(e):
                if d.value:
                    db.create_room(d.value, state["nick"])
                    page.dialog.open = False
                    navigate_to_home()
            page.dialog = ft.AlertDialog(title=ft.Text("Новый чат"), content=d, actions=[ft.TextButton("ОК", on_click=save)])
            page.dialog.open = True
            page.update()

        def join_room(room_id):
            k = ft.TextField(label="Пароль чата", password=True)
            def go(e):
                nonlocal crypto
                state["room"] = room_id
                crypto = CryptoManager(k.value, room_id)
                navigate_to_chat()
                page.dialog.open = False
            page.dialog = ft.AlertDialog(title=ft.Text(f"Вход в {room_id}"), content=k, actions=[ft.TextButton("ВХОД", on_click=go)])
            page.dialog.open = True
            page.update()

        # Получаем комнаты
        try:
            my_rms = requests.get(f"{DB_URL}/users/{state['nick']}/my_rooms.json").json()
            if my_rms:
                for r in my_rms.keys():
                    rooms_col.controls.append(ft.ListTile(title=ft.Text(r), on_click=lambda _, r=r: join_room(r)))
        except: pass

        page.add(
            ft.AppBar(title=ft.Text(f"Чаты: {state['nick']}"), bgcolor=HoshinoTheme.ACCENT),
            ft.Container(content=rooms_col, padding=20, expand=True),
            ft.FloatingActionButton(icon=ft.icons.ADD, on_click=create_room, bgcolor=HoshinoTheme.PINK)
        )
        page.update()

    def navigate_to_chat():
        page.clean()
        chat_col = ft.Column(scroll="always", expand=True)
        msg_f = ft.TextField(hint_text="Сообщение...", expand=True)

        def send(e):
            if msg_f.value:
                requests.post(f"{DB_URL}/rooms/{state['room']}/messages.json", json={
                    "u": state["nick"], "t": crypto.encrypt(msg_f.value), "ts": time.time()
                })
                msg_f.value = ""
                page.update()

        def sync():
            while state["room"]:
                try:
                    res = requests.get(f"{DB_URL}/rooms/{state['room']}/messages.json").json()
                    if res:
                        chat_col.controls.clear()
                        for k in sorted(res.keys(), key=lambda x: res[x]['ts']):
                            m = res[k]
                            chat_col.controls.append(ft.Text(f"{m['u']}: {crypto.decrypt(m['t'])}"))
                        page.update()
                except: pass
                time.sleep(3)

        page.add(
            ft.AppBar(title=ft.Text(state["room"]), leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda _: navigate_to_home())),
            ft.Container(content=chat_col, expand=True, padding=10),
            ft.Row([msg_f, ft.IconButton(ft.icons.SEND, on_click=send)])
        )
        threading.Thread(target=sync, daemon=True).start()
        page.update()

    # Старт логики
    time.sleep(1) # Даем время на инициализацию
    if state["nick"]: navigate_to_home()
    else: navigate_to_auth()

ft.app(target=main)