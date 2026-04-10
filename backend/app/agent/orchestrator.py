"""KankerWijzer agent orchestrator using Claude tool_use API with server-side citations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import Settings
from app.lastmeter import DOMAIN_RESOURCES, LASTMETER_DOMAINS, _get_dataset
from app.models import AnswerResponse, Provenance
from app.retrieval.hybrid import HybridMedicalRetriever

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (Dutch) -- medical-grade rules
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
Je bent KankerWijzer, een betrouwbare informatieassistent van IKNL.

REGELS:
1. Gebruik ALLEEN de aangeboden bronnen [SRC-1], [SRC-2], etc.
2. Verwijs naar elke feitelijke bewering met [SRC-N].
3. Verzin NOOIT medische informatie.
4. Geef GEEN persoonlijk medisch advies.
5. Antwoord in dezelfde taal als de vraag.
6. Eindig met: "Let op: deze informatie is informatief en vervangt geen medisch advies."

Bij onvoldoende bewijs: zeg eerlijk dat je het niet kunt vinden.
Verwijs bij persoonlijke vragen naar de huisarts of KWF Kanker Infolijn (0800-022 66 22).

LASTMETER:
Wanneer een gebruiker praat over hoe zij zich voelen, hun last, klachten, zorgen,
vermoeidheid, angst, pijn, somberheid, slaapproblemen, of andere vormen van distress
gerelateerd aan kanker, gebruik dan de lastmeter_assess tool. Dit is de Nederlandse
Lastmeter (Distress Thermometer) — een gevalideerd instrument voor kankerpatiënten.

De Lastmeter werkt als volgt:
1. Vraag de patiënt: "Op een schaal van 0-10, hoeveel last heeft u ervaren in de afgelopen week?" (0=geen last, 10=extreme last)
2. Als de score >= 4: vraag op welke gebieden de patiënt last ervaart (lichamelijk, emotioneel, praktisch, sociaal, zingeving)
3. Gebruik de lastmeter_assess tool met de geselecteerde domeinen om relevante hulpbronnen op te halen
4. Presenteer de resultaten met links naar kanker.nl pagina's die specifiek gaan over die klachten
5. Adviseer altijd om de resultaten te bespreken met hun arts of verpleegkundige

Gebruik de Lastmeter proactief wanneer een patiënt duidelijk last ervaart, maar dwing het niet af bij informationele vragen.

VERDUIDELIJKING BIJ BREDE VRAGEN:
Wanneer een vraag te breed of vaag is om een goed antwoord te geven, gebruik dan de
ask_clarification tool om de gebruiker een vervolgvraag te stellen. Voorbeelden van brede vragen:
- "kanker" (welke kankersoort?)
- "behandeling" (voor welke kankersoort? welk stadium?)
- "statistieken" (welke kankersoort? welk jaar? incidentie of overleving?)
- "bijwerkingen" (van welke behandeling?)

Bij een brede vraag:
1. Geef een KORT algemeen antwoord (2-3 zinnen max)
2. Gebruik ask_clarification om specifieke opties aan te bieden
3. De opties moeten relevant zijn voor de vraag (kankersoorten, behandeltypes, etc.)

Gebruik ask_clarification NIET als de vraag al specifiek genoeg is (bijv. "Wat is borstkanker?" is specifiek).\
"""

