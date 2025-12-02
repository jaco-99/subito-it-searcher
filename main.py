from nicegui import ui, app, run
import subito_searcher as backend

# Conf
PORTA = 5000
TIMEOUT = 20

# Global state
state = {
    'active': False,
    'telegram_enabled': True
}

daemon_timer = None

async def scheduled_check():
    """Questa funzione gira sul server indipendentemente dalla pagina"""
    if state['active']:
        await run.io_bound(backend.refresh, state['telegram_enabled'])


def toggle_daemon():
    state['active'] = not state['active']
    refresh_ui_state()

def toggle_telegram(e):
    state['telegram_enabled'] = e.value

def refresh_ui_state():
    """Aggiorna i colori e le scritte in base allo stato globale"""
    if state['active']:
        status_label.set_text('ACTIVE')
        status_label.classes('bg-green-500')
    else:
        status_label.set_text('NOT ACTIVE')
        status_label.classes('bg-red-500')

def update_logs():
    """Funzione locale della pagina per leggere i log"""
    logs_label.set_text('\n'.join(backend.get_logs()))

# --- USER INTERFACE ---
@ui.page('/')
def main_page():
    global status_label, logs_label

    # --- PAGE LAYOUT ---
    with ui.column().classes('w-full max-w-3xl mx-auto p-4'):

        # Title and state
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Subito Scraper Manager').classes('text-3xl font-bold')
            status_label = ui.label('INIT...').classes('text-white p-2 rounded font-bold')

        ui.separator()

        # Run control
        with ui.card().classes('w-full bg-gray-50'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.switch('Enable Telegram Notifications', value=state['telegram_enabled'], on_change=toggle_telegram).props('color=green')

                with ui.row().classes('gap-4'):
                    ui.button('Start/Stop Daemon', on_click=toggle_daemon)
                    ui.button('Run manual check', on_click=scheduled_check).props('outline')

        # Add new search
        with ui.card().classes('w-full mt-4'):
            ui.label('New search').classes('text-xl')
            with ui.grid(columns=2).classes('w-full gap-2'):
                name_input = ui.input('Name (es. iPhone)')
                url_input = ui.input('Subito URL').classes('col-span-2')
                min_input = ui.input('Min price')
                max_input = ui.input('Max price')

            def add_btn_click():
                if url_input.value and name_input.value:
                    backend.add(url_input.value, name_input.value, min_input.value or "null", max_input.value or "null")
                    backend.save_queries()
                    refresh_search_list.refresh()
                    url_input.value = ''
                    name_input.value = ''
                    ui.notify('Search added!')

            ui.button('Save search', on_click=add_btn_click).classes('mt-2 w-full')

        # Searches list
        ui.label('Active Searches').classes('text-xl mt-6')
        refresh_search_list()

        # Logs
        with ui.expansion('Activity logs', icon='list', value=True).classes('w-full mt-4'):
            with ui.scroll_area().classes('w-full h-64 bg-gray-900 text-green-400 p-2 rounded border border-gray-700'):
                logs_label = ui.label('Waiting...').style('white-space: pre-wrap; font-family: monospace')

    refresh_ui_state()

    ui.timer(2.0, update_logs)

@ui.refreshable
def refresh_search_list():
    if not backend.queries:
        ui.label('No active searches.').classes('text-gray-400 italic')
        return

    for name, details in backend.queries.items():
        with ui.card().classes('w-full mb-2 p-2 flex justify-between items-center'):
            with ui.column():
                ui.label(name).classes('font-bold text-lg')
                ui.label('Search saved').classes('text-xs text-gray-500')
            ui.button(icon='delete', color='red', on_click=lambda n=name: delete_search_wrapper(n)).props('flat')

def delete_search_wrapper(name):
    backend.delete(name)
    backend.save_queries()
    refresh_search_list.refresh()

app.timer(TIMEOUT, scheduled_check)

ui.run(host='127.0.0.1', port=PORTA, title='Subito Scraper')