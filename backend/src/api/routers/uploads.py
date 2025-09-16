from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.models import Asset, AssetType
from src.api.store import ASSETS, generate_id

router = APIRouter(tags=["uploads"])


class AssetCreateResponse(BaseModel):
    asset: Asset


@router.post(
    "",
    summary="Register uploaded file",
    description="MVP: Accepts an upload and registers an Asset in-memory. File bytes are discarded.",
    response_model=AssetCreateResponse,
)
async def upload_asset(
    file: UploadFile = File(..., description="Binary file to upload."),
    owner_id: Optional[str] = Form(None, description="Owner user ID (MVP optional)."),
) -> AssetCreateResponse:
    """
    PUBLIC_INTERFACE
    Register a new uploaded asset.

    Returns:
        AssetCreateResponse: Registered asset metadata.
    """
    # MVP: do not store the file, only record metadata
    asset_id = generate_id("asset")
    asset = Asset(
        id=asset_id,
        filename=file.filename,
        content_type=file.content_type,
        asset_type=_infer_asset_type(file.content_type or ""),
        size_bytes=None,
        url=f"/mock/storage/{asset_id}/{file.filename}",
        owner_id=owner_id,
    )
    ASSETS[asset_id] = asset
    return AssetCreateResponse(asset=asset)


@router.get(
    "",
    summary="List assets",
    description="List all registered assets (MVP in-memory).",
)
def list_assets():
    """
    PUBLIC_INTERFACE
    List all assets.

    Returns:
        dict: {"items": [Asset, ...]}
    """
    return {"items": list(ASSETS.values())}


@router.get(
    "/{asset_id}",
    summary="Get asset by ID",
    description="Fetch a single asset by ID.",
)
def get_asset(asset_id: str):
    """
    PUBLIC_INTERFACE
    Get a single asset.

    Args:
        asset_id (str): Asset ID

    Returns:
        Asset
    """
    asset = ASSETS.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _infer_asset_type(content_type: str) -> AssetType:
    if content_type.startswith("audio/"):
        return AssetType.audio
    if content_type.startswith("video/"):
        return AssetType.video
    return AssetType.unknown
