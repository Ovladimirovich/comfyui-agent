"""S3 tests — Ecosystem Facts & Provenance Queries (queries.py + KnowledgeCore facade).

Покрытие матрицы design §9 (Q1..Q16) + negative cases + отсутствие invented
semantics + P1 contract (no writes, тесты только в tmp_path).
"""
import json
import os
import pytest
from dataclasses import dataclass

from app.knowledge.core import KnowledgeCore, KnowledgeQuery, Readiness
from app.knowledge.models import ClaimStatus, KnowledgeClaim
from app.knowledge.node_schema import FieldSpec, NodeSchema
from app.knowledge import queries
from app.knowledge.candidates import CapabilityCandidate, UsageHypothesis
from app.knowledge.gaps import GapType


# ------------------------------------------------------------------ #
# helpers
# ------------------------------------------------------------------ #

def _schema(class_type, required=(), optional=(), outputs=("IMAGE",),
            module="nodes", category="image"):
    return NodeSchema(
        class_type=class_type,
        display_name=class_type,
        category=category,
        input_required=tuple(required),
        input_optional=tuple(optional),
        output_types=outputs,
        output_names=tuple(),
        python_module=module,
        discovered_at=0.0,
    )


def _fs(name, ftype, required=True, default=None, options=()):
    return FieldSpec(name=name, type=ftype, required=required,
                     default=default, options=tuple(options))


def _candidate(node_class, capability):
    return CapabilityCandidate(
        node_class=node_class,
        capability=capability,
        status=ClaimStatus.INFERENCE,
        usage=UsageHypothesis(description="test"),
    )


@pytest.fixture
def core(tmp_path):
    """Свежий KnowledgeCore в tmp_path (P1 contract: НИКОГДА production-dir)."""
    return KnowledgeCore(data_dir=str(tmp_path))


@pytest.fixture
def populated(core):
    core._schemas = {
        "ImageInvert": _schema("ImageInvert", required=[_fs("image", "IMAGE")],
                               outputs=("IMAGE",), module="nodes", category="image/color"),
        "CheckpointLoaderSimple": _schema(
            "CheckpointLoaderSimple",
            required=[_fs("ckpt_name", "ENUM", options=("a.safetensors",))],
            outputs=("MODEL", "CLIP", "VAE"), module="nodes", category="model/loaders"),
        "KSampler": _schema(
            "KSampler",
            required=[_fs("model", "MODEL"), _fs("seed", "INT"), _fs("steps", "INT"),
                      _fs("cfg", "FLOAT"), _fs("positive", "CONDITIONING"),
                      _fs("negative", "CONDITIONING"), _fs("latent_image", "LATENT"),
                      _fs("denoise", "FLOAT")],
            outputs=("LATENT",), module="nodes", category="model/sampling"),
        "SaveImage": _schema("SaveImage",
                             required=[_fs("images", "IMAGE"), _fs("filename_prefix", "STRING")],
                             outputs=("IMAGE",), module="nodes", category="image"),
        "MyVideoHead": _schema(
            "MyVideoHead",
            required=[_fs("prompt", "STRING"), _fs("fps", "INT")],
            outputs=("VIDEO",), module="custom_nodes.myvideo", category="video"),
        "OpenAIDalle3": _schema(
            "OpenAIDalle3",
            required=[_fs("prompt", "STRING")],
            outputs=("IMAGE",), module="comfy_api_nodes.nodes_openai", category="api/OpenAI"),
        "OrphanNode": _schema(
            "OrphanNode",
            required=[_fs("video", "VIDEO"), _fs("audio", "AUDIO")],
            outputs=("STRING", "LATENT"), module="custom_nodes.orphan", category="misc"),
    }
    core._candidates = {
        "MyVideoHead": [_candidate("MyVideoHead", "video.generate")],
        "OrphanNode": [_candidate("OrphanNode", "lip_sync.video")],
    }
    core._claims = [
        KnowledgeClaim(claim="MyVideoHead implements video.generate",
                       subject="MyVideoHead", predicate="implements",
                       object="video.generate", status=ClaimStatus.INFERENCE),
    ]
    return core


# ------------------------------------------------------------------ #
# Q1-Q2: find_node
# ------------------------------------------------------------------ #

class TestFindNode:
    def test_basic_facts(self, populated):
        facts = populated.find_node("ImageInvert")
        assert facts is not None
        assert facts.role == "processor"
        assert facts.safety == "ALLOWED"          # built-in nodes
        assert facts.package == "built-in"
        assert facts.best_claim_status == "UNKNOWN"
        assert facts.templates_available == ()
        # никаких домыслов: cost — константный маркер AD-46
        assert "AD-46" in facts.cost
        assert "per-node cost" in facts.cost

    def test_unknown_returns_none(self, populated):
        assert populated.find_node("NoSuchNode") is None

    def test_no_invented_semantics(self, populated):
        """Только факты схемы; семантика не выдумывается."""
        facts = populated.find_node("SaveImage")
        d = facts.to_dict()
        assert d["docs"] is None                   # нет NodeDoc — не изобретена
        assert d["claims"] == []                   # нет claims — не изобретены
        assert d["best_claim_status"] == "UNKNOWN"
        assert d["role"] == "sink"                 # правило, не угадывание

    def test_api_family_is_path_fact_not_cost(self, populated):
        facts = populated.find_node("OpenAIDalle3")
        assert facts is not None
        assert facts.cost == queries.COST_NOT_APPLICABLE
        pkg = populated.find_package("comfy_api_nodes.nodes_openai")
        assert pkg.api_family is True              # факт пути модуля
        assert pkg.package_id == "comfy_api_nodes.nodes_openai"


