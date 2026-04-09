import asyncio

from langchain_core.messages import SystemMessage, HumanMessage

from src.models.provider import get_chat_model
from src.models.schemas import JdAnalysis, GapAnalysis, Suggestions, RewriteResult
from src.memory.rag import query_resume_corpus
from src.memory.preferences import load_all_preferences


def build_system_prompt(preferences: list[str], conversation_summary: str | None) -> str:
    """Build the system prompt with preferences and conversation context."""
    parts = [
        "You are an expert resume tailoring assistant. Your job is to help "
        "tailor resumes to specific job descriptions by analyzing gaps and "
        "suggesting improvements grounded in the user's real experience."
    ]

    if preferences:
        parts.append("\nUser preferences (apply these to all outputs):")
        for pref in preferences:
            parts.append(f"- {pref}")

    if conversation_summary:
        parts.append(f"\nPrevious conversation context:\n{conversation_summary}")

    return "\n".join(parts)


async def step_jd_analysis(state: dict) -> dict:
    """Analyze the job description and extract structured requirements."""
    llm = await asyncio.to_thread(get_chat_model)
    structured_llm = llm.with_structured_output(JdAnalysis, method="function_calling")

    prompt = (
        f"Analyze this job description and extract the key requirements, "
        f"qualifications, technologies, and soft skills.\n\n"
        f"Job Description:\n{state['jd_text']}"
    )

    preferences = await load_all_preferences()
    system = build_system_prompt(preferences, state.get("conversation_summary"))

    result = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    return {**state, "jd_analysis": result.model_dump_json(), "preferences": preferences}


async def step_rag_retrieval(state: dict) -> dict:
    """Retrieve relevant experience from the resume corpus using RAG."""
    jd_analysis = JdAnalysis.model_validate_json(state["jd_analysis"])

    all_chunks = []
    for req in jd_analysis.key_requirements[:5]:
        chunks = await query_resume_corpus(req, n_results=3)
        all_chunks.extend(chunks)

    for tech in jd_analysis.technologies[:5]:
        chunks = await query_resume_corpus(tech, n_results=2)
        all_chunks.extend(chunks)

    seen = set()
    unique_chunks = []
    for chunk in all_chunks:
        if chunk["text"] not in seen:
            seen.add(chunk["text"])
            unique_chunks.append(chunk)

    rag_context = []
    for chunk in unique_chunks[:10]:
        source = f"[{chunk['resume_name']} - {chunk['section_type']}]"
        rag_context.append(f"{source} {chunk['text']}")

    return {**state, "rag_chunks": rag_context}


async def step_gap_analysis(state: dict) -> dict:
    """Compare JD requirements against the resume and RAG-retrieved experience."""
    llm = await asyncio.to_thread(get_chat_model)
    structured_llm = llm.with_structured_output(GapAnalysis, method="function_calling")

    rag_section = ""
    if state.get("rag_chunks"):
        rag_section = (
            "\n\nRelevant experience from other resume versions:\n"
            + "\n".join(state["rag_chunks"])
        )

    prompt = (
        f"Compare the job requirements against this resume and identify matches, "
        f"partial matches, and gaps. For gaps, check if the RAG-retrieved experience "
        f"from other resume versions could fill them.\n\n"
        f"JD Analysis:\n{state['jd_analysis']}\n\n"
        f"Resume:\n{state['resume_text']}"
        f"{rag_section}"
    )

    if state.get("preferences") is not None:
        preferences = state["preferences"]
    else:
        preferences = await load_all_preferences()
    system = build_system_prompt(preferences, state.get("conversation_summary"))

    result = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    return {**state, "gap_analysis": result.model_dump_json()}


async def step_suggestions(state: dict) -> dict:
    """Generate section-by-section rewrite suggestions."""
    llm = await asyncio.to_thread(get_chat_model)
    structured_llm = llm.with_structured_output(Suggestions, method="function_calling")

    recent_messages = state.get("recent_messages", [])
    chat_context = ""
    if recent_messages:
        chat_context = "\n\nRecent conversation:\n"
        for msg in recent_messages:
            chat_context += f"{msg['role']}: {msg['content']}\n"

    prompt = (
        f"Based on the gap analysis, generate specific section-by-section suggestions "
        f"for improving this resume. Include what to change and why.\n\n"
        f"Gap Analysis:\n{state['gap_analysis']}\n\n"
        f"Current Resume:\n{state['resume_text']}"
        f"{chat_context}"
    )

    if state.get("preferences") is not None:
        preferences = state["preferences"]
    else:
        preferences = await load_all_preferences()
    system = build_system_prompt(preferences, state.get("conversation_summary"))

    result = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    return {**state, "suggestions": result.model_dump_json()}


async def step_rewrite(state: dict) -> dict:
    """Generate the full rewritten resume."""
    llm = await asyncio.to_thread(get_chat_model)
    structured_llm = llm.with_structured_output(RewriteResult, method="function_calling")

    recent_messages = state.get("recent_messages", [])
    chat_context = ""
    if recent_messages:
        chat_context = "\n\nRecent conversation (apply any requested changes):\n"
        for msg in recent_messages:
            chat_context += f"{msg['role']}: {msg['content']}\n"

    prompt = (
        f"Rewrite the resume incorporating all suggestions. Output the complete "
        f"rewritten resume and a summary of changes made.\n\n"
        f"Suggestions:\n{state['suggestions']}\n\n"
        f"Current Resume:\n{state['resume_text']}"
        f"{chat_context}"
    )

    if state.get("preferences") is not None:
        preferences = state["preferences"]
    else:
        preferences = await load_all_preferences()
    system = build_system_prompt(preferences, state.get("conversation_summary"))

    result = await structured_llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])

    return {**state, "rewrite": result.model_dump_json()}
