"""S3 Forensic Audit probe — READ-ONLY.

Собирает фактическое состояние экосистемы: live /object_info, packages,
snapshot vs live diff, representative nodes, NodeDoc coverage, provenance
словарь, safety-классификация. Никаких изменений состояния.
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.comfy.client import ComfyClient
from app.knowledge.node_schema import NodeSchemaStore, node_schema_from_object_info
from app.synthesis.safety import classify_safety

client = ComfyClient()
info = client.get_object_info()

print('=== 1. LIVE /object_info ===')
print('total node classes:', len(info))

custom, builtin = {}, {}
for name, data in info.items():
    if not isinstance(data, dict):
        continue
    mod = data.get('python_module', '')
    if mod.startswith('nodes') or mod.startswith('comfy_extras'):
        builtin[name] = mod
    else:
        pkg = mod.replace('custom_nodes.', '')
        custom.setdefault(pkg, []).append(name)
print('built-in classes:', len(builtin), '| custom classes:', len(custom))
print()
print('=== 2. CUSTOM PACKAGES (live, отсортировано) ===')
for pkg, classes in sorted(custom.items(), key=lambda kv: -len(kv[1])):
    head = ', '.join(sorted(classes)[:4])
    more = '...' if len(classes) > 4 else ''
    print(f'  {pkg}: {len(classes)} [{head}{more}]')

print()
print('=== 3. PERSISTED SNAPSHOT vs LIVE ===')
store = NodeSchemaStore()
snap = store.load_current()
print('snapshot schemas:', len(snap))
missing = sorted(n for n in info if n not in snap)
extra = sorted(n for n in snap if n not in info)
print('live NOT in snapshot:', len(missing), missing[:8])
print('snapshot NOT in live (stale):', len(extra), extra[:8])

print()
print('=== 4. REPRESENTATIVE NODES (live schema → provenance/safety) ===')
REPS = ['ImageInvert', 'CheckpointLoaderSimple', 'PollinationsImageGen', 'KSampler']
# добавим AgnesVideo если live
for n in info:
    if n.lower().startswith('agnes'):
        REPS.append(n)
for name in REPS:
    data = info.get(name)
    if data is None:
        print(f'--- {name}: НЕ В LIVE (GAP)')
        continue
    s = node_schema_from_object_info(name, data)
    req = [(f.name, f.type) for f in s.input_required]
    opt = [(f.name, f.type) for f in s.input_optional][:6]
    safety = classify_safety(s.python_module, s.category, name)
    in_snap = 'snapshot+live' if name in snap else 'live-only'
    print(f'--- {name} [{in_snap}]')
    print(f'    module={s.python_module} category={s.category}')
    print(f'    required={req}')
    print(f'    optional={opt}')
    print(f'    outputs={s.output_types}')
    print(f'    safety={safety.value}')

print()
print('=== 5. NODE-DOC COVERAGE (NodeDocStore) ===')
try:
    from app.knowledge.node_doc import NodeDocStore
    nds = NodeDocStore()
    docs = getattr(nds, '_docs', {})
    if not docs:
        docs_path = 'docs/node_docs'
        files = [f for f in os.listdir(docs_path) if f.endswith('.md')] if os.path.isdir(docs_path) else []
        print('    md files in docs/node_docs:', len(files))
    else:
        print('    NodeDocStore entries:', len(docs))
except Exception as e:
    print('    NodeDocStore error:', e)

print()
print('=== 6. PROVENANCE VOCABULARY (существующий) ===')
from app.knowledge.models import EvidenceTrustLevel, EvidenceSource, ClaimStatus
print('EvidenceTrustLevel:', [e.name for e in EvidenceTrustLevel])
print('EvidenceSource:', [e.name for e in EvidenceSource])
print('ClaimStatus:', [e.name for e in ClaimStatus])

print()
print('=== 7. CLAIMS/VALIDATION PERSISTENCE ===')
from app.knowledge.claims_persistence import ClaimsPersistence
cp = ClaimsPersistence()
vn = cp.get_validated_nodes()
cc = cp.get_confirmed_claims()
print('validated_nodes persisted:', len(vn), list(vn.items())[:5])
print('confirmed_claims persisted:', len(cc))
