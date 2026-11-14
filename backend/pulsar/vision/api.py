"""HTTP surface of the AI cross-check.

- POST /vision/verify   {image: base64 JPEG, claim: {eyes, mouth}} -> what Gemma sees and whether it agrees
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from pulsar.vision.verify import Claim, verify

router = APIRouter(tags=["vision"])
MAX_IMAGE_B64 = 4 * 2 * 1024 * 1024 // 3 + 4  # a 2 MB JPEG, the same limit as /vision/describe


class VerifyRequest(BaseModel):
    image: str = Field(min_length=8, max_length=MAX_IMAGE_B64, pattern=r"^/9j/[A-Za-z0-9+/]*={0,2}$")
    claim: Claim


@router.post("/vision/verify", summary="Gemma checks what MediaPipe measured on the same frame")
def verify_frame(body: VerifyRequest) -> dict:
    try:
        return verify(body.image, body.claim)
    except OSError as error:
        raise HTTPException(503, f"the vision model is not answering: {error}") from error
    except (json.JSONDecodeError, ValidationError) as error:
        raise HTTPException(502, f"the vision model broke the answer format: {error}") from error
