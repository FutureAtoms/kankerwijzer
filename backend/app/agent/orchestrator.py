"""OncologieWijzer agent orchestrator using Claude tool_use API with server-side citations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import Settings
from app.lastmeter import DOMAIN_RESOURCES, LASTMETER_DOMAINS, _get_dataset
from app.models import AnswerResponse, ClarificationData, ContactInfo, Provenance
from app.retrieval.hybrid import HybridMedicalRetriever
from app.safety.red_flags import check_red_flags, get_routing_info

# GraphRAG — optional, degrades gracefully if Neo4j is unavailable
try:
    from app.graphrag.retriever import GraphRetriever as _GraphRetriever
except ImportError:
    _GraphRetriever = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (Dutch) -- medical-grade rules
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
Je bent OncologieWijzer, een betrouwbare informatieassistent van IKNL.

REGELS:
1. Gebruik ALLEEN de aangeboden bronnen [SRC-1], [SRC-2], etc.
2. Verwijs naar elke feitelijke bewering met [SRC-N].
3. Verzin NOOIT medische informatie.
4. Geef GEEN persoonlijk medisch advies.
5. Antwoord in dezelfde taal als de vraag.
6. Eindig met: "Let op: deze informatie is informatief en vervangt geen medisch advies."

Bij onvoldoende bewijs: zeg eerlijk dat je het niet kunt vinden.
Verwijs bij persoonlijke vragen naar de huisarts of KWF Kanker Infolijn (0800-022 66 22).

STATISTIEKEN — PROGRESSIEVE VERDUIDELIJKING (VERPLICHT):
Voor ELKE statistiekvraag MOET je ALLE drie filters kennen voordat je query_nkr_statistics aanroept:
1. Kankersoort (welke kanker precies?)
2. Type statistiek (incidentie / stadiumverdeling / prevalentie / sterfte / overleving)
3. Jaar (welk diagnosejaar?)

WERKWIJZE BIJ STATISTIEKVRAGEN:
- Als de gebruiker ALLE drie filters noemt → roep query_nkr_statistics DIRECT aan
  Voorbeeld: "Hoeveel prostaatkanker diagnoses in 2022?" → cancer_type=prostaatkanker, stat_type=incidentie, year=2022

- Als ÉÉN of MEER filters ontbreken → gebruik ask_clarification om de ontbrekende te vragen
  Geef ALTIJD klikbare opties zodat de gebruiker niet hoeft te typen.

  STAP-VOOR-STAP VOORBEELD:
  Vraag: "statistieken over kanker"
  → Stap 1: ask_clarification — "Over welke kankersoort wilt u statistieken zien?"
    opties: ["Borstkanker", "Longkanker", "Darmkanker", "Prostaatkanker", "Melanoom", "Blaaskanker", "Alle kankersoorten"]
  → Gebruiker klikt "Prostaatkanker"
  → Stap 2: ask_clarification — "Welk type statistiek wilt u over prostaatkanker?"
    opties: ["Incidentie (nieuwe diagnoses)", "Stadiumverdeling", "Overleving (5-jaars)", "Prevalentie", "Sterfte"]
  → Gebruiker klikt "Incidentie"
  → Stap 3: ask_clarification — "Over welk jaar wilt u de incidentiecijfers van prostaatkanker?"
    opties: ["2024", "2023", "2022", "2021", "2020"]
  → Gebruiker klikt "2023"
  → Nu heb je ALLES → roep query_nkr_statistics aan met cancer_type=prostaatkanker, stat_type=incidentie, year=2023

  SLIM COMBINEREN: Als de gebruiker in één vraag twee van de drie noemt, vraag alleen het ontbrekende.
  Voorbeeld: "Overleving bij longkanker" → je weet kankersoort + stat_type, vraag alleen het jaar.

EXTRA FILTERS (optioneel, niet verplicht vragen):
- Geslacht: als de gebruiker "bij mannen" of "bij vrouwen" zegt, vul sex in. Anders sex="alle".

BELANGRIJK: Roep query_nkr_statistics NOOIT aan zonder specifieke kankersoort tenzij de gebruiker
expliciet "alle kankersoorten" zegt. "Kanker" alleen is niet specifiek genoeg.

LASTMETER (PRIORITEIT — ALTIJD CONTROLEREN):
De Lastmeter (Distress Thermometer) is een gevalideerd instrument voor kankerpatiënten.
Je MOET de lastmeter_assess tool gebruiken wanneer je OOK MAAR EEN HINT van distress detecteert.

TRIGGER-SIGNALEN — gebruik lastmeter_assess bij ELK van deze signalen:
- Emotioneel: angst, bang, bezorgd, zorgen, stress, somber, depressief, verdrietig,
  boos, gefrustreerd, eenzaam, machteloos, hopeloos, onzeker, ongerust, paniek,
  huilen, emotioneel, overweldigd, niet meer weten, het niet meer zien zitten
- Lichamelijk: pijn, moe, vermoeid, uitgeput, misselijk, slapeloosheid, slaapproblemen,
  niet kunnen slapen, geen eetlust, gewichtsverlies, gewichtstoename, kortademig,
  duizelig, zwak, tintelingen, jeuk, haaruitval, bijwerkingen, klachten, last,
  niet lekker voelen, ziek voelen
- Praktisch: werk, financieel, geld, verzekering, kinderopvang, vervoer, administratie,
  regelen, mantelzorg
- Sociaal: relatie, partner, gezin, familie, vrienden, isolatie, alleen, eenzaam,
  seksualiteit, intimiteit
- Zingeving: waarom, zinloos, geloof, dood, angst voor de dood, afscheid,
  levensvragen, spiritueel, betekenis
- Algemeen: hoe gaat het, hoe voel je je, het gaat niet goed, ik heb het moeilijk,
  het valt me zwaar, ik kan het niet aan, het is te veel, alles is anders

WERKWIJZE:
1. Detecteer de relevante domeinen uit het bericht van de patiënt
2. Schat een distress_score in op basis van de toon en ernst (0-10)
3. Roep DIRECT lastmeter_assess aan met de gedetecteerde domeinen — je hoeft NIET
   eerst te vragen of de patiënt de Lastmeter wil invullen
4. Combineer de gevonden hulpbronnen met een empathisch antwoord
5. Adviseer altijd om de resultaten te bespreken met hun arts of verpleegkundige

BIJ TWIJFEL: gebruik de Lastmeter. Het is beter om relevante hulpbronnen aan te bieden
dan om een patiënt in nood te missen. De enige uitzondering is een puur informatieve vraag
zonder enige persoonlijke context (bijv. "wat is chemotherapie?").

VERDUIDELIJKING — GEBRUIK ask_clarification IN DEZE GEVALLEN:

A) BREDE OF VAGE VRAGEN:
Wanneer een vraag te breed is, zoals "kanker", "behandeling", "statistieken", "bijwerkingen"
zonder specificatie. Bied dan opties aan (kankersoorten, behandeltypes, etc.).

B) BRONNEN BEANTWOORDEN DE VRAAG NIET GOED (KRITIEK):
Controleer ALTIJD of de gevonden bronnen de vraag echt beantwoorden. Voorbeelden van slechte matches:
- Vraag over "vermoeidheid tijdens chemotherapie" → bronnen over vermoeidheid bij vaginakanker/schaamlipkanker
  (FOUT: de bronnen gaan over een specifieke kankersoort, niet over chemotherapie-vermoeidheid in het algemeen)
- Vraag over "bijwerkingen immunotherapie" → bronnen over bijwerkingen chemotherapie
  (FOUT: verkeerde behandeling)
- Vraag over "overleving bij longkanker" → bronnen over borstkanker overleving
  (FOUT: verkeerde kankersoort)

Als de bronnen NIET direct matchen met de vraag:
1. GEBRUIK de bronnen NIET alsof ze het antwoord zijn — citeer ze NIET
2. Probeer NIET herhaaldelijk te zoeken met dezelfde of vergelijkbare termen — dat geeft dezelfde resultaten
3. Gebruik DIRECT ask_clarification met:
   - brief_answer: "Ik heb geen specifieke informatie gevonden over [onderwerp]. De beschikbare informatie is per kankersoort georganiseerd."
   - clarification_question: een gerichte vervolgvraag
   - options: relevante keuzes die helpen om betere informatie te vinden
   Voorbeeld voor "vermoeidheid tijdens chemotherapie":
   - brief_answer: "Vermoeidheid is een veelvoorkomende bijwerking van chemotherapie. Onze informatie over vermoeidheid is per kankersoort beschikbaar."
   - question: "Voor welke kankersoort zoekt u informatie over vermoeidheid?"
   - options: ["Borstkanker", "Longkanker", "Darmkanker", "Prostaatkanker", "Leukemie", "Andere kankersoort"]
4. Doe MAXIMAAL 1 herzoekpoging. Als die ook niet matcht → ask_clarification

C) WANNEER DE VRAAG PERSOONLIJK KLINKT MAAR INFORMATIEF IS:
Vragen als "Hoe kan ik omgaan met..." zijn informatief (niet persoonlijk advies).
Beantwoord deze met praktische tips UIT DE BRONNEN, maar vraag welke kankersoort als de bronnen te generiek zijn.

GEBRUIK ask_clarification NIET als de vraag specifiek is EN de bronnen goed matchen.

AANVULLENDE STRIKTE REGELS:

VERBODEN GEDRAG:
- Vat NOOIT broninhoud samen of parafraseer het in eigen woorden.
- Geef NOOIT persoonlijke risico-inschattingen of statistische interpretaties.
- Ga NOOIT door na een weigering. Na een weigering: STOP. Geen "maar u kunt wel...", geen tips, geen suggesties.
- Leg NOOIT medische termen uit in eigen woorden. Verwijs naar de bron die het uitlegt.

ANTWOORDFORMAAT:
- Verwijs ALTIJD naar de exacte bronpagina met [SRC-N] en URL.
- Gebruik het fragment uit de bron. Schrijf het NIET in eigen woorden om.
- Bij professionele statistiekvragen: toon ALLEEN de exacte cijfers uit de bron, geen duiding.

BIJ VAGE VRAGEN:
- Gebruik ALLEEN ask_clarification. Geef GEEN "kort antwoord" of algemene informatie eerst.\
"""

