import time
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date

ADMIN_SESSION_COOKIE = "admin_sessionid"


class SplitSessionMiddleware:
    """
    前台使用 'sessionid' cookie，/admin/ 使用 'admin_sessionid' cookie。
    兩套 session 完全隔離，互不影響，可同時保持各自登入狀態。
    """

    def __init__(self, get_response):
        self.get_response = get_response
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def _cookie_name(self, request):
        if request.path.startswith("/admin/"):
            return ADMIN_SESSION_COOKIE
        return settings.SESSION_COOKIE_NAME

    def __call__(self, request):
        cookie_name = self._cookie_name(request)
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)

        response = self.get_response(request)

        try:
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        # Session 已清空且 cookie 存在 → 刪除 cookie
        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ("Cookie",))
        elif modified or settings.SESSION_SAVE_EVERY_REQUEST:
            if request.session.get_expire_at_browser_close():
                max_age = None
                expires = None
            else:
                max_age = request.session.get_expiry_age()
                expires = http_date(time.time() + max_age)

            if response.status_code != 500:
                try:
                    request.session.save()
                except UpdateError:
                    pass
                response.set_cookie(
                    cookie_name,
                    request.session.session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=settings.SESSION_COOKIE_SECURE or request.is_secure(),
                    httponly=settings.SESSION_COOKIE_HTTPONLY,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
                patch_vary_headers(response, ("Cookie",))

        return response
