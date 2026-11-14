"""Ask Gemma what a camera frame shows and compare it with MediaPipe's claim for that frame."""

import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field

from pulsar.ollama import chat

State = Literal["open", "closed"]

PROMPT = """\
You check a face-tracking system. Look only at the picture and report what is clearly visible.
eyes: "open" or "closed" (both eyes together; "unclear" if you cannot see them or they disagree).
mouth: "open" (lips clearly apart, like talking widely or yawning) or "closed"; "unclear" if not visible.
person: true if one human face is visible.
Never guess: answer "unclear" when unsure."""

SCHEMA = {
    "type": "object",
    "properties": {
        "person": {"type": "boolean"},
        "eyes": {"enum": ["open", "closed", "unclear"]},
        "mouth": {"enum": ["open", "closed", "unclear"]},
    },
    "required": ["person", "eyes", "mouth"],
}


class Claim(BaseModel):
    eyes: State = Field(description="What MediaPipe says for this frame (eye-blink blendshapes above 0.5 = closed)")
    mouth: State = Field(description="What MediaPipe says (jawOpen above 0.35 = open)")


class Seen(BaseModel):
    person: bool
    eyes: Literal["open", "closed", "unclear"]
    mouth: Literal["open", "closed", "unclear"]


def look(image_b64: str) -> Seen:
    content = chat([{"role": "system", "content": PROMPT},
                    {"role": "user", "content": "What does this frame show?", "images": [image_b64]}],
                   options={"temperature": 0, "num_predict": 40}, fmt=SCHEMA)
    return Seen.model_validate(json.loads(content))


def agreement(claim: Claim, seen: Seen) -> dict[str, bool | None]:
    """True or False per feature; None when Gemma could not tell, which is not counted either way."""
    def same(mine: str, theirs: str) -> bool | None:
        return None if theirs == "unclear" or not seen.person else mine == theirs
    return {"eyes": same(claim.eyes, seen.eyes), "mouth": same(claim.mouth, seen.mouth)}


def verify(image_b64: str, claim: Claim) -> dict[str, Any]:
    started = time.perf_counter()
    seen = look(image_b64)
    return {"ai": seen.model_dump(), "claim": claim.model_dump(), "agrees": agreement(claim, seen),
            "ms": round((time.perf_counter() - started) * 1000, 1)}
