from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum
from config.prompts import QUERY_ROUTER_PROMPT
from models.gemini_client import generate_json
from utils.logger import get_logger

logger = get_logger(__name__)

class QueryType(str, Enum):
    GRAPH_TRAVERSAL   = "GRAPH_TRAVERSAL"
    VECTOR_SIMILARITY = "VECTOR_SIMILARITY"
    HYBRID            = "HYBRID"
    AGENT_COMPLEX     = "AGENT_COMPLEX"
    AMBIGUOUS         = "AMBIGUOUS"
    OUT_OF_DOMAIN     = "OUT_OF_DOMAIN"
    GREETING          = "GREETING"


@dataclass
class RoutingResult:
    """Encapsulates the full output of query routing."""
    query_type: QueryType
    reasoning: str
    clarification_needed: str | None = None  # Only set for AMBIGUOUS


# Signal Pattern Definitions
# 1. SIMILARITY signals
# Vocabulary indicating the user wants embeddings / semantic proximity.
_SIM = re.compile(
    r"\b("
    # Direct similarity phrases
    r"similar to|similar papers?|similar works?|similar research|"
    r"recommend(ed)?|suggestion|suggest|"
    r"related to|related papers?|related works?|related research|"
    r"find .{0,30} like|papers? like|works? like|research like|"
    r"thematic(ally)?|in the same vein|reminds me of|analog(ous)? to|"
    r"semantically (similar|related|close|near|equivalent)|"
    r"closest to|nearest to|most similar|conceptually (similar|related)|"
    r"in the spirit of|along the lines of|akin to|"
    # Retrieval verbs with semantic topic object
    r"papers? (on|about|covering|addressing|discussing|exploring|surveying)|"
    r"research (on|about|in the area of|in the field of)|"
    r"works? (on|about|covering|addressing)|"
    r"literature (on|about|related to)|"
    r"find .{0,20}(papers?|research|works?|articles?) .{0,20}(on|about|regarding)|"
    r"retrieve (papers?|research|works?)|"
    r"papers? (dealing with|examining|investigating|focused on|centred? on)|"
    r"show me (papers?|research|works?) .{0,20}(on|about|regarding|related|similar)"
    r")\b",
    re.IGNORECASE,
)

# 2. STRUCTURAL CONSTRAINT signals 
# Hard filters that map to WHERE clauses in Cypher.
_STRUCT = re.compile(
    r"("
    # Year / date constraints
    r"\bpublished (after|before|in|between|during|since|from)\b|"
    r"\bafter \d{4}\b|\bbefore \d{4}\b|\bsince \d{4}\b|"
    r"\bfrom \d{4}\b|\buntil \d{4}\b|\bin \d{4}\b|"
    r"\b\d{4}\s*[-–]\s*\d{4}\b|"                   
    r"\bbetween \d{4} and \d{4}\b|"
    r"\b(post|pre)-?\d{4}\b|"
    r"\b(recent|last|past) \d+ years?\b|"
    r"\b(early|late|mid) \d{4}s?\b|"                
    # Venue / conference / journal
    r"\b(SIGIR|NAACL|TKDE|TNNLS|ACL|EMNLP|NeurIPS|NIPS|ICML|ICLR|AAAI|"
    r"WWW|WSDM|KDD|CIKM|ISWC|ESWC|TACL|COLING|CVPR|ECCV|ICCV|IROS|ICRA|"
    r"VLDB|SIGMOD|ICDE|ACM CCS|USENIX|OSDI|SOSP|PLDI|POPL)\b|"
    r"\b(venue|conference|journal|workshop|proceedings|preprint|arxiv|track)\b|"
    # Citation / property constraints
    r"\b(more|greater|less|fewer|over|above|below|under|at least|at most)"
    r"\s*(than\s*)?\d+\s*citations?\b|"
    r"\b\d{3,}\s*citations?\b|"
    r"\b(highly|most|top|least)\s*cited\b|"
    r"\bcitations?_?count\b|"                        # catch citations_count
    r"\bh.?index\s*(of|above|below|greater|less|over|under)\s*\d+\b|"
    r"\bimpact.?factor\b|"
    # Affiliation / institution constraints
    r"\b(at|from|by researchers? (at|from)|affiliated with|based at|working at)\s+"
    r"(MIT|Stanford|CMU|Berkeley|Oxford|Cambridge|ETH|EPFL|Tsinghua|Peking|"
    r"DeepMind|Google|Microsoft|Meta|OpenAI|Amazon|IBM|Yahoo|Baidu|Alibaba)\b|"
    r"\baffiliat(ed|ion|ions?)\b|"
    # Author-position constraints
    r"\b(first|second|third|last|corresponding|sole)\s+author\b|"
    r"\bonly\s+(by|from|at|authored|published)\b|"
    # Language / format constraints
    r"\b(english|chinese|french|german|spanish)\s+(language|only|papers?)\b|"
    r"\b(open.?access|peer.?reviewed|survey|review paper)\b"
    r")",
    re.IGNORECASE,
)

