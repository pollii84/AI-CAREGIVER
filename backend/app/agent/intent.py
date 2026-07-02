"""Intent classifier — Architecture doc §4.

Emergency signals bypass the LLM entirely and go straight to the alert path
(Architecture doc §6: "no LLM in the critical alert path — latency and
reliability requirements exclude it"). This is a keyword-based stub;
Testing doc §4 flags the interaction with revoked fall-location consent as
still needing a product decision, and this classifier's precision/recall is
itself an open item for the adversarial test suite (Testing doc §2.1).
"""

_EMERGENCY_KEYWORDS = (
    "fell",
    "fallen",
    "falling",
    "can't breathe",
    "cant breathe",
    "chest pain",
    "emergency",
    "call 911",
    "unconscious",
    "severe pain",
)


def is_emergency_signal(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _EMERGENCY_KEYWORDS)