# ---------------------------------------------------------------------------
# Prompt pre-classification — detect banned prompt categories
# ---------------------------------------------------------------------------

_SUMMARIZATION_RE = re.compile(
    r"samenvatten|samenvatting|samenvat|belangrijkste\s+inzichten|geef\s+een\s+overzicht",
    re.IGNORECASE,
)
_SYNTHESIS_RE = re.compile(
    r"combiner|combineer|beste\s+behandeling|combine.*information|informatie\s+combineren",
    re.IGNORECASE,
)
_PERSONAL_INTERPRETATION_RE = re.compile(
    r"voor\s+mij\b|mijn\s+kans|mijn\s+risico|wat\s+betekent.*voor\s+mij|mijn\s+overlevingskans|mijn\s+prognose",
    re.IGNORECASE,
)
_PERSONAL_ADVICE_RE = re.compile(
    r"als\s+jij\s+mij\s+was|zou\s+je.*dan|wat\s+raad\s+je.*aan|would\s+you\s+recommend|what\s+would\s+you",
    re.IGNORECASE,
)
_IMPOSSIBLE_PREMISE_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"vrouwen.*prostaatkanker", re.IGNORECASE),
        "prostaatkanker",
        "Prostaatkanker komt uitsluitend voor bij personen met een prostaat.",
    ),
    (
        re.compile(r"mannen.*baarmoeder(hals)?kanker", re.IGNORECASE),
        "baarmoederkanker",
        "Baarmoeder(hals)kanker komt uitsluitend voor bij personen met een baarmoeder.",
    ),
    (
        re.compile(r"mannen.*eierstokkanker", re.IGNORECASE),
        "eierstokkanker",
        "Eierstokkanker komt uitsluitend voor bij personen met eierstokken.",
    ),
]
_NO_SOURCE_EXPLICIT_RE = re.compile(
    r"niet\s+in\s+je\s+bronnen|not\s+in\s+your\s+sources|als\s+het\s+niet\s+in.*bronnen|buiten.*bronnen",
    re.IGNORECASE,
)
_NUMERIC_SIGNAL_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*[%]|(?:\s*jaar)|(?:\s*gevallen))?\b")


