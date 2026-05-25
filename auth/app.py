"""Мини-сервис авторизации для цифрового ассистента РТУ МИРЭА.
Без БД: проверяет логин/пароль из env и выдаёт подписанный cookie-токен (HMAC).
nginx через auth_request дёргает /verify, чтобы пускать только с валидным токеном."""
import base64
import hashlib
import hmac
import os
import time

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import JSONResponse

# Учётные данные: "user1:pass1,user2:pass2". По умолчанию — admin/mirea (поменять в .env!).
_RAW_USERS = os.getenv("AUTH_USERS", "admin:mirea")
USERS = dict(
    pair.split(":", 1) for pair in _RAW_USERS.split(",") if ":" in pair
)
SECRET = os.getenv("SESSION_SECRET", "change-me-please").encode("utf-8")
COOKIE = "mirea_session"
TTL = int(os.getenv("SESSION_TTL", str(60 * 60 * 12)))  # 12 часов

app = FastAPI(title="Auth")


def _sign(payload: str) -> str:
    sig = hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


def make_token(username: str) -> str:
    exp = str(int(time.time()) + TTL)
    payload = f"{username}|{exp}"
    body = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{body}.{_sign(payload)}"


def valid_token(token: str) -> bool:
    try:
        body, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(body.encode("ascii")).decode("utf-8")
        if not hmac.compare_digest(sig, _sign(payload)):
            return False
        _, exp = payload.rsplit("|", 1)
        return int(exp) > int(time.time())
    except Exception:
        return False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)) -> Response:
    if USERS.get(username) != password:
        return JSONResponse({"ok": False, "error": "Неверный логин или пароль"}, status_code=401)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        COOKIE, make_token(username),
        max_age=TTL, httponly=True, samesite="lax", path="/",
    )
    return resp


@app.get("/verify")
async def verify(request: Request) -> Response:
    token = request.cookies.get(COOKIE, "")
    if valid_token(token):
        return Response(status_code=204)
    return Response(status_code=401)


@app.post("/logout")
async def logout() -> Response:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path="/")
    return resp
