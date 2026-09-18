import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from app.rag import retrieve_context, retrieve_context_by_category

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

CATEGORIES = ["soil", "climate", "biodiversity", "land_use", "human_impact"]


def get_environmental_followup(user_message: str) -> str:
    system_prompt = (
        "You are an environmental advisory assistant.\n"
        "The user has reported an environmental problem but has not "
        "provided enough information for a recommendation.\n"
        "Do NOT explain the problem and do NOT give a recommendation yet.\n"
        "Ask for these three details:\n"
        "1. Soil organic carbon %\n"
        "2. Rainfall pattern\n"
        "3. Land use type\n"
        "Keep the response to one short sentence."
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        max_tokens=100,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()

def get_ai_reply(user_message: str) -> str:
    context = retrieve_context(user_message)

    system_prompt = (
        "You are StudyMate, a study tutor who explains concepts FAST and SIMPLE.\n"
        "STRICT RULES:\n"
        "- Maximum 4-5 sentences OR 3-4 short bullet points. Never more.\n"
        "- No headers, no markdown titles, no multi-section breakdowns unless the user explicitly asks for 'detailed' or 'full explanation'.\n"
        "- Explain like you're texting a friend before an exam — quick and clear, not a textbook chapter.\n"
        "- Use your own words. Never copy sentences from the notes.\n"
        "- If no relevant notes are found, say \"Not in your notes, but here's a quick explanation:\" then answer briefly.\n"
        "- Never refuse to answer."
    )

    user_prompt = (
        f"NOTES CONTEXT:\n{context}\n\nQUESTION: {user_message}"
        if context else
        f"QUESTION: {user_message}"
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=220,       # hard cap — forces brevity
        temperature=0.4
    )
    return response.choices[0].message.content


def get_answer(question):
    context = retrieve_context(question)

    system_prompt = """You are a study tutor.
- If context is provided, explain it in your own words, briefly and clearly — never copy text verbatim.
- If no context is given or it's unrelated, say "This isn't in your notes, but here's a general explanation:" then answer from your own knowledge.
- Never refuse to answer."""

    user_prompt = f"Context:\n{context}\n\nQuestion: {question}" if context else f"Question: {question}"

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=220,
        temperature=0.4
    )
    return response.choices[0].message.content




class Recommendation(BaseModel):
    recommendation: str
    reasoning: str
    metrics_impacted: list[str]
    time_horizon: str
    confidence: str
    sources: list[str]


def retrieve_multi_category_context(query: str, n_results: int = 1, max_chars: int = 350):
    blocks = []
    categories_hit = 0
    sources = []

    for category in CATEGORIES:
        docs, metas = retrieve_context_by_category(query, category, n_results)

        if not docs:
            continue

        categories_hit += 1

        for doc, meta in zip(docs, metas):
            truncated = doc[:max_chars] + ("..." if len(doc) > max_chars else "")

            blocks.append(
                f"[source: {meta['source']} | category: {meta['category']}] {truncated}"
            )

            if meta["source"] not in sources:
                sources.append(meta["source"])

    return "\n\n".join(blocks), categories_hit, sources

    """Pull top matches per category so the model can connect >=3 variables
    instead of answering off a single undifferentiated retrieval.
    n_results=1 and max_chars truncation keep total tokens under Groq's
    free-tier 8000 TPM limit — 5 categories x 1 chunk x ~500 chars fits
    comfortably; raise these later if you're on a paid tier."""
    blocks = []
    categories_hit = 0

    for category in CATEGORIES:
        docs, metas = retrieve_context_by_category(query, category, n_results)
        if not docs:
            continue
        categories_hit += 1
        for doc, meta in zip(docs, metas):
            truncated = doc[:max_chars] + ("..." if len(doc) > max_chars else "")
            blocks.append(
           f"[source: {meta['source']} | category: {meta['category']}] {truncated}"
           )

    return "\n\n".join(blocks), categories_hit