# 3. GRAPH TRAVERSAL signals
# Explicit node/property/relationship lookup vocabulary.
_GRAPH = re.compile(
    r"\b("
    # Author lookups
    r"who (authored?|wrote|published|co-?authored?)|"
    r"who are the (authors?|researchers?|writers?)|"
    r"author(s)? of (the )?(paper|work|article)|"
    r"(papers?|publications?|works?|articles?) (by|from|of) [A-Z]\w|" 
    r"authored by|co-?authored? (by|with)|"
    r"(list|show|get|fetch|give me|what are) .{0,25}"
    r"(papers?|publications?|works?|articles?) (by|from|of|authored by)|"
    # Counting / aggregation
    r"how many (papers?|publications?|citations?|authors?|co-?authors?|journals?)|"
    r"(number|count|total) of (papers?|publications?|citations?|authors?)|"
    # Temporal property lookup
    r"when was .{3,50} published|what year .{3,50} published|"
    r"publication (date|year) of|year (it was )?(published|appeared)|"
    # Citation graph traversal
    r"papers? that (cite|cited|reference)|papers? (citing|cited by)|"
    r"citation(s?) (of|for)|cited (by|in)|references? of|bibliography|"
    r"(which|what) papers? cite|"
    # Collaboration / co-authorship network
    r"co-?authors? of|collaborat(ed|ors?|ion) (with|between)|"
    r"who (has|have) collaborated with|"
    # Venue lookup
    r"(which|what) (journal|conference|venue|proceedings) (published|did .{3,30} appear)|"
    r"(papers?|works?) published in [A-Z]|"   
    # Institution / affiliation lookup
    r"(institution|university|lab|affiliation) of|"
    r"(where|what institution) (does|did|is) .{3,30} (work|research|affiliated)|"
    # Metrics / properties
    r"h-?index of|citation count of|impact factor of|"
    r"(number|count) of citations?|"
    # Specific paper lookup by title
    r"(find|get|show|what is|retrieve) the paper (titled?|called|named)|"
    r"find paper (titled?|called)|"
    # Topological queries
    r"most (cited|recent|prolific) (?!.*similar)(?!.*related)|"
    r"(top|first|last) \d+ (papers?|authors?|journals?)"
    r")\b",
    re.IGNORECASE,
)

# 4. AGENT COMPLEX signals 
# Multi-step analytical queries that require the ReAct agent.
_COMPLEX = re.compile(
    r"\b("
    # Comparison / contrast (multi-entity)
    r"compare|contrast|"
    r"difference(s?) between .{3,50} and .{3,}|"
    r"similarities between .{3,50} and .{3,}|"
    r"how (does|do|did) .{3,40} (compare|differ|relate) to|"
    r"\bvs\.?\b|\bversus\b|"
    # Evolution / longitudinal trends
    r"how (has|have|did) .{3,40} (evolved?|changed?|progressed?|developed?|grown?)|"
    r"(research|publication|citation) (trend|trajectory|evolution|history|progress)|"
    r"(over|throughout|across) (time|the years|decades?)|"
    r"(timeline|history|chronology|progression) of|"
    # Global ranking / extremes
    r"who (has|is) (the |most )?(most|least|highest|lowest|greatest|largest|smallest|frequent|active|prolific|cited)|"
    r"(most|least|largest|greatest|smallest) (number|count|amount|frequent(ly)?|often) of|"
    r"(most|least) (productive|influential|prolific|active) (author|researcher|scholar)|"
    r"(top|best|leading|highest.ranking) (author|researcher) (in|for|on)\b|"
    r"rank(ing)? (them |the )?(of |the )?(by|according to)|" 
    # Network / path / multi-entity reasoning
    r"(collaborat(ed|ion|ing)?|co-?authorship) (network|frequency|most|often|frequent(ly)?)|"
    r"(path|connection|link|relationship) (between|from) .{3,40} (to|and) .{3,}|"
    r"(bridge|connect|span|link).{0,25}(field|domain|area|topic)s?.{0,25}(and|with)|"
    r"across (all|different|multiple|various) (fields?|domains?|topics?)|"
    # Compound / multi-hop intent markers
    r"given .{5,50}[,;] (what|who|which|find|show|list)|"
    r"(and then|then|later|afterwards|subsequently) (find|look|check|see|compare|list|restrict|filter|rank|extract|co-?author|publish)|"
    r"multi.?step|multi.?hop|chain of (thought|reasoning)|step by step|"
    r"(a\) |b\) |c\) |\(a\)|\(b\)|\(1\)|\(2\))"    
    # Analytical / synthesis
    r"(explain|analyze|analyse|summarize|breakdown|break down) (why|how|the impact)|"
    r"impact of .{3,50} on .{3,}|"
    r"\b(metrics?|baselines?|benchmarks?|evaluat(ed|ion)|performance|improvement)\b|"
    r"(who|which authors?) .{0,40}(both|also|and) .{0,40}(authored?|published|worked)"
    r")\b",
    re.IGNORECASE,
)

