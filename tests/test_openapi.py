from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from stt_api.main import app  # noqa: E402


def multipart_schema(path: str) -> dict:
    schema = app.openapi()
    body = schema["paths"][path]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    if "$ref" in body:
        body = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]
    return body


def test_swagger_exposes_binary_file_upload() -> None:
    body = multipart_schema("/v1/audio/transcriptions")
    file_schema = body["properties"]["file"]
    assert file_schema["type"] == "string"
    assert file_schema["format"] == "binary"


def test_openai_compatible_route_is_documented() -> None:
    schema = app.openapi()
    assert "post" in schema["paths"]["/v1/audio/transcriptions"]
    assert {"file", "model"}.issubset(multipart_schema("/v1/audio/transcriptions")["required"])
    assert "get" in schema["paths"]["/v1/models"]
    assert schema["paths"]["/api/transcribe"]["post"]["deprecated"] is True


def test_openai_validation_error_and_request_id() -> None:
    response = TestClient(app).post("/v1/audio/transcriptions")
    assert response.status_code == 400
    assert set(response.json()["error"]) == {"message", "type", "param", "code"}
    assert response.headers["x-request-id"].startswith("req_")


def test_openai_unknown_model_error() -> None:
    response = TestClient(app).post(
        "/v1/audio/transcriptions",
        data={"model": "unknown-model"},
        files={"file": ("test.wav", b"not-audio", "audio/wav")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_upload_ui_is_packaged() -> None:
    assert (ROOT / "services" / "api" / "stt_api" / "static" / "index.html").is_file()
