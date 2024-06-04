from typing import Any
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpResponse, HttpRequest
from django.utils import translation


class HealthCheckMiddleware:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest):
        if request.path == "/health":
            return HttpResponse("ok")
        return await self.get_response(request)


class DisableAdminI18nMiddleware:
    async_capable = True
    sync_capable = False

    def __init__(self, get_response) -> None:
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    async def __call__(self, request: HttpRequest) -> Any:
        if request.path.startswith("/admin"):
            translation.activate("en")

        return await self.get_response(request)