# ------------------------------------------------------------------ #
# Q3-Q4: find_package
# ------------------------------------------------------------------ #

class TestFindPackage:
    def test_custom_package(self, populated):
        pkg = populated.find_package("myvideo")
        assert pkg is not None
        assert pkg.classes == ("MyVideoHead",)
        assert pkg.is_custom is True
        assert pkg.api_family is False
        assert pkg.safety_profile == "REQUIRES_CONFIRMATION"
        assert pkg.provenance == "derived:live-or-snapshot /object_info"

    def test_unknown_package_none(self, populated):
        assert populated.find_package("no-such-package") is None

    def test_doc_coverage_zero_without_docs(self, populated):
        pkg = populated.find_package("myvideo")
        assert pkg.doc_coverage == 0               # не выдумана документация


# ------------------------------------------------------------------ #
# Q5/Q5b: nodes_by_io + capability relation
# ------------------------------------------------------------------ #

class TestNodesByIo:
    def test_output_filter_includes_head_excludes_fragment(self, populated):
        vids = populated.nodes_by_io(output_type="VIDEO")
        names = {f.class_type for f in vids}
        assert "MyVideoHead" in names
        assert "KSampler" not in names             # LATENT output

    def test_required_contains(self, populated):
        img_in = populated.nodes_by_io(required_inputs_contain=("IMAGE",))
        names = {f.class_type for f in img_in}
        assert "ImageInvert" in names
        assert "MyVideoHead" not in names

    def test_optional_excluded_by_default_oq1(self, populated):
        # узел с optional IMAGE не проходит required-фильтр по умолчанию
        populated._schemas["HeadWithOptImg"] = _schema(
            "HeadWithOptImg",
            required=[_fs("prompt", "STRING")],
            optional=[_fs("image", "IMAGE", required=False)],
            outputs=("IMAGE",),
        )
        assert "HeadWithOptImg" not in {f.class_type for f in
                                        populated.nodes_by_io(required_inputs_contain=("IMAGE",))}
        assert "HeadWithOptImg" in {f.class_type for f in
                                    populated.nodes_by_io(required_inputs_contain=("IMAGE",),
                                                          include_optional=True)}

    def test_capability_relation_via_fields(self, populated):
        """capability-связь подаётся фактами (OQ4 не реализован)."""
        f = populated.find_node("MyVideoHead")
        # head-нода video.generate → S2 template подбирается (факт через чистый select_template)
        assert "s2_text_to_video" in f.templates_available
        assert isinstance(f.in_workflow_registry, bool)   # registry None → False (факт конфигурации)
        assert not hasattr(populated, "nodes_for_capability")  # OQ4 вне scope


# ------------------------------------------------------------------ #
# Q6: classification rules §3.2
# ------------------------------------------------------------------ #

class TestClassification:
    @pytest.mark.parametrize("cls,expected", [
        ("ImageInvert", "processor"),
        ("CheckpointLoaderSimple", "loader"),
        ("KSampler", "fragment"),
        ("SaveImage", "sink"),
        ("MyVideoHead", "head"),
    ])
    def test_roles(self, populated, cls, expected):
        assert populated.find_node(cls).role == expected


# ------------------------------------------------------------------ #
# Q7 + explain
# ------------------------------------------------------------------ #

class TestExplain:
    def test_explain_unknown_none(self, populated):
        assert populated.explain_node("Nope") is None

    def test_explain_has_honest_not_proven(self, populated):
        e = populated.explain_node("MyVideoHead")
        assert e is not None
        joined = "\n".join(e.what_is_not_proven)
        assert "CONFIRMED" in joined               # работоспособность НЕ доказана
        assert "NodeDoc" in joined or "NodeDoc" in " ".join(e.what_is_not_proven)
        # known — только факты схемы/claims, без выдуманной семантики
        for line in e.what_is_known:
            assert "вероятно" not in line.lower()
            assert "наверное" not in line.lower()
        assert e.provenance_sections["schema"].startswith("EvidenceTrustLevel.SCHEMA")
        assert "AD-46" in e.provenance_sections["cost"]

    def test_explain_api_not_proven_lists_cost_boundary(self, populated):
        e = populated.explain_node("OpenAIDalle3")
        assert any("comfy_api_nodes" in s and "НЕ моделируются" in s
                   for s in e.what_is_not_proven)

    def test_explain_claim_projection(self, populated):
        e = populated.explain_node("MyVideoHead")
        assert any("status=INFERENCE" in s for s in e.what_is_known)
        assert e.facts.best_claim_status == "INFERENCE"


