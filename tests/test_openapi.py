from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from stt_api.main import app  # noqa: E402


def test_swagger_exposes_binary_file_upload() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/transcribe"]["post"]
    body = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    if "$ref" in body:
        body = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]
    file_schema = body["properties"]["file"]
    assert file_schema["type"] == "string"
    assert file_schema["format"] == "binary"


def test_openai_compatible_route_is_documented() -> None:
    schema = app.openapi()
    assert "post" in schema["paths"]["/v1/audio/transcriptions"]


def test_upload_ui_is_packaged() -> None:
    assert (ROOT / "services" / "api" / "stt_api" / "static" / "index.html").is_file()
