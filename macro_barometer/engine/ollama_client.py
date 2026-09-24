"""Validated local Ollama geopolitical heuristic with safe neutral fallback."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from pydantic import BaseModel, Field, ValidationError


class GeoExtraction(BaseModel):
    # Forcing the LLM to output reasoning FIRST drastically reduces hallucinations
    reasoning: str = Field(description="Step-by-step reasoning evaluating the headlines against the rubric.")
    hormuz_shipping_threat: int = Field(ge=1, le=5)
    refinery_strike_damage: int = Field(ge=1, le=5)
    peace_deescalation_signals: int = Field(ge=1, le=5)
    key_geopolitical_summary: str = Field(min_length=3, max_length=500)

    def score(self) -> float:
        # 1-5 scale mapped to a 0-100 fragility score
        weighted = self.hormuz_shipping_threat * .45 + self.refinery_strike_damage * .45 + (6 - self.peace_deescalation_signals) * .10
        return round(((weighted - 1) / 4) * 100, 1)

    def as_record(self) -> dict[str, object]:
        return {**self.model_dump(), "summary": self.key_geopolitical_summary, "score": self.score()}


NEUTRAL = {
    "hormuz_shipping_threat": 3, "refinery_strike_damage": 3, "peace_deescalation_signals": 3,
    "summary": "Local geopolitical model was unavailable; a neutral score is in use.", "score": 50.0,
}


def assess_news(headlines: Sequence[str], host: str, model: str, timeout_seconds: int = 60) -> tuple[dict[str, object], str]:
    if not headlines:
        return NEUTRAL.copy(), "no headlines available"
        
    prompt = """You are a strict geopolitical intelligence analyst. Your task is to evaluate systemic macro risks based ONLY on the provided headlines. 
Ignore hypothetical scenarios, opinion pieces, and historical retrospectives. Only score based on currently occurring, factual events.

Scoring Rubric (1-5):
- hormuz_shipping_threat: 1=Normal transit; 2=Verbal political threats; 3=Minor harassment/seizures; 4=Major damage to vessels; 5=Active military blockade/closure.
- refinery_strike_damage: 1=No attacks; 2=Unsuccessful drone/missile attempts; 3=Minor damage/quick repair; 4=Major regional capacity offline; 5=Critical global supply outage.
- peace_deescalation_signals: 1=Active escalation/no talks; 2=Hardline rhetoric; 3=Stalemate/ongoing conflict; 4=Ceasefire talks progressing; 5=Signed peace treaties.

Return ONLY a JSON object matching this schema exactly. Provide your reasoning first, then the scores, then a summary.
{
  "reasoning": "Brief analysis of the factual events vs the rubric...",
  "hormuz_shipping_threat": 1,
  "refinery_strike_damage": 1,
  "peace_deescalation_signals": 1,
  "key_geopolitical_summary": "One concise sentence summarizing the actual factual events."
}

HEADLINES:
""" + "\n".join(f"- {item}" for item in headlines[:30])

    last_error = "unknown local model error"
    for _ in range(2):
        try:
            from ollama import Client
            client = Client(host=host, timeout=timeout_seconds)
            # Temperature set to 0.0 for maximum determinism (fact extraction vs creative writing)
            response = client.chat(model=model, messages=[{"role": "user", "content": prompt}], format="json", options={"temperature": 0.0})
            content = response["message"]["content"]
            parsed = GeoExtraction.model_validate(json.loads(content))
            return parsed.as_record(), "ok"
        except (Exception, ValidationError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            
    return NEUTRAL.copy(), f"ollama fallback after retry: {last_error}"