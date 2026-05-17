import flet as ft
import traceback
import sys
import time
import json
import hashlib
import base64
import urllib.request
import threading

# --- КОНФИГУРАЦИЯ ---
DB_URL = "https://mess-f848e-default-rtdb.europe-west1.firebasedatabase.app"

def main(page: ft.Page):
    # Настройки страницы
    page.title = "Hoshino Debug Tool"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#12131a"
    page.scroll = "always"
    
    # 1. Сразу создаем контейнер для вывода ошибок
    error_text = ft.Text(color="red", size=12, selectable=True)
    status_text = ft.Text("Запуск системы...", color="cyan")
    
    debug_container = ft.Column([
        ft.Text("HOSHINO DEBUG CONSOLE", weight="bold", color="pink"),
        status_text,
        error_text
    ], visible=True)

    page.add(debug_container)
    page.update()

    # --- ФУНКЦИЯ-ОБОЛОЧКА ДЛЯ БЕЗОПАСНОГО ЗАПУСКА ---
    def safe_run():
        try:
            status_text.value = "Проверка библиотек..."
            page.update()
            
            # Попробуем выполнить основной код
            run_logic()
            
        except Exception:
            # Если что-то упало — выводим ПОЛНЫЙ текст ошибки на экран
            status_text.value = "КРИТИЧЕСКАЯ ОШИБКА ПРИЛОЖЕНИЯ:"
            status_text.color = "red"
            error_text.value = traceback.format_exc()
            page.update()

    # --- ОСНОВНАЯ ЛОГИКА ПРИЛОЖЕНИЯ ---
    def run_logic():
        status_text.value = "Инициализация интерфейса..."
        page.update()

        # Простой XOR шифр (чистый Python)
        def hoshino_crypt(text, key, decrypt=False):
            k = hashlib.sha256(key.encode()).digest()
            raw = base64.b64decode(text) if decrypt else text.encode()
            res = bytes([b ^ k[i % len(k)] for i, b in enumerate(raw)])
            return res.decode('utf-8', errors='ignore') if decrypt else base64.b64encode(res).decode()

        # Сетевой запрос (чистый Python)
        def firebase_get(path):
            url = f"{DB_URL}{path}.json"
            with urllib.request.urlopen(url, timeout=5) as r:
                return json.loads(r.read().decode())

        # Рендерим форму входа
        status_text.value = "Загрузка экрана входа..."
        page.update()
        
        nick_input = ft.TextField(label="Никнейм", border_color="pink")
        
        def on_login_click(e):
            try:
                status_text.value = f"Связь с базой {DB_URL}..."
                page.update()
                data = firebase_get(f"/users/{nick_input.value}/pass")
                if data:
                    status_text.value = "Успешный вход!"
                    debug_container.visible = False # Прячем дебаг если всё ок
                    page.add(ft.Text(f"Добро пожаловать, {nick_input.value}!", size=30))
                else:
                    status_text.value = "Пользователь не найден"
                page.update()
            except Exception:
                error_text.value = traceback.format_exc()
                page.update()

        # Очищаем экран и добавляем UI
        page.clean()
        page.add(
            ft.Column([
                ft.Text("HOSHINO MESSENGER", size=32, weight="bold", color="pink"),
                nick_input,
                ft.ElevatedButton("ВОЙТИ", on_click=on_login_click),
                ft.Divider(),
                debug_container # Оставляем дебаг снизу для контроля
            ], horizontal_alignment="center")
        )
        page.update()

    # Запускаем через небольшую паузу, чтобы Flet успел прогрузить страницу
    threading.Timer(1, safe_run).start()

# Запуск приложения
try:
    ft.app(target=main)
except Exception:
    # Этот блок сработает, если упадет сам Flet
    print(traceback.format_exc())