def classify_prompt(query: str) -> tuple[str | None, str | None]:
    """Detect banned prompt categories and return a hard-coded response.

    Returns (category, hard_response) or (None, None) when no ban applies.
    """
    q = query.strip()

    # 1. Impossible biological premise
    for pattern, cancer_type, correction in _IMPOSSIBLE_PREMISE_PATTERNS:
        if pattern.search(q):
            return (
                "impossible_premise",
                f"Uw vraag bevat een onjuiste medische aanname. {correction}",
            )

    # 2. Personal advice requests
    if _PERSONAL_ADVICE_RE.search(q):
        return (
            "personal_advice",
            "Ik kan geen persoonlijk advies geven. Behandelbeslissingen zijn persoonlijk "
            "— bespreek dit met uw behandelteam of huisarts.\n\n"
            "Let op: deze informatie is informatief en vervangt geen medisch advies.",
        )

    # 3. Personal interpretation of statistics/risk
    if _PERSONAL_INTERPRETATION_RE.search(q):
        return (
            "personal_interpretation",
            "Ik kan geen persoonlijke interpretatie geven van medische gegevens. "
            "Bespreek dit met uw arts of verpleegkundige.\n\n"
            "Let op: deze informatie is informatief en vervangt geen medisch advies.",
        )

    # 4. Summarization requests
    if _SUMMARIZATION_RE.search(q):
        return (
            "summarization",
            "Ik mag geen samenvattingen maken van bronmateriaal. "
            "Hieronder vindt u de directe bronnen over dit onderwerp:",
        )

    # 5. Synthesis / best-treatment requests
    if _SYNTHESIS_RE.search(q):
        return (
            "synthesis",
            "Ik mag geen bronnen combineren of behandeladvies geven. "
            "Bespreek behandelopties met uw behandelteam.\n\n"
            "Let op: deze informatie is informatief en vervangt geen medisch advies.",
        )

    # 6. Explicit "not in your sources" framing
    if _NO_SOURCE_EXPLICIT_RE.search(q):
        return (
            "no_source_explicit",
            "Geen exacte match gevonden in de goedgekeurde bronnen.\n\n"
            "Let op: deze informatie is informatief en vervangt geen medisch advies.",
        )

    return (None, None)


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
            "Query the NKR (Nederlandse Kankerregistratie) for cancer statistics. "
            "BELANGRIJK: Gebruik ALLEEN als je ALLE vereiste filters kent: cancer_type, year, en stat_type. "
            "Als een van deze ontbreekt in de vraag, gebruik dan EERST ask_clarification om te vragen."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cancer_type": {
                    "type": "string",
                    "description": (
                        "Kankersoort. Beschikbare waarden: alle, borstkanker, longkanker, "
                        "darmkanker, dikkedarmkanker, endeldarmkanker, prostaatkanker, blaaskanker, "
                        "nierkanker, melanoom, huidkanker, maagkanker, slokdarmkanker, "
                        "alvleesklierkanker, leverkanker, eierstokkanker, baarmoederhalskanker, "
                        "baarmoederkanker, schildklierkanker, leukemie, hodgkinlymfoom, "
                        "non-hodgkinlymfoom, hersenkanker, keelkanker."
                    ),
                },
                "year": {
                    "type": "integer",
                    "description": "Jaar van diagnose (bijv. 2020, 2023). Standaard: 2024.",
                },
                "sex": {
                    "type": "string",
                    "enum": ["alle", "man", "vrouw"],
                    "description": "Geslachtsfilter. Standaard: alle.",
                },
                "stat_type": {
                    "type": "string",
                    "enum": ["incidentie", "stadiumverdeling", "prevalentie", "sterfte", "overleving"],
                    "description": (
                        "Type statistiek. "
                        "incidentie = aantal nieuwe diagnoses, "
                        "stadiumverdeling = verdeling per stadium (0/I/II/III/IV), "
                        "prevalentie = aantal levende patiënten, "
                        "sterfte = aantal sterfgevallen, "
                        "overleving = 5-jaars relatieve overleving."
                    ),
                },
                "stage": {
                    "type": "string",
                    "enum": ["alle", "0", "i", "ii", "iii", "iv", "x", "nvt"],
                    "description": "Optioneel stadiumfilter, vooral relevant voor overleving.",
                },
            },
            "required": ["cancer_type", "stat_type"],
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
            "Stel ALLEEN een verduidelijkende vraag. Geef GEEN antwoord, samenvatting of uitleg vooraf. "
            "Gebruik in TWEE situaties: "
            "(1) De vraag is te breed of vaag (bijv. 'kanker', 'behandeling'). "
            "(2) De gevonden bronnen beantwoorden de vraag NIET goed. "
            "Vraag om specificatie (kankersoort, behandeltype, etc.) zodat je gerichter kunt zoeken."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
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
                    "enum": ["cancer_type", "treatment", "statistics", "side_effects", "source_mismatch", "other"],
                    "description": "Categorie van de verduidelijking. Gebruik 'source_mismatch' als de bronnen niet goed matchen met de vraag.",
                },
                "suggested_search": {
                    "type": "string",
                    "description": "Optioneel: een betere zoekopdracht om te proberen als de gebruiker antwoordt, bijv. 'chemotherapie bijwerkingen vermoeidheid tips'.",
                },
            },
            "required": ["clarification_question", "options", "category"],
        },
    },
    {
        "name": "lastmeter_assess",
        "description": (
            "De Lastmeter (Distress Thermometer) — een gevalideerd instrument voor kankerpatiënten. "
            "GEBRUIK DIT PROACTIEF bij elke hint van distress, klachten, of emotionele last. "
            "Trigger-woorden: pijn, moe, vermoeid, angst, bang, zorgen, somber, stress, slapen, "
            "misselijk, eenzaam, boos, niet goed voelen, het is moeilijk, ik kan het niet aan, "
            "bijwerkingen, last, klachten, hoe gaat het, het gaat niet goed, overweldigd, huilen, "
            "zwaar, relatie, werk, financieel, betekenis, dood, afscheid. "
            "BIJ TWIJFEL: gebruik deze tool — het is beter om hulpbronnen te bieden dan te missen. "
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
    {
        "name": "explore_knowledge_graph",
        "description": (
            "Doorzoek de medische kennisgraaf voor relaties tussen kankersoorten, behandelingen, "
            "symptomen en stadia. Gebruik dit als AANVULLING op search_cancer_info om structurele "
            "verbanden te vinden — bijv. welke behandelingen een kankersoort heeft, welke symptomen "
            "voorkomen, of hoe entiteiten met elkaar verbonden zijn. "
            "Het resultaat bevat entiteiten, relaties en bron-URLs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": (
                        "Naam van de entiteit om te verkennen (kankersoort, behandeling, symptoom). "
                        "Bijv. 'borstkanker', 'chemotherapie', 'vermoeidheid'."
                    ),
                },
                "search_type": {
                    "type": "string",
                    "enum": ["related", "cancer_info", "search"],
                    "description": (
                        "Type zoekopdracht: "
                        "'related' = vind gerelateerde entiteiten, "
                        "'cancer_info' = haal alle info over een kankersoort op, "
                        "'search' = fuzzy zoeken op entiteitnaam."
                    ),
                },
            },
            "required": ["entity_name"],
        },
    },
]

