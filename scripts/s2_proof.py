"""S2 Real ComfyUI Synthesis Proof — READ-ONLY execution check.

ImageInvert (built-in, ALLOWED safety) → s2_image_to_image template →
synthesize → register → run() → real ComfyUI execution → output Asset.

Uses only EXISTING infrastructure (Agent.run → engine.execute).
"""
import sys, io, json, os, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 1. NodeSchema from LIVE ComfyUI
from app.comfy.client import ComfyClient
from app.knowledge.node_schema import node_schema_from_object_info
from app.knowledge.candidates import CapabilityCandidate, UsageHypothesis
from app.knowledge.models import ClaimStatus
from app.synthesis.selector import select_template
from app.synthesis.builder import synthesize_workflow
from app.synthesis.safety import classify_safety

client = ComfyClient()
obj_info = client.get_object_info()
schema = node_schema_from_object_info('ImageInvert', obj_info['ImageInvert'])
print(f'[1] NodeSchema: {schema.class_type} out={schema.output_types} module={schema.python_module}')

# 2. Candidate
candidate = CapabilityCandidate(
    node_class='ImageInvert',
    capability='image.edit',
    status=ClaimStatus.INFERENCE,
    usage=UsageHypothesis(description='invert image colors'),
)

# 3. Template + safety
tmpl = select_template(candidate, schema)
assert tmpl is not None, 'template must match'
safety = classify_safety(schema.python_module, schema.category, 'ImageInvert')
print(f'[2] Template: {tmpl.template_id} | Safety: {safety.value}')

# 4. Synthesize
result = synthesize_workflow(candidate, schema, tmpl, safety)
print(f'[3] Synthesized: manifest.id={result.manifest["id"]} source={result.manifest["source"]}')
print(f'    workflow nodes: {[ (nid, nd["class_type"]) for nid, nd in result.workflow.items() ]}')

# 5. Materialize as real workflow dir + register in Agent's registry
tmpdir = tempfile.mkdtemp(prefix='s2_proof_')
wdir = os.path.join(tmpdir, 's2_ImageInvert')
os.makedirs(wdir)
with open(os.path.join(wdir, 'manifest.json'), 'w') as f:
    json.dump(result.manifest, f)
with open(os.path.join(wdir, 'workflow.json'), 'w') as f:
    json.dump(result.workflow, f)

# 6. Full production path: Agent with synthesized workflows dir + REAL provider
from app.assets.store import AssetStore
from app.agent import Agent

store = AssetStore(root=os.path.join(tmpdir, 'assets'))
agent = Agent(store, workflows_dir=os.path.join(tmpdir, '__workflows__'))
# register synthesized workflow into agent's registry
os.makedirs(agent.registry._workflows_dir if hasattr(agent.registry, '_workflows_dir') else tmpdir, exist_ok=True)
# discover from temp dir containing ONLY our synthesized workflow
parent = os.path.join(tmpdir, 'wf_root')
os.makedirs(parent, exist_ok=True)
import shutil
shutil.copytree(wdir, os.path.join(parent, 's2_ImageInvert'))
agent2 = Agent(store, workflows_dir=parent)
caps = sorted({w.capability for w in agent2.registry.workflows})
print(f'[4] Registry capabilities: {caps}')
synth = [w for w in agent2.registry.workflows if w.id.startswith('s2_')]
print(f'    synthesized workflows registered: {[(w.id, w.status.value) for w in synth]}')

# 7. REAL execution via existing Agent.run path (engine.execute, no new mechanisms)
import glob
input_dir = r'C:\Users\1\AppData\Local\Comfy-Desktop\ComfyUI-Shared\input'
images = sorted(glob.glob(os.path.join(input_dir, '*.png')))
assert images, 'need an input image'
test_image = images[0]
print(f'[5] Executing REAL run() with input={os.path.basename(test_image)} ...')

job = agent2.run('image.edit', params={}, asset_paths={'image': test_image},
                 base_url='http://127.0.0.1:8188', ws_timeout=120)
print(f'    Job.state={job.state.value}')
print(f'    Job.workflow_id={job.workflow_id}')
print(f'    Job.error={job.error}')
if job.output_assets:
    asset = store.get(job.output_assets[0])
    if asset:
        size = os.path.getsize(asset.path)
        print(f'    OUTPUT ASSET: id={asset.id} type={asset.type} size={size} path={asset.path}')
        print(f'    lineage: {store.lineage(asset.id)}')
        ok = size > 100
        print(f'\n=== RESULT: {"SUCCESS — REAL ComfyUI executed synthesized workflow" if ok and job.state.value == "SUCCESS" else "FAILED"} ===')
    else:
        print('    output asset not in store')
else:
    print('\n=== RESULT: no output assets — see job error above ===')

# cleanup proof dir
shutil.rmtree(tmpdir, ignore_errors=True)
