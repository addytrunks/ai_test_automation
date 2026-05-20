import pytest

from app.specs.parser import parse_openapi_spec

SAMPLE_SPEC = """
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: OK
    post:
      summary: Create user
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        '201':
          description: Created
"""


def test_parse_valid_spec() -> None:
    version, raw, endpoints = parse_openapi_spec(SAMPLE_SPEC)
    assert version == "1.0.0"
    assert len(endpoints) == 2

    methods = {e["method"] for e in endpoints}
    assert methods == {"get", "post"}

    get_ep = next(e for e in endpoints if e["method"] == "get")
    assert get_ep["path"] == "/users"
    assert get_ep["summary"] == "List users"


def test_parse_invalid_spec() -> None:
    with pytest.raises(ValueError):
        parse_openapi_spec("invalid yaml {")


def test_parse_spec_from_bytes() -> None:
    version, raw, endpoints = parse_openapi_spec(SAMPLE_SPEC.encode("utf-8"))
    assert version == "1.0.0"
    assert len(endpoints) == 2


def test_parse_spec_skips_non_http_methods() -> None:
    spec = """
openapi: 3.0.0
info:
  title: Test
  version: 0.1.0
paths:
  /items:
    get:
      summary: Get items
      responses:
        '200':
          description: OK
    parameters:
      - name: id
        in: query
        schema:
          type: string
"""
    version, raw, endpoints = parse_openapi_spec(spec)
    assert len(endpoints) == 1
    assert endpoints[0]["method"] == "get"
