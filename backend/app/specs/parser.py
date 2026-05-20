from typing import Any

import yaml
from prance import ResolvingParser, ValidationError


def parse_openapi_spec(
    spec_content: str | bytes,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Parse an OpenAPI spec string/bytes, resolve references, and extract endpoints.

    Returns:
        A tuple of (version, raw_dict, endpoints_list).
    """
    if isinstance(spec_content, bytes):
        spec_content = spec_content.decode("utf-8")

    try:
        # Load spec and validate/resolve using prance
        parser = ResolvingParser(spec_string=spec_content, backend="openapi-spec-validator")
    except (ValidationError, yaml.YAMLError) as e:
        raise ValueError(f"Invalid OpenAPI specification: {e!s}") from e

    spec_dict = parser.specification
    version = spec_dict.get("info", {}).get("version", "unknown")

    endpoints: list[dict[str, Any]] = []

    paths = spec_dict.get("paths", {})
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            method_lower = method.lower()
            if method_lower not in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "options",
                "head",
            ]:
                continue

            endpoints.append(
                {
                    "method": method_lower,
                    "path": path,
                    "summary": operation.get("summary"),
                    "parameters": operation.get("parameters", []),
                    "request_body": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                }
            )

    return version, spec_dict, endpoints
