"""Structured-output schema for the Care Agent — Architecture doc §4.

Every response is forced into this shape via `output_config.format` on the
Claude Sonnet 5 call. `citations` is populated only from tool-result content
(search_corpus / search_trials), never asserted by the model directly — the
output validator (pipeline.py) checks that separately.
"""

AGENT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "title": {"type": "string"},
                    "corpus_or_trial": {"type": "string", "enum": ["corpus", "trial"]},
                },
                "required": ["source_id", "title", "corpus_or_trial"],
                "additionalProperties": False,
            },
        },
        "disclaimer": {"type": "string"},
        "escalate": {
            "type": "boolean",
            "description": "true if this answer should surface a 'Talk to your care team' CTA per Product/UX doc §4",
        },
    },
    "required": ["answer", "citations", "disclaimer", "escalate"],
    "additionalProperties": False,
}
