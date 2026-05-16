import flet as ft
import hashlib
import base64
import time
import threading

# --- СИСТЕМА ПРОВЕРКИ БИБЛИОТЕК ---
libs_status = {}

# Проверяем requests (нужен для связи с базой)
try:
    import requests
    libs_status["requests"] = "OK"
except ImportError:
    libs_status["requests"] = "MISSING"

# Проверяем cryptography (самая проблемная на Android)
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    libs_status["cryptography"] = "OK"
except ImportError:
    libs_status["cryptography"] = "MISSING"

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

class HoshinoTheme:
    BG = "#12131a"
    PINK = "#ff79c6"
    CYAN = "#8be9fd"
    TEXT = "#f8f8f2"
    ACCENT = "#1c1e26"
    ERROR_BG = "#442222"

# --- РЕЗЕРВНОЕ ШИФРОВАНИЕ (если cryptography упала) ---
def fallback_crypt(text, key, decrypt=False):
    k = hashlib.sha256(key.encode()).digest()
    res = []
    data = base64.b64decode(text) if decrypt else text.encode()
    for i, char in enumerate(data):
        res.append(char ^ k[i % len(k)])
    return bytes(res).decode('utf-8', errors='ignore') if decrypt else base64.b64encode(bytes(res)).decode()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---
def main(page: ft.Page):
    page.bgcolor = HoshinoTheme.BG
    page.theme_mode = ft.ThemeMode.DARK
    page.title = "Hoshino Debug Mode"
    page.padding = 0

    # Проверяем, есть ли критические ошибки
    critical_errors = [lib for lib, status in libs_status.items() if status == "MISSING"]

    def get_error_panel():
        if not critical_errors:
            return ft.Container()
        return ft.Container(
            content=ft.Column([
                ft.Text("ОШИБКА ЗАВИСИМОСТЕЙ:", color=ft.colors.WHITE, weight="bold", size=12),
                ft.Text(f"Не удалось загрузить: {', '.join(critical_errors)}", color=HoshinoTheme.PINK, size=11),
                ft.Text("Приложение работает в ограниченном режиме", color=ft.colors.WHITE, size=10),
            ], spacing=2),
            bgcolor=HoshinoTheme.ERROR_BG,
            padding=10,
            border_radius=ft.border_radius.only(top_left=15, top_right=15)
        )

    # --- ЭКРАН ЗАГРУЗКИ / СПЛЕШ ---
    splash = ft.Container(
        content=ft.Column([
            ft.Image(src="https://raw.githubusercontent.com/flet-dev/flet/main/package/flet/src/flet/assets/icon.png", width=100),
            ft.ProgressRing(color=HoshinoTheme.PINK),
            ft.Text("Инициализация систем...", color=HoshinoTheme.CYAN),
        ], horizontal_alignment="center", alignment="center"),
        expand=True
    )

    # Главный контейнер, куда будем подгружать контент
    main_container = ft.Container(content=splash, expand=True)
    
    # Слой с ошибками (всегда сверху снизу)
    layout = ft.Column([
        main_container,
        get_error_panel()
    ], expand=True, spacing=0)

    page.add(layout)

    # --- ЛОГИКА ПРИЛОЖЕНИЯ ---
    def start_app():
        time.sleep(2) # Имитация загрузки для проверки сплеша
        
        # Если нет requests, дальше идти нельзя
        if libs_status.get("requests") == "MISSING":
            main_container.content = ft.Column([
                ft.Icon(ft.icons.ERROR_OUTLINE, color="red", size=50),
                ft.Text("Критическая ошибка: отсутствует модуль 'requests'", textAlign="center")
            ], alignment="center", horizontal_alignment="center")
            page.update()
            return

        show_login()

    def show_login():
        nick_f = ft.TextField(label="Никнейм", border_color=HoshinoTheme.CYAN, border_radius=15)
        pass_f = ft.TextField(label="Пароль", password=True, border_color=HoshinoTheme.PINK, border_radius=15)

        def do_login(e):
            # Простая проверка через requests
            try:
                res = requests.get(f"{DB_URL}/users/{nick_f.value}/pass.json", timeout=5).json()
                hp = hashlib.sha256(pass_f.value.encode()).hexdigest()
                if res == hp:
                    page.client_storage.set("nick", nick_f.value)
                    show_chat_select(nick_f.value)
                else:
                    page.open(ft.SnackBar(ft.Text("Ошибка входа!")))
            except Exception as ex:
                page.open(ft.SnackBar(ft.Text(f"Ошибка сети: {ex}")))

        main_container.content = ft.Container(
            content=ft.Column([
                ft.Text("HOSHINO", size=45, weight="bold", color=HoshinoTheme.PINK),
                nick_f, pass_f,
                ft.ElevatedButton("ВОЙТИ", on_click=do_login, bgcolor=HoshinoTheme.PINK, color="white", width=200),
                ft.TextButton("РЕГИСТРАЦИЯ (тест)", on_click=lambda _: requests.put(f"{DB_URL}/users/{nick_f.value}/pass.json", json=hashlib.sha256(pass_f.value.encode()).hexdigest()))
            ], horizontal_alignment="center", spacing=15),
            padding=40
        )
        page.update()

    def show_chat_select(nick):
        main_container.content = ft.Column([
            ft.AppBar(title=ft.Text(f"Привет, {nick}"), bgcolor=HoshinoTheme.ACCENT),
            ft.Container(
                content=ft.Column([
                    ft.Text("Выберите чат или создайте новый", color=HoshinoTheme.CYAN),
                    ft.ElevatedButton("Демо-чат", on_click=lambda _: show_chat_room("demo", nick))
                ], horizontal_alignment="center"),
                padding=20
            )
        ])
        page.update()

    def show_chat_room(room_id, nick):
        msgs = ft.Column(scroll="always", expand=True)
        input_f = ft.TextField(hint_text="Сообщение...", expand=True)

        def send(e):
            # Если cryptography нет, используем fallback
            raw_text = input_f.value
            if libs_status["cryptography"] == "OK":
                # Здесь была бы логика Fernet, но для стабильности юзаем fallback если боимся вылета
                enc = fallback_crypt(raw_text, "key123")
            else:
                enc = fallback_crypt(raw_text, "key123")
            
            requests.post(f"{DB_URL}/rooms/{room_id}/m.json", json={"u": nick, "t": enc, "ts": time.time()})
            input_f.value = ""
            page.update()

        main_container.content = ft.Column([
            ft.AppBar(title=ft.Text(f"Комната: {room_id}")),
            msgs,
            ft.Row([input_f, ft.IconButton(ft.icons.SEND, on_click=send)], padding=10)
        ])
        page.update()

    # Запускаем приложение в отдельном потоке, чтобы интерфейс не вис
    threading.Thread(target=start_app, daemon=True).start()

ft.app(target=main)