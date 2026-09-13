"""S3 — Ecosystem Facts & Provenance Queries.

Read-only query/aggregation слой над существующим состоянием KnowledgeCore:
  find_node / find_package / nodes_by_io / explain_node / gap_report.

Инварианты (утверждённый design docs/ECOSYSTEM_FIRST_S3_DESIGN.md):
- Advisory-only: чистые функции от текущего состояния. НЕТ записей, НЕТ
  регистрации, НЕТ изменения Readiness/execution eligibility (AD-45 сохранён).
- Никаких догадок о семантике: NodeFacts строится ИСКЛЮЧИТЕЛЬНО из полей
  NodeSchema / NodeDoc / claims / Candidates / registries.
- Provenance — существующие EvidenceTrustLevel/ClaimStatus. НОВЫХ ENUM НЕТ.
- Per-node cost НЕ вводится (AD-46): поле cost — константный маркер.
- comfy_api_nodes.* — api_family = ФАКТ ПУТИ МОДУЛЯ, не стоимость.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.knowledge.models import ClaimStatus
from app.knowledge.node_schema import FieldSpec, NodeSchema

# --- Классификация ролей (design §3.2) — единственное определение ---
GRAPH_TYPES = frozenset({
    "MODEL", "CLIP", "VAE", "LATENT", "CONDITIONING", "CONTROL_NET",
})
MEDIA_TYPES = frozenset({"IMAGE", "VIDEO", "AUDIO"})
_LOADER_ALLOWED_REQUIRED = frozenset({"ENUM", "STRING"})

# Константный маркер: per-node cost сознательно НЕ введён (AD-46)
COST_NOT_APPLICABLE = "N/A (per-node cost не введён — AD-46)"

_STATUS_ORDER = {
    ClaimStatus.UNKNOWN: 0,
    ClaimStatus.INFERENCE: 1,
    ClaimStatus.SUPPORTED: 2,
    ClaimStatus.CONFIRMED: 3,
}


@dataclass(frozen=True)
class NodeFacts:
    """Плоский view-объект (НЕ сущность хранения). Только факты."""
    class_type: str
    display_name: str
    category: str
    python_module: str
    package: str
    role: str  # head | loader | processor | fragment | sink | other
    inputs: tuple[FieldSpec, ...]
    outputs: tuple[str, ...]
    safety: str
    best_claim_status: str
    claims: tuple[Any, ...]
    docs: Any  # Optional[NodeDocEntry]
    templates_available: tuple[str, ...]
    in_workflow_registry: bool
    cost: str = COST_NOT_APPLICABLE

    def to_dict(self) -> dict:
        return {
            "class_type": self.class_type,
            "display_name": self.display_name,
            "category": self.category,
            "python_module": self.python_module,
            "package": self.package,
            "role": self.role,
            "inputs": [f.to_dict() for f in self.inputs],
            "outputs": list(self.outputs),
            "safety": self.safety,
            "best_claim_status": self.best_claim_status,
            "claims": [c.to_dict() for c in self.claims],
            "docs": self.docs.to_dict() if self.docs is not None else None,
            "templates_available": list(self.templates_available),
            "in_workflow_registry": self.in_workflow_registry,
            "cost": self.cost,
        }


@dataclass(frozen=True)
class PackageFacts:
    package_id: str
    classes: tuple[str, ...]
    is_custom: bool
    api_family: bool
    safety_profile: str
    doc_coverage: int
    provenance: str = "derived:live-or-snapshot /object_info"


@dataclass(frozen=True)
class GapEntry:
    subject: str
    gap_type: str
    description: str
    priority: str = "MEDIUM"

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "gap_type": self.gap_type,
            "description": self.description,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class NodeExplanation:
    facts: NodeFacts
    what_is_known: tuple[str, ...]
    what_is_not_proven: tuple[str, ...]
    template_hint: str
    provenance_sections: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "facts": self.facts.to_dict(),
            "what_is_known": list(self.what_is_known),
            "what_is_not_proven": list(self.what_is_not_proven),
            "template_hint": self.template_hint,
            "provenance_sections": dict(self.provenance_sections),
        }


# --------------------------------------------------------------------------- #
# helpers (чистые)
# --------------------------------------------------------------------------- #

def package_of(python_module: str) -> str:
    """Пакет выводится из python_module (факт пути, без догадок)."""
    m = python_module or ""
    if m.startswith("custom_nodes."):
        return m[len("custom_nodes."):]
    if m.startswith("comfy_api_nodes."):
        return m  # comfy_api_nodes.nodes_X — сам является именем пакета
    if m.startswith("nodes") or m.startswith("comfy_extras"):
        return "built-in"
    return m.split(".")[0] if m else "unknown"


def is_api_family(python_module: str) -> bool:
    return (python_module or "").startswith("comfy_api_nodes.")


def classify_role(schema: NodeSchema) -> str:
    """head/loader/processor/fragment/sink/other — детерминированно (§3.2)."""
    required_types = {f.type for f in schema.input_required}
    outputs = {o for o in schema.output_types if isinstance(o, str)}
    name = schema.class_type or ""

    if name.startswith("Save"):
        return "sink"
    if (outputs & GRAPH_TYPES) and required_types <= _LOADER_ALLOWED_REQUIRED:
        return "loader"
    if (outputs & MEDIA_TYPES) and not (required_types & GRAPH_TYPES) \
            and not (required_types & MEDIA_TYPES):
        return "head"
    if (required_types & MEDIA_TYPES) and (outputs & MEDIA_TYPES):
        return "processor"
    if required_types & GRAPH_TYPES:
        return "fragment"
    return "other"


def _safety_of(schema: NodeSchema) -> str:
    from app.synthesis.safety import classify_safety
    return classify_safety(schema.python_module, schema.category, schema.class_type).value


def _templates_for(core, schema) -> tuple[str, ...]:
    """S2 select_template для существующих candidates ноды (чистая функция)."""
    ids: list[str] = []
    cands = core._candidates.get(schema.class_type, [])
    if not cands:
        return ()
    try:
        from app.synthesis.selector import select_template
    except Exception:
        return ()
    for cand in cands:
        try:
            tmpl = select_template(cand, schema)
        except Exception:
            tmpl = None
        if tmpl is not None and tmpl.template_id not in ids:
            ids.append(tmpl.template_id)
    return tuple(ids)


def _in_registry(core, schema) -> bool:
    """capability ЕСТЬ у существующих candidates и registry их знает (факт)."""
    registry = getattr(core, "_workflow_registry", None)
    if registry is None:
        return False
    for cand in core._candidates.get(schema.class_type, []):
        try:
            if registry.by_capability(cand.capability):
                return True
        except Exception:
            continue
    return False


def _claims_for(core, class_type: str):
    return tuple(c for c in core._claims if c.subject == class_type)


def _best_status(core, class_type: str) -> str:
    claims = _claims_for(core, class_type)
    best = ClaimStatus.UNKNOWN
    for c in claims:
        if _STATUS_ORDER.get(c.status, 0) > _STATUS_ORDER[best]:
            best = c.status
    return best.value


def _doc_for(core, class_type: str):
    """NodeDoc из того же data_dir, что и persistence core (только чтение)."""
    try:
        from app.knowledge.node_doc import NodeDocStore
        data_dir = getattr(core._claims_persistence, "_data_dir", None)
        store = NodeDocStore(data_dir=data_dir)
        return store.get_doc_for(class_type)
    except Exception:
        return None


def build_node_facts(core, class_type: str) -> Optional[NodeFacts]:
    schema = core._schemas.get(class_type)
    if schema is None:
        return None
    return NodeFacts(
        class_type=schema.class_type,
        display_name=schema.display_name,
        category=schema.category,
        python_module=schema.python_module,
        package=package_of(schema.python_module),
        role=classify_role(schema),
        inputs=tuple(list(schema.input_required) + list(schema.input_optional)),
        outputs=tuple(o for o in schema.output_types if isinstance(o, str)),
        safety=_safety_of(schema),
        best_claim_status=_best_status(core, class_type),
        claims=_claims_for(core, class_type),
        docs=_doc_for(core, class_type),
        templates_available=_templates_for(core, schema),
        in_workflow_registry=_in_registry(core, schema),
    )


# --------------------------------------------------------------------------- #
# public query functions (делегаты KnowledgeCore вызывает эти)
# --------------------------------------------------------------------------- #

def find_node(core, class_type: str) -> Optional[NodeFacts]:
    return build_node_facts(core, class_type)


def find_package(core, package_id: str) -> Optional[PackageFacts]:
    classes: list[str] = []
    modules: dict[str, str] = {}
    for name, schema in core._schemas.items():
        if package_of(schema.python_module) == package_id:
            classes.append(name)
            modules[name] = schema.python_module
    if not classes:
        return None
    from app.synthesis.safety import SafetyClass
    profiles = {_safety_of(core._schemas[c]) for c in classes}
    if SafetyClass.FORBIDDEN.value in profiles:
        profile = SafetyClass.FORBIDDEN.value
    elif profiles == {SafetyClass.ALLOWED.value}:
        profile = SafetyClass.ALLOWED.value
    else:
        profile = SafetyClass.REQUIRES_CONFIRMATION.value
    doc_cov = 0
    for c in classes:
        if _doc_for(core, c) is not None:
            doc_cov += 1
    first_module = next(iter(modules.values()))
    is_custom = not first_module.startswith(("nodes", "comfy_extras"))
    return PackageFacts(
        package_id=package_id,
        classes=tuple(sorted(classes)),
        is_custom=is_custom,
        api_family=is_api_family(first_module),
        safety_profile=profile,
        doc_coverage=doc_cov,
    )


def nodes_by_io(
    core,
    output_type: Optional[str] = None,
    required_inputs_contain: tuple[str, ...] = (),
    include_optional: bool = False,
) -> list[NodeFacts]:
    """Фильтр по существующим полям схем. OQ1: default только required-inputs."""
    results: list[NodeFacts] = []
    for class_type in core._schemas:
        facts = build_node_facts(core, class_type)
        if facts is None:
            continue
        if output_type is not None and output_type not in facts.outputs:
            continue
        if required_inputs_contain:
            if include_optional:
                input_types = {f.type for f in facts.inputs}
            else:
                input_types = {f.type for f in facts.inputs if f.required}
            if not set(required_inputs_contain) <= input_types:
                continue
        results.append(facts)
    return results


def gap_report(core, live_object_info: Optional[dict] = None) -> list[GapEntry]:
    """Derived on-demand реестр неизвестного (design §3.3). НЕ персистентный."""
    gaps: list[GapEntry] = []
    registry = getattr(core, "_workflow_registry", None)

    # (1) CANDIDATE_NO_WORKFLOW / реестр недоступен
    for class_type, cands in core._candidates.items():
        for cand in cands:
            if registry is None:
                gaps.append(GapEntry(
                    subject=class_type,
                    gap_type="workflow_registry_unavailable",
                    description=(
                        f"capability '{cand.capability}' не верифицируема: "
                        "workflow registry не подключён к KnowledgeCore (факт конфигурации)"
                    ),
                    priority="LOW",
                ))
                continue
            try:
                known = bool(registry.by_capability(cand.capability))
            except Exception:
                known = False
            if not known:
                from app.knowledge.gaps import GapType
                gaps.append(GapEntry(
                    subject=class_type,
                    gap_type=GapType.CANDIDATE_NO_WORKFLOW.value,
                    description=f"capability '{cand.capability}' не имеет зарегистрированного workflow",
                    priority="MEDIUM",
                ))

    # (2) candidate_no_template (строка описания; enum НЕ расширяется)
    for class_type, cands in core._candidates.items():
        schema = core._schemas.get(class_type)
        if schema is None:
            continue
        templates = _templates_for(core, schema)
        if cands and not templates:
            gaps.append(GapEntry(
                subject=class_type,
                gap_type="candidate_no_template",
                description="candidates есть, ни один S2 шаблон не подошёл (synthesis невозможен без нового template)",
                priority="MEDIUM",
            ))

    # (3) doc_gap для custom-пакетов
    packages: dict[str, list[str]] = {}
    for name, schema in core._schemas.items():
        pkg = package_of(schema.python_module)
        if pkg != "built-in":
            packages.setdefault(pkg, []).append(name)
    for pkg, classes in packages.items():
        if all(_doc_for(core, c) is None for c in classes):
            gaps.append(GapEntry(
                subject=pkg,
                gap_type="doc_gap",
                description=f"пакет '{pkg}' ({len(classes)} classes) не имеет ни одной NodeDoc-записи",
                priority="LOW",
            ))

    # (4) PERSISTENCE_HYGIENE — показывает, НЕ чистит (P1 contract §3.5)
    try:
        validated = core._claims_persistence.get_validated_nodes()
    except Exception:
        validated = {}
    for node_class in sorted(validated):
        if node_class not in core._schemas:
            gaps.append(GapEntry(
                subject=node_class,
                gap_type="PERSISTENCE_HYGIENE",
                description=(
                    "запись validated_nodes без схемы в snapshot — "
                    "возможен тестовый мусор (P1) или удалённый нод; "
                    "удаление — отдельное решение автора"
                ),
                priority="LOW",
            ))

    # (5) STALE_SNAPSHOT — только если вызывающий передал live info (S3 не ходит в сеть)
    if live_object_info is not None:
        from app.knowledge.gaps import GapType
        live_keys = set(live_object_info)
        snap_keys = set(core._schemas)
        for missing in sorted(live_keys - snap_keys):
            gaps.append(GapEntry(
                subject=missing,
                gap_type=GapType.STALE_KNOWLEDGE.value,
                description="есть в live /object_info, отсутствует в snapshot — нужен refresh",
                priority="MEDIUM",
            ))
        for stale in sorted(snap_keys - live_keys):
            gaps.append(GapEntry(
                subject=stale,
                gap_type=GapType.STALE_KNOWLEDGE.value,
                description="есть в snapshot, отсутствует в live — stale запись",
                priority="LOW",
            ))

    return gaps


def explain_node(core, class_type: str) -> Optional[NodeExplanation]:
    facts = build_node_facts(core, class_type)
    if facts is None:
        return None

    known: list[str] = []
    schema = core._schemas[class_type]
    known.append(f"schema: class_type='{facts.class_type}', module='{facts.python_module}', category='{facts.category}'")
    for f in schema.input_required:
        known.append(f"required input '{f.name}': type={f.type}, default={f.default!r}, options={list(f.options) if f.options else []}")
    for f in schema.input_optional:
        known.append(f"optional input '{f.name}': type={f.type}, default={f.default!r}")
    known.append(f"outputs: {list(facts.outputs)}")
    known.append(f"classification: role={facts.role}, safety={facts.safety} (детерминированные правила §3.2/s2 safety)")
    for c in facts.claims:
        known.append(f"claim: '{c.claim}' status={c.status.value}")
    if facts.docs is not None and getattr(facts.docs, "purpose", ""):
        known.append(f"NodeDoc purpose: {facts.docs.purpose}")
    try:
        validated_record = core._claims_persistence.get_validated_nodes().get(class_type)
    except Exception:
        validated_record = None
    if validated_record is True:
        known.append("ClaimsPersistence: validated=True запись существует (runtime-проверка выполнялась)")
    elif validated_record is False:
        known.append("ClaimsPersistence: validated=False запись существует (runtime-проверка НЕ подтверждена)")
    if facts.templates_available:
        known.append(f"S2 templates available: {list(facts.templates_available)}")
    if facts.in_workflow_registry:
        known.append("capability candidates ноды имеют зарегистрированные workflows")

    not_proven: list[str] = []
    if facts.best_claim_status != ClaimStatus.CONFIRMED.value:
        not_proven.append(f"нет CONFIRMED claim (текущий максимум={facts.best_claim_status}); работоспособность НЕ доказана")
    if facts.docs is None:
        not_proven.append("нет NodeDoc (документация/назначение не задокументированы)")
    if not facts.templates_available:
        not_proven.append("ни один S2 template не подобран — synthesis недоступен")
    if not facts.in_workflow_registry:
        not_proven.append("capability ноды не подтверждена существующими workflow-регистрациями")
    if validated_record is None:
        not_proven.append("нет записи runtime-валидации в ClaimsPersistence")
    if is_api_family(facts.python_module):
        not_proven.append("comfy_api_nodes.* — внешний API: тариф/квоты/наличие ключа НЕ моделируются на уровне ноды (AD-46); safety-граница = S2 REQUIRES_CONFIRMATION")

    hint = "template_available" if facts.templates_available else "no_template"
    prov = {
        "schema": "EvidenceTrustLevel.SCHEMA / EvidenceSource.RUNTIME (snapshot /object_info)",
        "classification": "derived deterministic rules (queries.classify_role, s2 classify_safety)",
        "claims": f"ClaimStatus projection (max={facts.best_claim_status})",
        "docs": "DECLARED_PURPOSE (NodeDoc)" if facts.docs is not None else "NONE",
        "validation": ("ClaimsPersistence record (OBSERVED_BEHAVIOR-уровень)") if validated_record is not None else "NONE",
        "cost": COST_NOT_APPLICABLE,
    }
    return NodeExplanation(
        facts=facts,
        what_is_known=tuple(known),
        what_is_not_proven=tuple(not_proven),
        template_hint=hint,
        provenance_sections=prov,
    )
