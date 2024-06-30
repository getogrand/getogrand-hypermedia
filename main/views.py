import asyncio
import re
import json
import requests
from urllib.parse import urlparse, ParseResult
from django.core.exceptions import BadRequest
from django.http import HttpRequest, HttpResponse
from django.template import loader
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .forms import ProfileForm
from .models import Profile


def index(request: HttpRequest) -> HttpResponse:
    profile = (
        Profile.objects.prefetch_related(
            "experience_set__duty_set__dutyitem_set__dutysubitem_set",
        )
        .filter(email="getogrand@hey.com")
        .first()
    )
    assert profile is not None
    form = ProfileForm(profile=profile, data=request.GET if request.GET else None)
    form.full_clean()

    hx_target = request.headers.get("HX-Target")

    if not hx_target:
        return render(
            request=request,
            template_name="main/index.html",
            context={"profile": profile, "form": form},
        )

    if target_match := re.search(r"experience-(\d+)-(details|expand)", hx_target):
        experience_id = target_match.group(1)
        experience = profile.experience_set.get(pk=int(experience_id))
        render_results = [
            loader.render_to_string(
                template_name="main/index.html#experience_details",
                context={
                    "experience": experience,
                    "form": form,
                },
            ),
            loader.render_to_string(
                template_name="main/index.html#select", context={"form": form}
            ),
        ]
        return HttpResponse("\n".join(render_results))
    else:
        raise Exception(f"unknown target: {hx_target}")


@csrf_exempt
def sentry_tunnel(request: HttpRequest) -> HttpResponse:
    envelope = request.body
    piece = envelope.splitlines()[0]
    header = json.loads(piece)
    dsn: ParseResult = urlparse(header["dsn"])
    project_id: str = dsn.path.replace("/", "")

    sentry_hostname = "o303432.ingest.us.sentry.io"
    if dsn.hostname != sentry_hostname:
        raise BadRequest(f"invalid dsn hostname: {dsn.hostname}")
    if project_id != "4507459219685376":
        raise BadRequest(f"invalid project id: {project_id}")

    upstream_sentry_url = f"https://{sentry_hostname}/api/{project_id}/envelope/"
    requests.post(upstream_sentry_url, envelope)
    return HttpResponse("")
