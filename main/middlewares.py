from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.http import HttpResponse, HttpRequest


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
