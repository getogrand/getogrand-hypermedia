from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


async def index(request: HttpRequest) -> HttpResponse:
    return render(request=request, template_name="main/index.html")
