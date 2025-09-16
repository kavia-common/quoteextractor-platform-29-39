import json
import os

"""
Generate OpenAPI specification for the FastAPI app.

This script imports the FastAPI app which already registers all routers:
- uploads (/api/uploads)
- transcripts (/api/transcripts)
- quotes (/api/quotes)
- exports (/api/exports)
- status (/api/status)
- auth (/auth)

It then invokes app.openapi() to produce the full OpenAPI schema including
paths, components (schemas), tags, and metadata and writes it to
backend/interfaces/openapi.json.
"""

# Importing app builds and registers all routes/schemas via module side-effects
from src.api.main import app  # noqa: E402


def _generate_openapi_dict() -> dict:
    """
    Build the OpenAPI dictionary from the FastAPI app.
    """
    # FastAPI builds the OpenAPI on demand and caches it;
    # calling once ensures the latest routers are reflected.
    return app.openapi()


def _write_openapi(schema: dict, out_path: str) -> None:
    """
    Write the OpenAPI schema as pretty-printed JSON.
    """
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    """
    Entry point for generating the OpenAPI JSON file.
    """
    # Ensure output directory exists relative to backend/
    output_dir = "interfaces"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "openapi.json")

    schema = _generate_openapi_dict()

    # Basic validation: confirm key sections exist
    if not isinstance(schema, dict) or "openapi" not in schema or "paths" not in schema:
        raise RuntimeError("Failed to generate a valid OpenAPI schema from app.")

    # Write file
    _write_openapi(schema, output_path)

    # Optional: print a short confirmation for CLI users
    print(f"Wrote OpenAPI spec to {output_path} with {len(schema.get('paths', {}))} paths.")


if __name__ == "__main__":
    main()