def get_environmental_recommendation(user_input: dict) -> Recommendation:
    """
    user_input example:
    {"soil_organic_carbon": "0.3%", "rainfall": "low",
     "crop": "monoculture wheat", "region": "semi-arid"}
    """
    query = ", ".join(f"{k}: {v}" for k, v in user_input.items())
    context, categories_hit, sources = retrieve_multi_category_context(query)

    if categories_hit < 3:
        return Recommendation(
            recommendation="More information needed before a confident recommendation.",
            reasoning=(
                f"Only {categories_hit} relevant categories were retrieved for this "
                "input — not enough to responsibly connect 3+ variables."
            ),
            metrics_impacted=[],
            time_horizon="n/a",
            confidence="low",
            sources=[],
        )

    system_prompt = (
    "You are an evidence-based environmental and biodiversity advisory assistant.\n"
    "Your task is to reason across multiple environmental variables and provide "
    "one practical recommendation supported by the retrieved scientific evidence.\n\n"

    "STRICT RULES:\n"
    "- Use only the RETRIEVED_CONTEXT as scientific evidence.\n"
    "- Connect at least 3 environmental variables in the reasoning.\n"
    "- Address the user's soil, rainfall/climate, and land-use conditions.\n"
    "- Explain the connection between soil, water/climate, land use, and biodiversity "
    "where supported by the evidence.\n"
    "- Recommend a practical and specific intervention, not a generic statement "
    "such as 'use sustainable practices'.\n"
    "- Do not invent numerical improvements, percentages, timeframes, or scientific "
    "claims that are not supported by the retrieved evidence.\n"
    "- If the evidence contains a quantitative estimate, include it only when it "
    "is relevant to the user's conditions.\n"
    "- If quantitative evidence is unavailable, explicitly say that a reliable "
    "numerical estimate is not available from the retrieved evidence.\n"
    "- Use cautious scientific wording such as 'may improve', 'is associated with', "
    "or 'can support' when appropriate.\n"
    "- metrics_impacted must contain only metrics supported by the retrieved evidence.\n"
    "- Keep recommendation under 60 words.\n"
    "- Keep reasoning under 90 words.\n"
    "- Keep metrics_impacted to 2-4 items.\n"
    "- Keep time_horizon concise.\n"
    "- Do not generate source names, author names, citations, or references.\n"
    "- The application will attach the actual retrieved PDF sources automatically.\n"
    "- Return an empty list for sources.\n"
    "- Do not invent specific crop varieties, species, practices, percentages, or numerical estimates.\n"
    "- Only recommend a specific practice if the retrieved context supports it.\n"
    "- Do not assume that a practice improves a metric unless the retrieved evidence supports that connection.\n"
    "- Do not generate unsupported claims about greenhouse gas reduction, water retention, carbon sequestration, or biodiversity improvement.\n"
    "- If evidence is insufficient for a specific claim, use cautious wording such as 'may help' or leave the claim out.\n"
    "- sources must contain only the actual source IDs represented in the retrieved context.\n"
    "- Respond ONLY with valid JSON.\n\n"

    "JSON FORMAT:\n"
    '{"recommendation": "...", '
    '"reasoning": "...", '
    '"metrics_impacted": ["...", "..."], '
    '"time_horizon": "...", '
    '"confidence": "low|medium|high", '
    '"sources": ["..."]}'
   )

    user_prompt = (
    f"RETRIEVED_CONTEXT:\n{context}\n\n"
    f"USER CONDITIONS:\n{query}\n\n"
    "Analyze the retrieved evidence across the user's environmental "
    "conditions and provide the most practical evidence-supported "
    "biodiversity recommendation."
   )

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=2500,
        temperature=0.3,
    )

    raw = response.choices[0].message.content

    if not raw:
     raise ValueError(
        "Groq returned an empty response. "
        f"Finish reason: {response.choices[0].finish_reason}"
    )

    raw = raw.strip()

    try:
        data = json.loads(raw)
        data["sources"] = sources
        return Recommendation(**data)
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Model did not return valid structured output: {e}\nRaw: {raw}")