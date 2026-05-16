import flet as ft

def main(page: ft.Page):
    page.theme_mode = ft.ThemeMode.LIGHT
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.add(
        ft.Row(
            [ft.Text("Привет из GitHub Actions!", size=25, weight="bold")],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        ft.Row(
            [ft.ElevatedButton("Работает!")],
            alignment=ft.MainAxisAlignment.CENTER,
        )
    )

if __name__ == "__main__":
    ft.app(target=main)