# Regex to find [SRC-N] references in answer text
_SRC_REF_RE = re.compile(r"\[SRC-(\d+)\]")


class AnthropicUnavailableError(RuntimeError):
    pass


class MedicalAnswerOrchestrator:
    """Tool-calling agent orchestrator for OncologieWijzer.

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

        # GraphRAG retriever — optional
        self.graph_retriever = None
        if _GraphRetriever is not None:
            try:
                self.graph_retriever = _GraphRetriever(settings)
                if not self.graph_retriever.available:
                    self.graph_retriever = None
                    logger.info("GraphRetriever initialized but Neo4j not available — graph features disabled.")
                else:
                    logger.info("GraphRetriever initialized successfully.")
            except Exception as exc:
                logger.warning("Failed to initialize GraphRetriever: %s", exc)
                self.graph_retriever = None

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

        # ---- Step 0: Check for red flags and attach contacts -----------
        flag_type, _ = check_red_flags(query)
        contacts: list[ContactInfo] = []
        severity: str | None = None
        if flag_type:
            routing = get_routing_info(flag_type)
            if routing:
                severity = routing.get("severity")
                for c in routing.get("contacts", []):
                    contacts.append(ContactInfo(
                        name=c["name"],
                        phone=c.get("phone"),
                        email=c.get("email"),
                        url=c.get("url"),
                        description=c.get("description"),
                        icon=c.get("icon"),
                    ))

        # ---- Step 0.5: Early return for treatment_decision red flags ----
        if flag_type == "treatment_decision":
            routing = get_routing_info(flag_type)
            msg = routing.get("message", "") if routing else ""
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason=(
                    msg or "Behandelbeslissingen zijn persoonlijk — bespreek dit met uw behandelteam."
                ) + "\n\nLet op: deze informatie is informatief en vervangt geen medisch advies.",
                contacts=contacts,
                severity=severity,
                notes=["Treatment decision detected; hard refusal without LLM."],
            )

        # ---- Step 0.6: Pre-classify prompt for banned categories ------
        ban_category, ban_response = classify_prompt(query)

        if ban_category and ban_category not in ("summarization", "impossible_premise"):
            # Pure refusal — no retrieval or LLM needed
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason=ban_response,
                contacts=contacts,
                severity=severity,
                notes=[f"Pre-classified as '{ban_category}'; hard refusal."],
            )

        # ---- Step 1: Retrieve evidence --------------------------------
        retrieval = self.retriever.retrieve(query=query, audience=audience, limit=limit)

        if retrieval.refusal_reason:
            return AnswerResponse(
                query=query,
                audience=audience,
                refusal_reason=retrieval.refusal_reason,
                contacts=contacts,
                severity=severity,
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
                f"URL: {prov.url}\n"
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

        # ---- Step 2.1: Handle banned categories that need source links -
        if ban_category in ("summarization", "impossible_premise"):
            # Return hard response with source links attached (no LLM)
            source_links = "\n".join(
                f"- [SRC-{idx}] {hit.document.title}: {hit.document.provenance.url}"
                for idx, hit in enumerate(retrieval.hits, start=1)
            )
            answer_text = f"{ban_response}\n\n{source_links}"
            answer_text += "\n\nLet op: deze informatie is informatief en vervangt geen medisch advies."
            clarification = None
            if ban_category == "impossible_premise":
                clarification = ClarificationData(
                    brief_answer=ban_response,
                    question="Bedoelt u prostaatkanker bij personen met een prostaat, of zoekt u informatie over een andere kankersoort?",
                    options=["Prostaatkanker", "Een andere kankersoort"],
                    category="cancer_type",
                )
            return AnswerResponse(
                query=query,
                audience=audience,
                answer_markdown=answer_text,
                citations=all_provenances,
                notes=[f"Pre-classified as '{ban_category}'; hard refusal with source links."],
                clarification=clarification,
            )

        # ---- Step 2.5: Detect source mismatch -------------------------
        mismatch_hint = self._detect_source_mismatch(query, retrieval.hits)

        # ---- Step 2.6: Detect distress signals (proactive Lastmeter) --
        distress_domains, distress_hint = self._detect_distress_signals(query)
        if distress_domains:
            extra_provenances, extra_evidence = self._build_lastmeter_evidence(
                distress_domains=distress_domains,
                query=query,
                start_idx=len(all_provenances) + 1,
            )
            if extra_provenances:
                all_provenances.extend(extra_provenances)
                evidence_lines.extend(extra_evidence)
                notes.append("Added Lastmeter support evidence for distress query.")

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

        if mismatch_hint:
            user_message += (
                f"\n\n⚠️ SYSTEEMWAARSCHUWING: {mismatch_hint}\n"
                "ACTIE: Gebruik de ask_clarification tool om de gebruiker te vragen "
                "om meer specifieke informatie. Doe GEEN herhaalde zoekopdrachten — "
                "die geven dezelfde resultaten. Citeer de bovenstaande bronnen NIET "
                "als ze niet bij de vraag passen."
            )

        if distress_hint:
            user_message += (
                f"\n\n🔔 LASTMETER ACTIVATIE: {distress_hint}\n"
                "Je MOET de lastmeter_assess tool aanroepen voor deze patiënt. "
                "Noem expliciet de Lastmeter in je antwoord."
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
        answer_text, clarification = self._process_response(
            client, response, query, audience, evidence_lines, notes
        )

        # ---- Step 4.5: Post-process — strip forbidden patterns ---------
        answer_text = self._validate_output(answer_text)
        answer_text = self._ensure_structured_numeric_output(
            query=query,
            answer_text=answer_text,
            provenances=all_provenances,
        )
        answer_text = self._normalize_citation_aliases(
            answer_text=answer_text,
            provenances=all_provenances,
        )
        answer_text = self._ensure_structured_source_reference(
            query=query,
            answer_text=answer_text,
            provenances=all_provenances,
        )
        answer_text = self._ensure_lastmeter_mention(
            answer_text=answer_text,
            distress_domains=distress_domains,
            provenances=all_provenances,
        )

        # ---- Step 5: Map [SRC-N] references to provenances -----------
        cited_provenances = self._extract_cited_provenances(
            answer_text, all_provenances
        )

        # ---- Step 6: Compute overall answer confidence ---------------
        confidence, confidence_label = self._compute_confidence(
            hit_scores, cited_provenances or all_provenances
        )

        # ---- Step 7: Auto-query graph for related concepts -----------
        graph_context = self._get_graph_context(query)

        return AnswerResponse(
            query=query,
            audience=audience,
            answer_markdown=answer_text,
            citations=cited_provenances if cited_provenances else all_provenances,
            confidence=confidence,
            confidence_label=confidence_label,
            notes=notes,
            clarification=clarification,
            graph_context=graph_context,
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
    ) -> tuple[str | None, ClarificationData | None]:
        """Extract answer text, handling tool_use if Claude requests it.

        Returns (answer_text, clarification_data).
        """

        text_parts: list[str] = []
        tool_results: list[dict[str, Any]] = []
        clarification: ClarificationData | None = None

        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
            elif getattr(block, "type", None) == "tool_use":
                # Capture clarification data before executing
                if block.name == "ask_clarification":
                    clarification = ClarificationData(
                        brief_answer=None,
                        question=block.input.get("clarification_question", ""),
                        options=block.input.get("options", []),
                        category=block.input.get("category", "other"),
                        suggested_search=block.input.get("suggested_search"),
                    )
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
                    elif getattr(block, "type", None) == "tool_use":
                        if block.name == "ask_clarification":
                            clarification = ClarificationData(
                                brief_answer=block.input.get("brief_answer"),
                                question=block.input.get("clarification_question", ""),
                                options=block.input.get("options", []),
                                category=block.input.get("category", "other"),
                                suggested_search=block.input.get("suggested_search"),
                            )

                notes.append("Tool-use round completed.")
            except Exception as exc:
                logger.exception("Follow-up Claude call failed")
                notes.append(f"Tool follow-up error: {exc}")

        answer_text = "\n".join(text_parts).strip() if text_parts else None
        return answer_text, clarification

    # ------------------------------------------------------------------
    # Post-processing output validator
    # ------------------------------------------------------------------

    _FORBIDDEN_OUTPUT_RE = re.compile(
        r"|".join([
            r"Dit\s+betekent\s+dat",
            r"Met\s+andere\s+woorden",
            r"Kort\s+gezegd",
            r"Samenvattend",
            r"In\s+het\s+kort",
            r"Dit\s+wil\s+zeggen",
            r"Dat\s+houdt\s+in\s+dat",
            r"Maar\s+u\s+kunt\s+wel",
            r"Wat\s+u\s+wel\s+kunt\s+doen",
            r"Het\s+is\s+belangrijk\s+om",
            r"Overweeg\s+om",
            r"U\s+kunt\s+overwegen",
            r"Voor\s+u\s+persoonlijk",
            r"In\s+uw\s+geval",
            r"Op\s+basis\s+van\s+uw",
        ]),
        re.IGNORECASE,
    )

    def _validate_output(self, text: str | None) -> str | None:
        """Strip forbidden explanatory/advisory patterns from LLM output."""
        if not text:
            return text
        match = self._FORBIDDEN_OUTPUT_RE.search(text)
        if match:
            # Truncate at the first forbidden pattern
            truncated = text[: match.start()].rstrip()
            if truncated:
                # Keep what came before (likely the source references)
                return truncated + (
                    "\n\nLet op: deze informatie is informatief en vervangt geen medisch advies."
                )
            # Nothing useful before the forbidden pattern
            return (
                "Neem voor verdere informatie contact op met uw behandelteam of huisarts.\n\n"
                "Let op: deze informatie is informatief en vervangt geen medisch advies."
            )
        return text

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
            elif tool_name == "explore_knowledge_graph":
                return self._tool_explore_graph(tool_input)
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
        """Execute query_nkr_statistics tool via NKR API with specific filters."""
        cancer_type = input_data.get("cancer_type", "alle")
        year = input_data.get("year", 2024)
        sex = input_data.get("sex", "alle")
        stat_type = input_data.get("stat_type", "incidentie")
        stage = input_data.get("stage", "alle")
        try:
            data = self.retriever.nkr.query_statistics(
                cancer_type=cancer_type,
                year=year,
                sex=sex,
                stat_type=stat_type,
                stage=stage,
            )
            return {
                "data": str(data)[:3000],
                "filters_used": {
                    "cancer_type": cancer_type,
                    "year": year,
                    "sex": sex,
                    "stat_type": stat_type,
                    "stage": stage,
                },
                "source": "NKR Cijfers IKNL",
                "source_url": "https://nkr-cijfers.iknl.nl/",
                "instruction": "Presenteer ALLEEN de exacte cijfers met bronvermelding. Geen uitleg.",
            }
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

    # ------------------------------------------------------------------
    # Distress signal detection (proactive lastmeter trigger)
    # ------------------------------------------------------------------

    _DISTRESS_KEYWORDS: list[tuple[str, str]] = [
        # (keyword, suggested domain)
        ("pijn", "physical:pain"), ("zeer", "physical:pain"), ("zeer doen", "physical:pain"),
        ("moe", "physical:fatigue"), ("vermoeid", "physical:fatigue"), ("uitgeput", "physical:fatigue"),
        ("zwak", "physical:fatigue"), ("geen energie", "physical:fatigue"),
        ("slapen", "physical:sleep"), ("slaap", "physical:sleep"), ("slapeloosheid", "physical:sleep"),
        ("wakker", "physical:sleep"), ("niet kunnen slapen", "physical:sleep"),
        ("misselijk", "physical:nausea"), ("overgeven", "physical:nausea"), ("braken", "physical:nausea"),
        ("eetlust", "physical:appetite"), ("niet eten", "physical:appetite"), ("gewicht", "physical:appetite"),
        ("adem", "physical:breathing"), ("kortademig", "physical:breathing"), ("benauwd", "physical:breathing"),
        ("bewegen", "physical:mobility"), ("lopen", "physical:mobility"),
        ("haaruitval", "physical:appearance"), ("uiterlijk", "physical:appearance"),
        ("angst", "emotional:anxiety"), ("bang", "emotional:anxiety"), ("paniek", "emotional:anxiety"),
        ("ongerust", "emotional:anxiety"), ("bezorgd", "emotional:anxiety"),
        ("somber", "emotional:depression"), ("depressief", "emotional:depression"),
        ("verdrietig", "emotional:depression"), ("huilen", "emotional:depression"),
        ("hopeloos", "emotional:depression"), ("machteloos", "emotional:depression"),
        ("zorgen", "emotional:worry"), ("onzeker", "emotional:worry"), ("piekeren", "emotional:worry"),
        ("boos", "emotional:anger"), ("gefrustreerd", "emotional:anger"), ("kwaad", "emotional:anger"),
        ("geen zin", "emotional:loss_of_interest"), ("nergens zin", "emotional:loss_of_interest"),
        ("werk", "practical:work"), ("baan", "practical:work"),
        ("geld", "practical:financial"), ("financ", "practical:financial"), ("verzekering", "practical:financial"),
        ("kinderen", "practical:childcare"), ("kinderopvang", "practical:childcare"),
        ("vervoer", "practical:transport"),
        ("partner", "social:partner"), ("relatie", "social:partner"), ("intimiteit", "social:partner"),
        ("gezin", "social:family"), ("familie", "social:family"),
        ("vrienden", "social:friends"), ("alleen", "social:friends"), ("eenzaam", "social:friends"),
        ("isolatie", "social:friends"),
        ("waarom", "spiritual:meaning"), ("zinloos", "spiritual:meaning"), ("betekenis", "spiritual:meaning"),
        ("geloof", "spiritual:faith"),
        ("dood", "spiritual:death"), ("afscheid", "spiritual:death"), ("doodgaan", "spiritual:death"),
        # General distress phrases
        ("last", "emotional:worry"), ("klachten", "physical:pain"),
        ("het gaat niet goed", "emotional:depression"), ("moeilijk", "emotional:worry"),
        ("zwaar", "emotional:worry"), ("niet meer", "emotional:depression"),
        ("kan het niet aan", "emotional:worry"), ("te veel", "emotional:worry"),
        ("overweldigd", "emotional:anxiety"), ("stress", "emotional:anxiety"),
        ("emotioneel", "emotional:worry"), ("niet lekker", "physical:pain"),
        ("ziek", "physical:pain"), ("bijwerkingen", "physical:pain"),
    ]

    @staticmethod
    def _detect_distress_signals(query: str) -> tuple[list[str], str | None]:
        """Detect distress signals in the query and return suggested domains + hint.

        Returns (matched_domains, hint_text). If no distress detected, returns ([], None).
        """
        q_lower = query.lower()
        matched_domains: list[str] = []
        seen: set[str] = set()

        for keyword, domain in MedicalAnswerOrchestrator._DISTRESS_KEYWORDS:
            if keyword in q_lower and domain not in seen:
                matched_domains.append(domain)
                seen.add(domain)

        if not matched_domains:
            return [], None

        domain_list = ", ".join(matched_domains[:8])
        hint = (
            f"De patiënt toont tekenen van distress. "
            f"Gedetecteerde probleemgebieden: {domain_list}. "
            f"GEBRUIK de lastmeter_assess tool met deze domeinen om relevante hulpbronnen "
            f"op te halen. Schat een passende distress_score in op basis van de toon."
        )
        return matched_domains, hint

    # ------------------------------------------------------------------
    # Source mismatch detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_source_mismatch(query: str, hits: list) -> str | None:
        """Detect when retrieved sources don't match the query topic.

        Returns a hint string if mismatch is detected, None otherwise.
        """
        if not hits:
            return None

        q_lower = query.lower()

        # Extract key topics from query
        query_topics = set()
        treatment_keywords = {
            "chemotherapie": "chemotherapie", "bestraling": "bestraling",
            "immunotherapie": "immunotherapie", "operatie": "operatie",
            "hormoontherapie": "hormoontherapie", "doelgerichte therapie": "doelgerichte therapie",
        }
        cancer_keywords = {
            "borstkanker": "borstkanker", "longkanker": "longkanker",
            "darmkanker": "darmkanker", "prostaatkanker": "prostaatkanker",
            "huidkanker": "huidkanker", "melanoom": "melanoom",
            "leukemie": "leukemie", "lymfoom": "lymfoom",
        }
        symptom_keywords = {
            "vermoeidheid": "vermoeidheid", "pijn": "pijn", "misselijkheid": "misselijkheid",
            "slaap": "slaapproblemen", "haaruitval": "haaruitval",
            "bijwerkingen": "bijwerkingen",
        }

        for kw, topic in treatment_keywords.items():
            if kw in q_lower:
                query_topics.add(("treatment", topic))
        for kw, topic in cancer_keywords.items():
            if kw in q_lower:
                query_topics.add(("cancer", topic))
        for kw, topic in symptom_keywords.items():
            if kw in q_lower:
                query_topics.add(("symptom", topic))

        if not query_topics:
            return None  # Can't detect mismatch without clear topics

        # Check if retrieved sources match the query topics
        hit_titles = " ".join(h.document.title.lower() for h in hits[:5])
        hit_urls = " ".join(h.document.url.lower() for h in hits[:5])
        hit_text = hit_titles + " " + hit_urls

        # If query mentions a specific treatment but sources are about different cancers
        query_treatments = [t[1] for t in query_topics if t[0] == "treatment"]
        query_cancers = [t[1] for t in query_topics if t[0] == "cancer"]

        if query_treatments and not query_cancers:
            # User asks about a treatment in general → sources are cancer-specific
            # Check if sources are about unrelated cancer types
            cancer_types_in_hits = set()
            cancer_names = [
                "vaginakanker", "schaamlipkanker", "baarmoederkanker",
                "baarmoederhalskanker", "vulvakanker", "eierstokkanker",
                "borstkanker", "longkanker", "darmkanker", "prostaatkanker",
                "melanoom", "huidkanker", "leukemie", "lymfoom",
                "blaaskanker", "nierkanker", "maagkanker", "slokdarmkanker",
            ]
            for name in cancer_names:
                if name in hit_text:
                    cancer_types_in_hits.add(name)

            if len(cancer_types_in_hits) >= 2:
                # Sources are about multiple random cancer types — mismatch
                return (
                    f"De bronnen gaan over vermoeidheid/bijwerkingen bij specifieke kankersoorten "
                    f"({', '.join(list(cancer_types_in_hits)[:3])}), maar de vraag gaat over "
                    f"{' en '.join(query_treatments)} in het algemeen. "
                    f"Onze informatie is per kankersoort georganiseerd."
                )

        return None

    def _tool_ask_clarification(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Return clarification data — the agent will format this into its response."""
        return {
            "type": "clarification",
            "brief_answer": input_data.get("brief_answer", ""),
            "question": input_data.get("clarification_question", ""),
            "options": input_data.get("options", []),
            "category": input_data.get("category", "other"),
        }

    def _tool_explore_graph(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute explore_knowledge_graph tool via GraphRetriever."""
        if not self.graph_retriever:
            return {"error": "Knowledge graph not available", "entities": [], "relationships": []}

        entity_name = input_data.get("entity_name", "")
        search_type = input_data.get("search_type", "related")

        try:
            if search_type == "cancer_info":
                result = self.graph_retriever.get_cancer_type_info(entity_name)
            elif search_type == "search":
                entities = self.graph_retriever.search_entities(entity_name, limit=10)
                result = {"entities": entities, "relationships": [], "sources": []}
                # Collect sources from entities
                for ent in entities:
                    result["sources"].extend(ent.get("sources", []))
                result["sources"] = list(set(result["sources"]))[:20]
            else:  # "related" (default)
                result = self.graph_retriever.find_related(entity_name, max_hops=2)

            return {
                "source": "Neo4j Knowledge Graph",
                **result,
            }
        except Exception as exc:
            logger.warning("explore_knowledge_graph failed: %s", exc)
            return {"error": str(exc), "entities": [], "relationships": []}

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

    @staticmethod
    def _estimate_distress_score(query: str, distress_domains: list[str]) -> int:
        q_lower = query.lower()
        score = max(4, min(10, len(distress_domains) + 3))
        if any(token in q_lower for token in ("erg", "bijna niet", "zwaar", "niet meer", "overweldigd")):
            score = max(score, 7)
        return score

    def _build_lastmeter_evidence(
        self,
        *,
        distress_domains: list[str],
        query: str,
        start_idx: int,
    ) -> tuple[list[Provenance], list[str]]:
        result = self._tool_lastmeter_assess(
            {
                "domains": distress_domains[:4],
                "distress_score": self._estimate_distress_score(query, distress_domains),
                "patient_message": query,
            }
        )
        resources = result.get("resources", []) if isinstance(result, dict) else []
        provenances: list[Provenance] = []
        evidence_lines: list[str] = []

        for offset, resource in enumerate(resources[:3], start=start_idx):
            url = resource.get("url") or ""
            title = resource.get("title") or "Lastmeter-hulpbron"
            excerpt = resource.get("excerpt") or "Hulpbron uit kanker.nl voor Lastmeter-gerelateerde ondersteuning."
            prov = Provenance(
                source_id="kanker.nl",
                title=title,
                url=url,
                canonical_url=url,
                publisher="KWF / NFK / IKNL",
                excerpt=excerpt,
                metadata={
                    "lastmeter": True,
                    "lastmeter_domain": resource.get("domain"),
                },
            )
            provenances.append(prov)
            evidence_lines.append(
                f"[SRC-{offset}] {title}\n"
                f"Bron: {prov.publisher}\n"
                f"URL: {url}\n"
                "Relevantie: 100%\n"
                f"Fragment: {excerpt}\n"
            )

        return provenances, evidence_lines

    @staticmethod
    def _ensure_disclaimer(text: str | None) -> str | None:
        if not text:
            return text
        disclaimer = "Let op: deze informatie is informatief en vervangt geen medisch advies."
        if disclaimer.lower() in text.lower():
            return text
        return text.rstrip() + f"\n\n{disclaimer}"

    def _ensure_structured_numeric_output(
        self,
        *,
        query: str,
        answer_text: str | None,
        provenances: list[Provenance],
    ) -> str | None:
        q_lower = query.lower()
        if not any(
            token in q_lower
            for token in (
                "hoeveel",
                "hoe vaak",
                "komt het voor",
                "incidentie",
                "prevalentie",
                "overleving",
                "sterfte",
                "cijfers",
                "percentage",
                "postcode",
            )
        ):
            return answer_text
        if answer_text and _NUMERIC_SIGNAL_RE.search(answer_text):
            return answer_text

        for idx, prov in enumerate(provenances, start=1):
            if prov.source_id not in {"nkr-cijfers", "kankeratlas"}:
                continue
            if not prov.excerpt or not _NUMERIC_SIGNAL_RE.search(prov.excerpt):
                continue
            fallback = f"Exact cijfer uit de bron: {prov.excerpt} [SRC-{idx}]"
            return self._ensure_disclaimer(fallback)

        return answer_text

    @staticmethod
    def _normalize_citation_aliases(
        *,
        answer_text: str | None,
        provenances: list[Provenance],
    ) -> str | None:
        if not answer_text:
            return answer_text

        alias_to_sources = {
            "incidentie": ("nkr-cijfers",),
            "nkr": ("nkr-cijfers",),
            "nkr-cijfers": ("nkr-cijfers",),
            "atlas": ("kankeratlas",),
            "richtlijn": ("richtlijnendatabase",),
            "guideline": ("richtlijnendatabase",),
            "kg": ("kanker.nl",),
            "kanker": ("kanker.nl",),
            "kanker.nl": ("kanker.nl",),
        }

        def replace(match: re.Match[str]) -> str:
            token = match.group(1)
            if token.isdigit():
                return match.group(0)

            normalized = token.strip().lower()
            source_ids = alias_to_sources.get(normalized)
            if source_ids is None:
                for key, candidate_sources in alias_to_sources.items():
                    if key in normalized:
                        source_ids = candidate_sources
                        break
            if source_ids is None:
                return match.group(0)

            for idx, prov in enumerate(provenances, start=1):
                if prov.source_id in source_ids:
                    return f"[SRC-{idx}]"
            return match.group(0)

        return re.sub(r"\[SRC-([^\]]+)\]", replace, answer_text)

    def _ensure_structured_source_reference(
        self,
        *,
        query: str,
        answer_text: str | None,
        provenances: list[Provenance],
    ) -> str | None:
        if not answer_text:
            return answer_text

        q_lower = query.lower()
        if not any(
            token in q_lower
            for token in (
                "overleving",
                "overlevingskans",
                "incidentie",
                "prevalentie",
                "sterfte",
                "cijfers",
                "hoeveel",
                "hoe vaak",
                "komt het voor",
                "postcode",
            )
        ):
            return answer_text

        source_messages = {
            "nkr-cijfers": "Voor landelijke registratiestatistieken gebruikt OncologieWijzer NKR Cijfers",
            "kankeratlas": "Voor regionale incidentiedata gebruikt OncologieWijzer Kanker Atlas",
        }

        for idx, prov in enumerate(provenances, start=1):
            prefix = source_messages.get(prov.source_id)
            if not prefix:
                continue
            if f"[SRC-{idx}]" in answer_text:
                return answer_text
            return self._ensure_disclaimer(
                f"{answer_text.rstrip()}\n\n{prefix} [SRC-{idx}]."
            )

        return answer_text

    def _ensure_lastmeter_mention(
        self,
        *,
        answer_text: str | None,
        distress_domains: list[str],
        provenances: list[Provenance],
    ) -> str | None:
        if not distress_domains:
            return answer_text
        if answer_text and "lastmeter" in answer_text.lower():
            return self._ensure_disclaimer(answer_text)

        lastmeter_index: int | None = None
        for idx, prov in enumerate(provenances, start=1):
            if prov.metadata.get("lastmeter"):
                lastmeter_index = idx
                break

        base_text = (answer_text or "Ik hoor dat u het zwaar heeft.").rstrip()
        if lastmeter_index is None:
            addition = "De Lastmeter kan helpen om klachten en zorgen in kaart te brengen en met uw arts of verpleegkundige te bespreken."
        else:
            addition = (
                "De Lastmeter kan helpen om klachten en zorgen in kaart te brengen "
                f"en met uw arts of verpleegkundige te bespreken [SRC-{lastmeter_index}]."
            )
        return self._ensure_disclaimer(f"{base_text}\n\n{addition}")

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _get_graph_context(self, query: str) -> dict | None:
        """Auto-query Neo4j graph for entities related to the query.
        Returns a dict with entities and relationships, or None if graph unavailable."""
        if not self.graph_retriever:
            return None
        try:
            q_lower = query.lower()
            # Try multiple search strategies
            result = None
            # 1. Try full query
            result = self.graph_retriever.search_entities(q_lower, limit=5)
            # 2. If no results, try individual words (skip stopwords)
            if not result:
                stopwords = {"wat", "is", "de", "het", "een", "van", "bij", "voor",
                             "en", "in", "op", "met", "over", "hoe", "kan", "ik",
                             "what", "is", "the", "a", "of", "for", "and", "how",
                             "about", "are", "information", "informatie"}
                # Strip punctuation from each word
                import string
                words = [w.strip(string.punctuation) for w in q_lower.split()]
                words = [w for w in words if w not in stopwords and len(w) > 2]
                for word in words:
                    result = self.graph_retriever.search_entities(word, limit=3)
                    if result:
                        break
            if not result:
                return None
            best = result[0]
            entity_name = best.get("name", "")
            if not entity_name:
                return None
            related = self.graph_retriever.find_related(entity_name, max_hops=1)
            entities = related.get("entities", [])
            relationships = related.get("relationships", [])
            if not entities and not relationships:
                return None
            return {
                "center": entity_name,
                "entities": entities[:15],
                "relationships": relationships[:15],
                "sources": related.get("sources", [])[:5],
            }
        except Exception:
            return None

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