# ------------------------------------------------------------------ #
# Q8-Q10: gap_report (derived, non-persistent)
# ------------------------------------------------------------------ #

class TestGapReport:
    def test_candidate_no_template(self, populated):
        gaps = populated.gap_report()
        g = [x for x in gaps if x.subject == "OrphanNode" and x.gap_type == "candidate_no_template"]
        assert g, "для кандидата без шаблона обязан быть gap"

    def test_workflow_registry_unavailable_factual(self, populated):
        # registry не подключён → честный gap о конфигурации (не выдумка про workflow)
        gaps = populated.gap_report()
        assert any(x.gap_type == "workflow_registry_unavailable" for x in gaps)

    def test_doc_gap_for_custom_package(self, populated):
        gaps = populated.gap_report()
        assert any(x.subject == "myvideo" and x.gap_type == "doc_gap" for x in gaps)

    def test_persistence_hygiene_shown_not_cleaned(self, populated, tmp_path):
        # внедрим «мусорную» запись validated (tmp-дир, НЕ production)
        populated._claims_persistence.add_validated_node("GhostTestNode", False)
        gaps = populated.gap_report()
        hy = [x for x in gaps if x.gap_type == "PERSISTENCE_HYGIENE"
              and x.subject == "GhostTestNode"]
        assert hy, "gap_report обязан показать запись без схемы"
        # НЕ чистит:
        assert populated._claims_persistence.get_validated_nodes().get("GhostTestNode") is False
        # enum GapType НЕ расширен строками отчёта:
        assert "PERSISTENCE_HYGIENE" not in [g.value for g in GapType]

    def test_stale_snapshot_only_with_live_info(self, populated):
        assert not any(x.gap_type == GapType.STALE_KNOWLEDGE.value for x in populated.gap_report())
        live = {"ImageInvert": {}, "BrandNewNode": {}}
        gaps = populated.gap_report(live_object_info=live)
        assert any(x.subject == "BrandNewNode" for x in gaps)   # added
        assert any(x.subject == "KSampler" for x in gaps)       # removed/stale

    def test_gap_report_is_not_persisted(self, populated, tmp_path):
        populated.gap_report()
        files = set(os.listdir(tmp_path))
        assert all("gap" not in f.lower() for f in files)


# ------------------------------------------------------------------ #
# Q11-Q14: инварианты
# ------------------------------------------------------------------ #

class TestInvariants:
    def _dir_state(self, d):
        out = {}
        for root, _dirs, files in os.walk(d):
            for f in files:
                p = os.path.join(root, f)
                st = os.stat(p)
                out[p] = (st.st_size, st.st_mtime_ns)
        return out

    def test_no_side_effects(self, populated, tmp_path):
        before = self._dir_state(tmp_path)
        populated.find_node("ImageInvert")
        populated.find_package("myvideo")
        populated.nodes_by_io(output_type="IMAGE")
        populated.explain_node("MyVideoHead")
        populated.gap_report()
        after = self._dir_state(tmp_path)
        assert before == after                     # ни одна операция не записывает

    def test_readiness_unchanged(self, populated):
        q = KnowledgeQuery(required_operation="video.generate",
                           required_media_input=(), required_media_output="video")
        r1 = populated.query(q).readiness
        populated.find_node("MyVideoHead")
        populated.explain_node("MyVideoHead")
        populated.gap_report()
        r2 = populated.query(q).readiness
        assert r1 == r2                            # queries не двигают readiness

    def test_user_confirmed_absent(self, populated):
        assert "USER_CONFIRMED" not in ClaimStatus.__members__
        e = populated.explain_node("MyVideoHead")
        blob = e.to_dict()
        assert "USER_CONFIRMED" not in json.dumps(blob, default=str)

    def test_registry_and_enums_untouched(self, populated):
        assert len(list(GapType)) == 7             # enum не расширялся в S3
        assert len(list(ClaimStatus)) == 4


# ------------------------------------------------------------------ #
# Q15-Q16: совместимость S2/S1 + facade
# ------------------------------------------------------------------ #

class TestCompat:
    def test_facade_all_five(self, populated):
        for m in ("find_node", "find_package", "nodes_by_io", "explain_node", "gap_report"):
            assert callable(getattr(populated, m))

    def test_s2_selector_pure_reuse(self, populated):
        """explain использует S2 select_template без мутаций."""
        f_before = populated.find_node("MyVideoHead").templates_available
        f_after = populated.find_node("MyVideoHead").templates_available
        assert f_before == f_after

    def test_gap_report_does_not_call_synthesize(self, populated, monkeypatch):
        called = {"n": 0}
        orig = populated.synthesize_candidates
        def spy(*a, **k):
            called["n"] += 1
            return orig(*a, **k)
        populated.synthesize_candidates = spy
        populated.gap_report()
        assert called["n"] == 0                    # gap_report НЕ синтезирует
