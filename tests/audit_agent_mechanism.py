"""
Debug audit: Agent Core + Knowledge Core cycle on real capabilities.

Проверяет полный цикл:
User Intent → Agent → Capability Discovery → Planner → Workflow selection → Execution

Ищет разрывы в механизме.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.agent import Agent
from app.assets.store import AssetStore
from app.knowledge.node_doc import NodeDocStore
from app.knowledge.core import KnowledgeCore
from app.comfy.client import ComfyClient
from app.planner.heuristic import HeuristicPlanner


def audit():
    """Полный аудит механизма."""
    
    print("=" * 60)
    print("AGENT CORE + KNOWLEDGE CORE AUDIT")
    print("=" * 60)
    
    # 1. Check what's available
    print("\n[1] DISCOVERY")
    client = ComfyClient(base_url="http://127.0.0.1:8188")
    oi = client.get_object_info()
    
    available_nodes = sorted(oi.keys())
    print(f"  Available nodes: {len(available_nodes)}")
    
    # Key nodes we care about
    key_nodes = ['PollinationsImageGen', 'AgnesImage', 'AgnesVideo', 
                 'OpenAICompatibleChat', 'Get Request Node']
    found_keys = [n for n in key_nodes if n in oi]
    print(f"  Key nodes found: {found_keys}")
    
    # 2. Check Agent capabilities
    print("\n[2] AGENT CAPABILITIES")
    store = AssetStore(root="tests/__audit__")
    agent = Agent(store)
    caps = agent.capabilities()
    print(f"  Capabilities: {caps}")
    
    # 3. Check workflows
    print("\n[3] WORKFLOWS")
    for wf in agent.registry.workflows:
        print(f"  {wf.id}: {wf.capability}")
    
    # 4. Check what documentation says
    print("\n[4] DOCUMENTED NODES (relevant)")
    docs = NodeDocStore()
    for doc in docs.get_all_docs():
        if any(k in doc.node_class for k in ['Pollinations', 'Agnes', 'OpenAI']):
            print(f"  {doc.node_class}: {doc.category} -> {doc.purpose[:50]}...")
    
    # 5. Test planner
    print("\n[5] PLANNER TESTS")
    planner = HeuristicPlanner()
    
    test_prompts = [
        "generate an image",
        "generate an image using pollinations",
        "create a video with agnes",
        "chat with openai",
    ]
    
    for prompt in test_prompts:
        result = planner.plan(prompt)
        print(f"  '{prompt}' -> {result.capability} ({result.rationale})")
    
    # 6. Check KnowledgeCore
    print("\n[6] KNOWLEDGE CORE")
    kc = KnowledgeCore()
    from app.knowledge.core import KnowledgeQuery
    
    # Query for image.generate
    query = KnowledgeQuery(
        required_operation="image.generate",
        required_media_input=(),
        required_media_output="image",
    )
    response = kc.query(query)
    print(f"  Query image.generate:")
    print(f"    known_capabilities: {response.known_capabilities}")
    print(f"    candidate_nodes: {[c.node_class for c in response.candidate_nodes]}")
    print(f"    readiness: {response.readiness.value}")
    print(f"    gaps: {[g.gap_type.value for g in response.gaps]}")
    
    # 7. Check what the agent would actually do
    print("\n[7] AGENT BEHAVIOR")
    # Try to find what workflow would be selected for image.generate
    manifests = agent.registry.by_capability("image.generate")
    print(f"  Workflows for image.generate: {[m.id for m in manifests]}")
    
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    audit()
