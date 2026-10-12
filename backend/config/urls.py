"""URL Configuration for trucksafe."""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse
from django.urls import include, path, re_path

urlpatterns = [
    path("api/", include("trucksafe.api.urls")),
]


# Catch-all view for SPA when dist is present
def serve_spa(request: HttpRequest) -> HttpResponse:
    dist_index = Path(settings.BASE_DIR).parent / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return FileResponse(open(dist_index, "rb"))
    return HttpResponse(
        "<h1>TruckSafe Backend API is running</h1><p>Visit <code>/api/health</code></p>",
        content_type="text/html",
    )


urlpatterns += [
    re_path(r"^(?!api/).*$", serve_spa, name="spa-catchall"),
]
