from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

import app as legacy

router = APIRouter()


@router.get('/')
def root_page():
    return legacy.root_page()


@router.get('/favicon.svg')
def favicon_svg():
    return legacy.favicon_svg()


@router.get('/health')
def health():
    return legacy.health()


@router.get('/setup', response_class=HTMLResponse)
def setup_page(request: Request):
    return legacy.setup_page(request)


@router.get('/download/project.zip')
def download_project_zip():
    return legacy.download_project_zip()


@router.get('/changelog', response_class=HTMLResponse)
def changelog_page():
    return legacy.changelog_page()


@router.get('/app', response_class=HTMLResponse)
def app_shell():
    return legacy.app_shell_page()


@router.get('/dashboard', response_class=HTMLResponse)
def dashboard_page(request: Request):
    return legacy.dashboard_page(request)


@router.get('/grow-guide', response_class=HTMLResponse)
def grow_guide_page(request: Request):
    return legacy.grow_guide_page(request)


@router.get('/poll-errors', response_class=HTMLResponse)
def poll_errors_page(request: Request):
    return legacy.poll_errors_page(request)


@router.get('/api/poll-errors')
def api_poll_errors(request: Request):
    return legacy.api_poll_errors(request)


@router.get('/api/export')
def api_export(tent_id: int, range: str = '24h'):
    return legacy.export_history_csv(tent_id, range)


@router.get('/api/history')
def api_history(
    deviceId: str | None = None,
    hours: int | None = None,
    from_ts: str | None = Query(default=None, alias='from'),
    to: str | None = None,
):
    return legacy.api_history_for_device(deviceId, hours=hours, limit=50, from_ts=from_ts, to_ts=to)


@router.get('/config/backup/export')
def config_backup_export():
    return legacy.export_config_backup()


@router.post('/config/backup/import')
def config_backup_import(payload: dict):
    return legacy.import_config_backup(payload)


@router.get('/config/guests')
def config_guests():
    return legacy.get_guest_users_config()


@router.post('/config/guests')
def config_guests_create(payload: legacy.GuestUserCreatePayload):
    return legacy.create_guest_user(payload)


@router.put('/config/guests/{guest_id}')
def config_guests_update(guest_id: int, payload: legacy.GuestUserUpdatePayload):
    return legacy.update_guest_user(guest_id, payload)


@router.delete('/config/guests/{guest_id}')
def config_guests_delete(guest_id: int):
    return legacy.delete_guest_user(guest_id)