# ---------------------------------------------------------------------------
# Tool definitions for Claude tool_use API
# ---------------------------------------------------------------------------
TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_cancer_info",
        "description": (
            "Search the IKNL cancer knowledge base for information about cancer types, "
            "treatment, prevention, screening, etc. Returns evidence blocks with [SRC-N] labels."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in Dutch or English.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_nkr_statistics",
        "description": (
            "Query the NKR (Nederlandse Kankerregistratie) for cancer statistics such as "
            "incidence, stage distribution, survival rates, and trends over time."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Description of the statistics requested.",
                },
                "year": {
                    "type": "integer",
                    "description": "Year for the statistics (default: 2024).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_cancer_atlas",
        "description": (
            "Query the Kanker Atlas for geographic/regional cancer incidence data "
            "by postcode area in the Netherlands."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cancer_group": {
                    "type": "integer",
                    "description": "Cancer group ID (e.g. 11 for lung cancer).",
                },
                "sex": {
                    "type": "integer",
                    "description": "Sex filter: 1=male, 2=female, 3=all.",
                },
                "postcode_digits": {
                    "type": "integer",
                    "description": "Postcode digit level: 3 or 4.",
                },
            },
            "required": ["cancer_group", "sex"],
        },
    },
    {
        "name": "ask_clarification",
        "description": (
            "Stel de gebruiker een verduidelijkende vraag wanneer hun vraag te breed of vaag is. "
            "Gebruik dit bij brede vragen zoals 'kanker', 'behandeling', 'statistieken', 'bijwerkingen' "
            "zonder specificatie van kankersoort, behandeltype of tijdsperiode. "
            "Bied specifieke opties aan zodat de gebruiker kan verfijnen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brief_answer": {
                    "type": "string",
                    "description": (
                        "Een kort algemeen antwoord (2-3 zinnen) op de brede vraag, "
                        "voordat je de vervolgvraag stelt."
                    ),
                },
                "clarification_question": {
                    "type": "string",
                    "description": (
                        "De verduidelijkende vraag aan de gebruiker, bijv. "
                        "'Over welke kankersoort wilt u meer weten?'"
                    ),
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lijst van suggesties/opties voor de gebruiker, bijv. "
                        "['Borstkanker', 'Longkanker', 'Darmkanker', 'Prostaatkanker', 'Huidkanker']"
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": ["cancer_type", "treatment", "statistics", "side_effects", "other"],
                    "description": "Categorie van de verduidelijking.",
                },
            },
            "required": ["clarification_question", "options", "category"],
        },
    },
    {
        "name": "lastmeter_assess",
        "description": (
            "De Lastmeter (Distress Thermometer) — een gevalideerd instrument voor kankerpatiënten. "
            "Gebruik dit wanneer een patiënt praat over hun klachten, last, vermoeidheid, angst, pijn, "
            "somberheid, slaapproblemen, zorgen, of andere vormen van distress. "
            "Geeft relevante hulpbronnen van kanker.nl terug op basis van de geselecteerde probleemgebieden. "
            "Domein-opties: physical:pain, physical:fatigue, physical:sleep, physical:nausea, "
            "physical:appetite, physical:breathing, physical:mobility, physical:appearance, "
            "emotional:anxiety, emotional:depression, emotional:worry, emotional:anger, "
            "emotional:loss_of_interest, practical:work, practical:financial, practical:childcare, "
            "practical:transport, social:partner, social:family, social:friends, social:children, "
            "spiritual:meaning, spiritual:faith, spiritual:death"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "distress_score": {
                    "type": "integer",
                    "description": "De lastmeter-score van de patiënt (0-10). 0=geen last, 10=extreme last.",
                },
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Probleemgebieden die de patiënt ervaart, afgeleid uit hun bericht. "
                        "Bijv. ['physical:pain', 'emotional:anxiety', 'physical:fatigue']."
                    ),
                },
                "patient_message": {
                    "type": "string",
                    "description": "Het originele bericht van de patiënt (voor context).",
                },
            },
            "required": ["domains"],
        },
    },
]

# Regex to find [SRC-N] references in answer text
_SRC_REF_RE = re.compile(r"\[SRC-(\d+)\]")


class AnthropicUnavailableError(RuntimeError):
    pass


