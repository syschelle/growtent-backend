from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

import app as legacy
from services.tent_service import TentService
from core.dependencies import get_tent_service

router = APIRouter()


@router.get('/auth/login', response_class=HTMLResponse)
def login_page():
    return legacy.auth_login_page()


@router.post('/auth/login')
def login(payload: legacy.LoginPayload):
    return legacy.auth_login(payload)


@router.post('/auth/login/2fa')
def login_2fa(payload: legacy.Login2FAPayload):
    return legacy.auth_login_2fa(payload)


@router.post('/auth/logout')
def logout():
    return legacy.auth_logout()


@router.get('/auth/qr.png')
def auth_qr_png(u: str):
    return legacy.auth_qr_png(u)


@router.get('/auth/whoami')
def auth_whoami(request: legacy.Request):
    return legacy.auth_whoami(request)


@router.get('/config/auth')
def get_auth_config():
    return legacy.get_auth_config()


@router.post('/config/auth')
def save_auth_config(payload: legacy.AuthConfigPayload):
    return legacy.set_auth_config(payload)


@router.post('/config/auth/2fa')
def auth_2fa_setup(payload: legacy.TwoFAConfigPayload):
    return legacy.set_2fa_config(payload)


@router.post('/config/auth/2fa/verify')
def auth_2fa_verify(payload: legacy.TwoFAVerifyPayload):
    return legacy.verify_2fa_setup(payload)
