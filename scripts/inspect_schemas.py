import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
with open('app/data/knowledge/node_schemas.json', 'r', encoding='utf-8') as f:
    schemas = json.load(f)

targets = ['AgnesVideo', 'ImageScale', 'SaveImage', 'PollinationsImageGen', 'LoadImage', 'CheckpointLoaderSimple']
for t in targets:
    if t in schemas:
        s = schemas[t]
        print(f'=== {t} ===')
        print(f'  category: {s.get("category")}')
        print(f'  display_name: {s.get("display_name")}')
        print(f'  python_module: {s.get("python_module")}')
        req = s.get('input_required', [])
        opt = s.get('input_optional', [])
        print(f'  input_required ({len(req)}):')
        for inp in req[:6]:
            print(f'    {inp["name"]}: type={inp["type"]}, required={inp["required"]}, default={inp.get("default")}, options={inp.get("options",[])}')
        if len(req) > 6: print(f'    ... and {len(req)-6} more')
        print(f'  input_optional ({len(opt)}):')
        for inp in opt[:4]:
            print(f'    {inp["name"]}: type={inp["type"]}, default={inp.get("default")}')
        if len(opt) > 4: print(f'    ... and {len(opt)-4} more')
        print(f'  output_types: {s.get("output_types")}')
        print(f'  output_names: {s.get("output_names")}')
        print()
    else:
        print(f'=== {t} === NOT FOUND')
        print()

# Also find nodes with model-related inputs
print('=== Nodes with "ckpt_name" or "model" required input ===')
count = 0
for name, s in schemas.items():
    for inp in s.get('input_required', []):
        if inp['name'] in ('ckpt_name', 'model', 'lora_name', 'vae_name'):
            print(f'  {name}: {inp["name"]} type={inp["type"]} options_count={len(inp.get("options",[]))}')
            count += 1
            if count >= 10:
                break
    if count >= 10:
        break