class MedicalAnswerOrchestrator:
    """Tool-calling agent orchestrator for KankerWijzer.

    Flow (simplified for hackathon -- single retrieval + single LLM call):
      1. Call HybridMedicalRetriever to get hits (or refusal)
      2. Build evidence blocks with [SRC-N] labels
      3. Call Claude once with evidence + system prompt
      4. Map [SRC-N] references in the answer to Provenance objects
      5. Return AnswerResponse with server-side citations
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.retriever = HybridMedicalRetriever(settings)

    # ------------------------------------------------------------------
    # Anthropic client (lazy)
    # ------------------------------------------------------------------

    def _client(self):
        if not self.settings.anthropic_api_key:
            raise AnthropicUnavailableError("ANTHROPIC_API_KEY is not configured.")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise AnthropicUnavailableError(
                "Anthropic SDK not installed. Run `uv sync --extra anthropic`."
            ) from exc
        return Anthropic(api_key=self.settings.anthropic_api_key)

    # ------------------------------------------------------------------
    # Public API (signature compatible with main.py)
    # ------------------------------------------------------------------

    def answer(
        self, query: str, audience: str = "patient", limit: int = 5
    ) -> AnswerResponse:
        """Answer a user question with server-side provenance citations."""
        notes: list[str] = []

        # ---- Step 1: Retrieve evidence --------------------------------
        retrieval = self.retriever.retrieve(query=query, audience=audience, limit=limit)

        if retrieval.refusal_reason:
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason=retrieval.refusal_reason,
                notes=retrieval.notes,
            )

        # ---- Step 2: Build [SRC-N] evidence blocks --------------------
        all_provenances: list[Provenance] = []
        hit_scores: list[float] = []
        evidence_lines: list[str] = []

        for idx, hit in enumerate(retrieval.hits, start=1):
            prov = hit.document.provenance
            prov.relevance_score = round(hit.score, 3)
            all_provenances.append(prov)
            hit_scores.append(hit.score)
            evidence_lines.append(
                f"[SRC-{idx}] {hit.document.title}\n"
                f"Bron: {prov.publisher or prov.source_id}\n"
                f"Relevantie: {hit.score:.0%}\n"
                f"Fragment: {hit.excerpt}\n"
            )

        notes.extend(retrieval.notes)

        if not evidence_lines:
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason="Geen relevante bronnen gevonden.",
                notes=notes,
            )

        # ---- Step 3: Call Claude with evidence + tools ----------------
        try:
            client = self._client()
        except AnthropicUnavailableError as exc:
            notes.append(str(exc))
            return AnswerResponse(
                query=query,
                audience=audience,
                answer_markdown=None,
                citations=all_provenances,
                notes=notes,
            )

        user_message = (
            f"Doelgroep: {audience}\n"
            f"Vraag: {query}\n\n"
            f"Beschikbaar bewijs:\n"
            + "\n".join(evidence_lines)
        )

        try:
            response = client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=1500,
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as exc:
            logger.exception("Claude API call failed")
            notes.append(f"Claude API error: {exc}")
            return AnswerResponse(
                query=query,
                audience=audience,
                answer_markdown=None,
                citations=all_provenances,
                notes=notes,
            )

        # ---- Step 4: Handle tool_use blocks (if Claude wants to call tools)
        answer_text = self._process_response(
            client, response, query, audience, evidence_lines, notes
        )

        # ---- Step 5: Map [SRC-N] references to provenances -----------
        cited_provenances = self._extract_cited_provenances(
            answer_text, all_provenances
        )

        # ---- Step 6: Compute overall answer confidence ---------------
        confidence, confidence_label = self._compute_confidence(
            hit_scores, cited_provenances or all_provenances
        )

        return AnswerResponse(
            query=query,
            audience=audience,
            answer_markdown=answer_text,
            citations=cited_provenances if cited_provenances else all_provenances,
            confidence=confidence,
            confidence_label=confidence_label,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Response processing (handles text + tool_use blocks)
    # ------------------------------------------------------------------

    def _process_response(
        self,
        client,
        response,
        query: str,
        audience: str,
        evidence_lines: list[str],
        notes: list[str],
    ) -> str | None:
        """Extract answer text, handling tool_use if Claude requests it."""

        text_parts: list[str] = []
        tool_results: list[dict[str, Any]] = []

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
            elif getattr(block, "type", None) == "tool_use":
                # Execute the tool call server-side
                tool_result = self._execute_tool(block.name, block.input, notes)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        # If there were tool calls, do one follow-up call with results
        if tool_results and response.stop_reason == "tool_use":
            try:
                messages = [
                    {"role": "user", "content": (
                        f"Doelgroep: {audience}\n"
                        f"Vraag: {query}\n\n"
                        f"Beschikbaar bewijs:\n"
                        + "\n".join(evidence_lines)
                    )},
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results},
                ]

                follow_up = client.messages.create(
                    model=self.settings.anthropic_model,
                    max_tokens=1500,
                    temperature=0,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )

                for block in follow_up.content:
                    if getattr(block, "type", None) == "text":
                        text_parts.append(block.text)

                notes.append("Tool-use round completed.")
            except Exception as exc:
                logger.exception("Follow-up Claude call failed")
                notes.append(f"Tool follow-up error: {exc}")

        return "\n".join(text_parts).strip() if text_parts else None

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool(
        self, tool_name: str, tool_input: dict[str, Any], notes: list[str]
    ) -> dict[str, Any]:
        """Execute a tool call and return the result."""
        try:
            if tool_name == "search_cancer_info":
                return self._tool_search_cancer_info(tool_input)
            elif tool_name == "query_nkr_statistics":
                return self._tool_query_nkr_statistics(tool_input)
            elif tool_name == "query_cancer_atlas":
                return self._tool_query_cancer_atlas(tool_input)
            elif tool_name == "lastmeter_assess":
                return self._tool_lastmeter_assess(tool_input)
            elif tool_name == "ask_clarification":
                return self._tool_ask_clarification(tool_input)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as exc:
            logger.exception("Tool execution failed: %s", tool_name)
            notes.append(f"Tool '{tool_name}' error: {exc}")
            return {"error": str(exc)}

    def _tool_search_cancer_info(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute search_cancer_info tool via HybridMedicalRetriever."""
        q = input_data.get("query", "")
        result = self.retriever.retrieve(query=q, audience="patient", limit=5)
        if result.refusal_reason:
            return {"refusal": result.refusal_reason}
        hits = []
        for idx, hit in enumerate(result.hits, start=1):
            hits.append({
                "label": f"[SRC-{idx}]",
                "title": hit.document.title,
                "excerpt": hit.excerpt[:500],
            })
        return {"hits": hits, "count": len(hits)}

    def _tool_query_nkr_statistics(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute query_nkr_statistics tool via NKR API."""
        year = input_data.get("year", 2024)
        try:
            data = self.retriever.nkr.example_stage_distribution(year=year)
            return {"data": str(data)[:3000], "source": "NKR Cijfers IKNL"}
        except Exception as exc:
            return {"error": f"NKR API unavailable: {exc}"}

    def _tool_query_cancer_atlas(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute query_cancer_atlas tool via Cancer Atlas API."""
        cancer_group = input_data.get("cancer_group", 11)
        sex = input_data.get("sex", 3)
        postcode_digits = input_data.get("postcode_digits", 3)
        try:
            data = self.retriever.kankeratlas.cancer_data(
                cancer_group=cancer_group, sex=sex, postcode_digits=postcode_digits
            )
            rows = data.get("res", [])[:10]
            return {"rows": rows, "source": "Kanker Atlas IKNL"}
        except Exception as exc:
            return {"error": f"Cancer Atlas API unavailable: {exc}"}

    def _tool_ask_clarification(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Return clarification data — the agent will format this into its response."""
        return {
            "type": "clarification",
            "brief_answer": input_data.get("brief_answer", ""),
            "question": input_data.get("clarification_question", ""),
            "options": input_data.get("options", []),
            "category": input_data.get("category", "other"),
        }

    def _tool_lastmeter_assess(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute lastmeter_assess tool — find resources for patient distress domains."""
        domains = input_data.get("domains", [])
        distress_score = input_data.get("distress_score")
        patient_message = input_data.get("patient_message", "")

        dataset = _get_dataset()
        resources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for domain_key in domains:
            search_queries = DOMAIN_RESOURCES.get(domain_key, [])
            for sq in search_queries:
                try:
                    hits = dataset.search(sq, limit=3)
                except Exception:
                    continue
                for hit in hits:
                    url = hit.document.url
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    resources.append({
                        "domain": domain_key,
                        "title": hit.document.title,
                        "url": url,
                        "excerpt": hit.excerpt[:200] if hit.excerpt else "",
                    })

        # Build the domain labels for the response
        domain_labels = {}
        for d in LASTMETER_DOMAINS:
            for item in d["items"]:
                key = f"{d['id']}:{item['id']}"
                domain_labels[key] = f"{d['name']} — {item['label']}"

        matched_labels = [domain_labels.get(d, d) for d in domains]

        return {
            "distress_score": distress_score,
            "identified_domains": matched_labels,
            "resources": resources[:15],  # cap at 15 links
            "resource_count": len(resources),
            "source": "kanker.nl (Lastmeter hulpbronnen)",
            "note": (
                "De Lastmeter is een gevalideerd instrument. "
                "Adviseer de patiënt om deze resultaten te bespreken met hun arts of verpleegkundige."
            ),
        }

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        hit_scores: list[float],
        cited_provenances: list[Provenance],
    ) -> tuple[float, str]:
        """Compute overall answer confidence from retrieval scores.

        Factors:
        - Top retrieval score (how well the best source matches)
        - Average of top-3 scores (consistency of evidence)
        - Source diversity (multiple distinct sources = higher confidence)
        - Number of citations (more evidence = more confident)

        Returns (confidence_float, label_string).
        """
        if not hit_scores:
            return 0.0, "geen"

        top_score = max(hit_scores)
        top3 = sorted(hit_scores, reverse=True)[:3]
        avg_top3 = sum(top3) / len(top3)

        # Source diversity bonus: unique source families cited
        unique_sources = set()
        for p in cited_provenances:
            if p.relevance_score and p.relevance_score > 0.3:
                unique_sources.add(p.source_id)
        diversity_bonus = min(len(unique_sources) * 0.05, 0.15)

        # Citation count factor
        n_cited = len(cited_provenances)
        citation_factor = min(n_cited / 5.0, 1.0)  # caps at 5 citations

        # Weighted combination
        confidence = (
            top_score * 0.40
            + avg_top3 * 0.30
            + citation_factor * 0.15
            + diversity_bonus
        )
        confidence = round(min(confidence, 1.0), 2)

        # Label
        if confidence >= 0.75:
            label = "hoog"
        elif confidence >= 0.55:
            label = "gemiddeld"
        elif confidence >= 0.35:
            label = "laag"
        else:
            label = "zeer laag"

        return confidence, label

    # ------------------------------------------------------------------
    # Citation mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_cited_provenances(
        answer_text: str | None,
        all_provenances: list[Provenance],
    ) -> list[Provenance]:
        """Extract only the Provenance objects referenced by [SRC-N] in the answer."""
        if not answer_text:
            return []

        cited_indices: set[int] = set()
        for match in _SRC_REF_RE.finditer(answer_text):
            idx = int(match.group(1))
            cited_indices.add(idx)

        cited: list[Provenance] = []
        for idx in sorted(cited_indices):
            if 1 <= idx <= len(all_provenances):
                cited.append(all_provenances[idx - 1])

        return cited
