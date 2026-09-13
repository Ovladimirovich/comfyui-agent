"""
Tests for NodeDocEntry + NodeDocStore + NodeDocParser.
"""

import json
import os
import tempfile
import time

import pytest

from app.knowledge.node_doc import NodeDocEntry, NodeDocStore
from app.knowledge.node_doc_parser import NodeDocParser, format_node_explanation


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def sample_markdown():
    return """## Get Request Node
- **Category:** RequestNode/Get Request
- **Purpose:** HTTP GET запрос
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes
- **Related:** Post Request Node, Rest Api Node

**Inputs:**
- `target_url` (STRING, required): URL для запроса
- `headers` (KEY_VALUE, optional): Заголовки HTTP

**Outputs:**
- `text` (STRING): Ответ как текст
- `json` (JSON): Ответ как JSON

**Configuration:**
- proxy: Не используется
- timeout: System default

**Example:**
```json
{"target_url": "https://api.example.com"}
```
"""


@pytest.fixture
def sample_markdown_multi():
    return """## Get Request Node
- **Category:** RequestNode/Get Request
- **Purpose:** HTTP GET запрос
- **Module:** custom_nodes.ComfyUI-HttpRequestNodes

**Inputs:**
- `target_url` (STRING, required): URL

**Outputs:**
- `text` (STRING): Ответ

## Post Request Node
- **Category:** RequestNode/Post Request
- **Purpose:** HTTP POST запрос

**Inputs:**
- `target_url` (STRING, required): URL
- `body` (STRING, optional): Тело

**Outputs:**
- `text` (STRING): Ответ
"""


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def store(temp_data_dir):
    return NodeDocStore(data_dir=temp_data_dir)


@pytest.fixture
def parser():
    return NodeDocParser()


# ------------------------------------------------------------------
# NodeDocEntry
# ------------------------------------------------------------------


class TestNodeDocEntry:
    def test_create_entry(self):
        entry = NodeDocEntry(
            node_class="Get Request Node",
            display_name="Get Request Node",
            category="RequestNode/Get Request",
            purpose="HTTP GET запрос",
            python_module="custom_nodes.ComfyUI-HttpRequestNodes",
        )
        assert entry.node_class == "Get Request Node"
        assert entry.category == "RequestNode/Get Request"
        assert entry.inputs_documented == {}
        assert entry.outputs_documented == {}
        assert entry.version == "1.0"

    def test_frozen(self):
        entry = NodeDocEntry(
            node_class="Test",
            display_name="Test",
            category="test",
            purpose="test",
            python_module="test",
        )
        with pytest.raises(AttributeError):
            entry.node_class = "Changed"

    def test_defaults(self):
        entry = NodeDocEntry(
            node_class="X",
            display_name="X",
            category="",
            purpose="",
            python_module="",
        )
        assert entry.examples == []
        assert entry.related_nodes == []
        assert entry.ingested_at > 0


# ------------------------------------------------------------------
# NodeDocParser
# ------------------------------------------------------------------


class TestNodeDocParser:
    def test_parse_single_node(self, parser, sample_markdown):
        entries = parser.parse_text(sample_markdown)
        assert len(entries) == 1

        doc = entries[0]
        assert doc.node_class == "Get Request Node"
        assert doc.category == "RequestNode/Get Request"
        assert doc.purpose == "HTTP GET запрос"
        assert doc.python_module == "custom_nodes.ComfyUI-HttpRequestNodes"

    def test_parse_inputs(self, parser, sample_markdown):
        entries = parser.parse_text(sample_markdown)
        doc = entries[0]

        assert "target_url" in doc.inputs_documented
        assert doc.inputs_documented["target_url"]["type"] == "STRING"
        assert doc.inputs_documented["target_url"]["required"] is True
        assert doc.inputs_documented["target_url"]["description"] == "URL для запроса"

        assert "headers" in doc.inputs_documented
        assert doc.inputs_documented["headers"]["required"] is False

    def test_parse_outputs(self, parser, sample_markdown):
        entries = parser.parse_text(sample_markdown)
        doc = entries[0]

        assert "text" in doc.outputs_documented
        assert doc.outputs_documented["text"]["type"] == "STRING"
        assert "json" in doc.outputs_documented

    def test_parse_configuration(self, parser, sample_markdown):
        entries = parser.parse_text(sample_markdown)
        doc = entries[0]

        assert "proxy" in doc.configuration
        assert "timeout" in doc.configuration

    def test_parse_related(self, parser, sample_markdown):
        entries = parser.parse_text(sample_markdown)
        doc = entries[0]

        assert "Post Request Node" in doc.related_nodes
        assert "Rest Api Node" in doc.related_nodes

    def test_parse_multi_node(self, parser, sample_markdown_multi):
        entries = parser.parse_text(sample_markdown_multi)
        assert len(entries) == 2
        assert entries[0].node_class == "Get Request Node"
        assert entries[1].node_class == "Post Request Node"

    def test_parse_empty(self, parser):
        entries = parser.parse_text("")
        assert entries == []

    def test_parse_no_metadata(self, parser):
        text = """## Some Node
Just some text without metadata.
"""
        entries = parser.parse_text(text)
        assert len(entries) == 1
        assert entries[0].node_class == "Some Node"
        assert entries[0].category == ""


