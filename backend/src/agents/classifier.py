from src.models.schemas import ClassifierOutput
from src.models.provider import get_classifier_model

CLASSIFIER_PROMPT = """You are a routing classifier for a resume tailoring pipeline.

Given a user's follow-up message about their resume analysis, decide which pipeline steps need to re-run.

Pipeline steps:
1. JD Analysis - Parse job description into requirements
2. Gap Analysis - Compare requirements against resume + RAG chunks
3. Suggestions - Generate section-by-section rewrite suggestions
4. Rewrite - Generate the full rewritten resume

Rules:
- If the user provides NEW information about the JD: re-run from JD Analysis
- If the user mentions experience from another role/job: re-run from Gap Analysis
- If the user wants different emphasis or approach: re-run from Suggestions
- If the user wants wording/formatting changes only: re-run Rewrite only
- When in doubt, re-run from the earliest affected step (all downstream steps also re-run)

Examples:
- "make it shorter" -> rewrite only
- "emphasize leadership more" -> suggestions + rewrite
- "I also have Kafka experience from my Stripe role" -> gap analysis + suggestions + rewrite
- "the JD also requires Go experience" -> jd analysis + gap analysis + suggestions + rewrite
- "use bullet points instead of paragraphs" -> rewrite only

Alongside the booleans, populate the `response_message` field with a one-sentence
acknowledgement addressed to the user that says what you are about to do.
Keep it short and friendly. Examples:
- "Sure, I'll tighten the rewrite to emphasize leadership."
- "Got it — I'll refresh suggestions and rewrite with a Kafka focus."
- "Will do. I'll redo gap analysis and suggestions with the new JD requirement."

User message: {message}

Previous context: {context}
"""


def classify_followup(message: str, context: str = "") -> ClassifierOutput:
    """Classify a follow-up message to determine which pipeline steps to re-run."""
    llm = get_classifier_model()
    structured_llm = llm.with_structured_output(ClassifierOutput)

    result = structured_llm.invoke(
        CLASSIFIER_PROMPT.format(message=message, context=context)
    )
    return result