# 5. AMBIGUOUS signals 
_AMBIGUOUS = re.compile(
    r"^("
    r"tell me|show me|find|give me|i want|what is|research|papers?|"
    r"help|anything|something|info(rmation)?|data|results?"
    r")[\s.!?]*$",
    re.IGNORECASE,
)

# 6. CONTEXT DEPENDENCE signals 
# Pronouns and relative terms that indicate a follow-up question.
_CONTEXT = re.compile(
    r"\b(it|they|them|their|his|her|this|that|those|these|previous|above|former|latter|him)\b",
    re.IGNORECASE,
)

# 7. GREETING signals
_GREETING = re.compile(
    r"^("
    r"hi|hello|hey|greetings|morning|afternoon|evening|hola|yo|sup|what's up|howdy|"
    r"how are you|how is it going|nice to meet you"
    r")([\s\w]{0,15})[\s.!?]*$",
    re.IGNORECASE,
)


# Pre-filter decision function
def _rule_based_prefilter(question: str) -> QueryType | None:
    """
    Robust rule-based classification — runs synchronously before any LLM call.

    Decision tree (strict priority order):
      1. AMBIGUOUS    — too short (≤3 words) or clearly vague
      2. AGENT_COMPLEX — any multi-step / comparative / analytical signal
      3. HYBRID       — similarity signal + structural constraint OR graph lookup
      4. VECTOR_SIMILARITY — similarity only, zero hard constraints
      5. GRAPH_TRAVERSAL  — graph/explicit lookup or structural-only (no similarity)
      6. None (defer)  — no strong signal detected → let Gemini classify

    Returns QueryType or None.
    """
    q = question.strip()

    # 1. Greetings
    if _GREETING.match(q):
        return QueryType.GREETING

    # 2. Too short or obviously vague
    if len(q.split()) <= 3 or _AMBIGUOUS.match(q):
        return QueryType.AMBIGUOUS

    has_sim     = bool(_SIM.search(q))
    has_struct  = bool(_STRUCT.search(q))
    has_graph   = bool(_GRAPH.search(q))
    has_complex = bool(_COMPLEX.search(q))
    has_context = bool(_CONTEXT.search(q))

    logger.debug(
        "Pre-filter signals for query: sim=%s struct=%s graph=%s complex=%s context=%s",
        has_sim, has_struct, has_graph, has_complex, has_context
    )

    if has_context:
        return None 

    if has_complex:
        return QueryType.AGENT_COMPLEX

    if has_sim and (has_struct or has_graph):
        return QueryType.HYBRID

    if has_sim and not has_struct and not has_graph:
        return QueryType.VECTOR_SIMILARITY

    if has_graph and not has_sim:
        return QueryType.GRAPH_TRAVERSAL

    if has_struct and not has_sim and not has_graph:
        return QueryType.GRAPH_TRAVERSAL

    # 6. No strong signal — let Gemini decide
    return None


# Main router
def route_query(question: str, conversation_history: str = "") -> RoutingResult:
    logger.info("Routing question: '%s'", question.replace("\n", " "))

    #Step 1: Try rule-based pre-filter 
    prefilter_type = _rule_based_prefilter(question)
    if prefilter_type is not None:
        logger.debug("Pre-filter classified as: %s", prefilter_type.value)
        if prefilter_type == QueryType.AMBIGUOUS:
            return RoutingResult(
                query_type=QueryType.AMBIGUOUS,
                reasoning="Question is too short or vague for the pre-filter",
                clarification_needed=_generate_clarification_hint(question),
            )
        return RoutingResult(
            query_type=prefilter_type,
            reasoning="Matched by rule-based pre-filter pattern",
        )

    # Step 2: LLM-based classification 
    prompt = QUERY_ROUTER_PROMPT.format(
        question=question,
        conversation_history=conversation_history or "No prior conversation",
    )

    try:
        result = generate_json(prompt)
    except (ValueError, Exception) as e:
        logger.warning("Router LLM call failed, defaulting to GRAPH_TRAVERSAL: %s", e)
        return RoutingResult(
            query_type=QueryType.GRAPH_TRAVERSAL,
            reasoning="LLM routing failed; defaulting to graph traversal",
        )

    raw_type = result.get("type", "GRAPH_TRAVERSAL").upper()
    try:
        query_type = QueryType(raw_type)
    except ValueError:
        logger.warning("Unknown query type from LLM: %s", raw_type)
        query_type = QueryType.GRAPH_TRAVERSAL

    clarification = result.get("clarification_needed")
    if isinstance(clarification, str) and clarification.lower() in ("null", "none", ""):
        clarification = None

    logger.info("Routed to: %s (reason: %s)", str(query_type), result.get("reasoning", ""))

    return RoutingResult(
        query_type=query_type,
        reasoning=result.get("reasoning", ""),
        clarification_needed=clarification,
    )


def _generate_clarification_hint(question: str) -> str:
    return (
        "Your question is a bit broad — could you be more specific? For example:\n"
        "• 'Who authored the paper Attention Is All You Need?'\n"
        "• 'Find papers similar to deep learning and computer vision'\n"
        "• 'Which authors at Stanford have collaborated with MIT researchers?'"
    )