# ------------------------------------------------------------------
# NodeDocStore
# ------------------------------------------------------------------


class TestNodeDocStore:
    def test_empty_store(self, store):
        assert store.count() == 0
        assert store.get_all_docs() == []

    def test_ingest_from_text(self, store, sample_markdown):
        entries = store.ingest_from_text(sample_markdown)
        assert len(entries) == 1
        assert store.count() == 1

    def test_get_doc_for(self, store, sample_markdown):
        store.ingest_from_text(sample_markdown)
        doc = store.get_doc_for("Get Request Node")
        assert doc is not None
        assert doc.purpose == "HTTP GET запрос"

    def test_get_doc_for_missing(self, store):
        assert store.get_doc_for("Nonexistent") is None

    def test_upsert(self, store):
        entry = NodeDocEntry(
            node_class="Test Node",
            display_name="Test Node",
            category="test",
            purpose="test purpose",
            python_module="test",
        )
        store.upsert(entry)
        assert store.count() == 1
        assert store.get_doc_for("Test Node").purpose == "test purpose"

    def test_upsert_updates(self, store):
        entry1 = NodeDocEntry(
            node_class="Test", display_name="Test", category="", purpose="v1", python_module=""
        )
        entry2 = NodeDocEntry(
            node_class="Test", display_name="Test", category="", purpose="v2", python_module=""
        )
        store.upsert(entry1)
        store.upsert(entry2)
        assert store.count() == 1
        assert store.get_doc_for("Test").purpose == "v2"

    def test_search(self, store, sample_markdown):
        store.ingest_from_text(sample_markdown)
        results = store.search("GET")
        assert len(results) == 1

    def test_search_by_input(self, store, sample_markdown):
        store.ingest_from_text(sample_markdown)
        results = store.search("URL")
        assert len(results) == 1

    def test_search_no_results(self, store, sample_markdown):
        store.ingest_from_text(sample_markdown)
        results = store.search("nonexistent")
        assert len(results) == 0

    def test_get_docs_by_category(self, store, sample_markdown_multi):
        store.ingest_from_text(sample_markdown_multi)
        get_nodes = store.get_docs_by_category("Get Request")
        assert len(get_nodes) == 1
        assert get_nodes[0].node_class == "Get Request Node"

    def test_list_categories(self, store, sample_markdown_multi):
        store.ingest_from_text(sample_markdown_multi)
        cats = store.list_categories()
        assert "RequestNode/Get Request" in cats
        assert "RequestNode/Post Request" in cats

    def test_persistence(self, temp_data_dir, sample_markdown):
        store1 = NodeDocStore(data_dir=temp_data_dir)
        store1.ingest_from_text(sample_markdown)
        assert store1.count() == 1

        store2 = NodeDocStore(data_dir=temp_data_dir)
        assert store2.count() == 1
        assert store2.get_doc_for("Get Request Node") is not None

    def test_ingest_from_file(self, store, sample_markdown, temp_data_dir):
        path = os.path.join(temp_data_dir, "test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(sample_markdown)

        count = store.ingest_from_file(path)
        assert count == 1
        assert store.count() == 1

    def test_ingest_multi_from_text(self, store, sample_markdown_multi):
        entries = store.ingest_from_text(sample_markdown_multi)
        assert len(entries) == 2
        assert store.count() == 2


# ------------------------------------------------------------------
# format_node_explanation
# ------------------------------------------------------------------


class TestFormatNodeExplanation:
    def test_basic_format(self):
        doc = NodeDocEntry(
            node_class="Get Request Node",
            display_name="Get Request Node",
            category="RequestNode/Get Request",
            purpose="HTTP GET запрос",
            python_module="custom_nodes.ComfyUI-HttpRequestNodes",
            inputs_documented={
                "target_url": {
                    "type": "STRING",
                    "required": True,
                    "description": "URL для запроса",
                }
            },
            outputs_documented={
                "text": {"type": "STRING", "description": "Ответ как текст"}
            },
        )
        result = format_node_explanation(doc)
        assert "Get Request Node" in result
        assert "HTTP GET запрос" in result
        assert "target_url" in result
        assert "STRING" in result

    def test_empty_doc(self):
        doc = NodeDocEntry(
            node_class="Empty",
            display_name="Empty",
            category="",
            purpose="",
            python_module="",
        )
        result = format_node_explanation(doc)
        assert "Empty" in result
