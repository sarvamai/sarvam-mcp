"""Sarvam Prism — calibrated decisions (yes/no, pick-one, ordered scale).

  POST /v2/systemone      synchronous JSON, model `sarvam-prism`

Prism is a decision model: it generates no text, it scores the options you give
it and returns a probability for each. Several questions can share one `state`,
and the state is billed once per request.
"""

from __future__ import annotations

from typing import Any, Literal

from fastmcp import Context, FastMCP
from pydantic import Field

from sarvam_mcp.observability import measure_tool
from sarvam_mcp.tools._common import ready_ctx

PRISM_PATH = "/v2/systemone"
PRISM_MODEL = "sarvam-prism"

QuestionKind = Literal["noul", "choice", "score"]
_QUESTION_KEYS = {"type", "instructions", "criteria"}
_CHOICE_OPTIONS = (2, 255)
_SCORE_LEVELS = (2, 10)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="sarvam_tools_prism_decide",
        description=(
            "Runtime tool — calls Sarvam API now. For code-writing help, use sarvam_code_* tools.\n\n"
            "Ask Sarvam Prism (POST /v2/systemone) yes/no, pick-one, or ordered-scale "
            "questions about some input and get a calibrated probability for every option. "
            "It generates no text, so there is nothing to parse. Use it for routing, "
            "triage, moderation, intent, sentiment, or any decision you would otherwise "
            "prompt an LLM for and then parse.\n\n"
            "`state` is the input (text, or JSON). `questions` maps your own question id "
            "to {type, instructions, criteria}:\n"
            "- type 'noul' — yes/no. Answer: `noul` = probability of yes (0-1). "
            "`criteria` optional: {'true': '...', 'false': '...'}.\n"
            "- type 'choice' — pick one. `criteria` required: {option_id: description}, "
            "2-255 options. Answer: `choice` (top option), `confidence`, `probabilities`.\n"
            "- type 'score' — ordered scale. `criteria` required: list of level "
            "descriptions, LOWEST first, 2-10 levels (order matters). Answer: `score` "
            "(expected level, 0-based float), `confidence`, `legend`, `probabilities`.\n\n"
            "Ask all questions about one input in a single call — the state is billed once. "
            "Text/JSON only (no images); English, 10 Indian languages, Hinglish. Max 32,768 "
            "tokens per question; the state is never truncated. Probabilities can vary "
            "slightly between identical calls, so leave a margin around thresholds and "
            "judge on the top probability (`noul`, or `probabilities[choice]`), not on "
            "`confidence`. Indian-language answers clear a 0.9 threshold far less often "
            "than English ones, so plan more human review there."
        ),
    )
    async def sarvam_prism_decide(
        ctx: Context,
        state: str | dict[str, Any] | list[Any] = Field(
            description=(
                "The input to decide about: a string, or an object/array (sent as compact "
                "JSON). Shared by every question."
            ),
        ),
        questions: dict[str, dict[str, Any]] = Field(
            description=(
                "At least one question, keyed by an id you choose. Each is "
                "{'type': 'noul'|'choice'|'score', 'instructions': '...', 'criteria': ...}. "
                "Only those three keys are allowed. Example: "
                "{'refund': {'type': 'noul', 'instructions': 'Is the customer asking for a refund?'}, "
                "'team': {'type': 'choice', 'instructions': 'Which team owns this?', "
                "'criteria': {'billing': 'Payments and invoices', 'tech': 'Product bugs'}}, "
                "'urgency': {'type': 'score', 'instructions': 'How urgent is it?', "
                "'criteria': ['Can wait', 'Needs a reply today', 'Needs action now']}}"
            ),
        ),
    ) -> dict[str, Any]:
        _validate_questions(questions)
        sc = await ready_ctx(ctx)
        with measure_tool() as metrics:
            payload, call = await sc.client.post_json(
                PRISM_PATH,
                json_body={"model": PRISM_MODEL, "state": state, "questions": questions},
            )
            metrics.merge(call)

        body = payload if isinstance(payload, dict) else {}
        return {
            "model": body.get("model", PRISM_MODEL),
            "answers": body.get("answers"),
            "usage": body.get("usage"),
            "observability": metrics.to_response_block(),
        }


def _validate_questions(questions: dict[str, dict[str, Any]]) -> None:
    """Reject what the API would 422 on, before spending a call."""
    if not questions:
        raise ValueError("Provide at least one question.")
    for qid, question in questions.items():
        where = f"questions['{qid}']"
        unknown = set(question) - _QUESTION_KEYS
        if unknown:
            raise ValueError(
                f"{where}: unknown key(s) {sorted(unknown)}. "
                f"Allowed: {sorted(_QUESTION_KEYS)} (note `instructions`, plural)."
            )
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "noul":
            if criteria is not None and not isinstance(criteria, dict):
                raise ValueError(f"{where}: 'noul' criteria must be an object with 'true' and 'false'.")
        elif kind == "choice":
            lo, hi = _CHOICE_OPTIONS
            if not isinstance(criteria, dict) or not lo <= len(criteria) <= hi:
                raise ValueError(
                    f"{where}: 'choice' needs criteria as an object of option id -> "
                    f"description with {lo}-{hi} options."
                )
        elif kind == "score":
            lo, hi = _SCORE_LEVELS
            if not isinstance(criteria, list) or not lo <= len(criteria) <= hi:
                raise ValueError(
                    f"{where}: 'score' needs criteria as a list of {lo}-{hi} level "
                    "descriptions, lowest first."
                )
        else:
            raise ValueError(f"{where}: type must be 'noul', 'choice' or 'score' (lowercase); got {kind!r}.")
