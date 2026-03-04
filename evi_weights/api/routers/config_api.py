"""Config endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from evi_weights.api.dependencies import get_config, set_config
from evi_weights.api.routers.calculate import _apply_overrides
from evi_weights.api.schemas import ConfigOverrides
from evi_weights.config import EVIConfig
from evi_weights.db.repository import _config_to_json

import json

router = APIRouter(tags=["config"])


@router.get("/config")
def read_config(config: EVIConfig = Depends(get_config)):
    return json.loads(_config_to_json(config))


@router.put("/config")
def update_config(
    overrides: ConfigOverrides,
    config: EVIConfig = Depends(get_config),
):
    updated = _apply_overrides(config, overrides)
    set_config(updated)
    return json.loads(_config_to_json(updated))
