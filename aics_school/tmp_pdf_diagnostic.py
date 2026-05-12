import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aics_school.settings")
import django

django.setup()
from django.test import Client

client = Client()
for pk in [2, 3]:
    print("=== report", pk, "===")
    r = client.get(f"/report/{pk}/pdf/", HTTP_HOST="127.0.0.1")
    print("status", r.status_code)
    print("Content-Type", r.get("Content-Type"))
    print("Content-Length", r.get("Content-Length"))
    print("Content-Range", r.get("Content-Range"))
    print("Accept-Ranges", r.get("Accept-Ranges"))
    content = (
        b"".join(r.streaming_content) if hasattr(r, "streaming_content") else r.content
    )
    print("len", len(content))
    print("first4", content[:4])
    r2 = client.get(f"/report/{pk}/pdf/", HTTP_HOST="127.0.0.1", HTTP_RANGE="bytes=0-3")
    print("range status", r2.status_code)
    print("range Content-Type", r2.get("Content-Type"))
    print("range Content-Length", r2.get("Content-Length"))
    print("range Content-Range", r2.get("Content-Range"))
    print("range Accept-Ranges", r2.get("Accept-Ranges"))
    print(
        "range first4",
        (
            b"".join(r2.streaming_content)
            if hasattr(r2, "streaming_content")
            else r2.content
        ),
    )
