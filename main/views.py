from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Profile


async def index(request: HttpRequest) -> HttpResponse:
    profile = (
        await Profile.objects.prefetch_related(
            "experience_set__duty_set__dutyitem_set__dutysubitem_set",
        )
        .filter(email="getogrand@hey.com")
        .afirst()
    )
    assert profile is not None
    return render(
        request=request,
        template_name="main/index.html",
        context={
            "profile": profile,
        },
    )
