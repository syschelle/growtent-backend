from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

import app as legacy
from services.tent_service import TentService
from core.dependencies import get_tent_service

router = APIRouter()


@router.get('/auth/login', response_class=HTMLResponse)
def login_page():
    return legacy.auth_login_page()


@router.post('/auth/login')
def login(payload: legacy.LoginPayload, request: Request):
    return legacy.auth_login(payload, request)


@router.post('/auth/login/2fa')
def login_2fa(payload: legacy.Login2FAPayload, request: Request):
    return legacy.auth_login_2fa(payload, request)


@router.post('/auth/logout')
def logout(request: Request):
    return legacy.auth_logout(request)


@router.get('/auth/qr.png')
def auth_qr_png(token: str, request: Request):
    return legacy.auth_qr_png(token, request)


@router.post('/auth/step-up')
def auth_step_up(payload: legacy.StepUpPayload, request: Request):
    return legacy.auth_step_up(payload, request)


@router.get('/auth/step-up/status')
def auth_step_up_status(request: Request):
    return legacy.auth_step_up_status(request)


@router.get('/auth/whoami')
def auth_whoami(request: legacy.Request):
    return legacy.auth_whoami(request)


@router.get('/config/auth')
def get_auth_config():
    return legacy.get_auth_config()


@router.post('/config/auth', dependencies=[Depends(legacy.require_recent_admin_confirmation)])
def save_auth_config(payload: legacy.AuthConfigPayload, request: Request):
    return legacy.set_auth_config(payload, request)


@router.post('/config/auth/2fa', dependencies=[Depends(legacy.require_recent_admin_confirmation)])
def auth_2fa_setup(payload: legacy.TwoFAConfigPayload, request: Request):
    return legacy.set_2fa_config(payload, request)


@router.post('/config/auth/2fa/verify', dependencies=[Depends(legacy.require_recent_admin_confirmation)])
def auth_2fa_verify(payload: legacy.TwoFAVerifyPayload, request: Request):
    return legacy.verify_2fa_setup(payload, request)
