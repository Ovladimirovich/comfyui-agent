"""3-turn UI test with different resolutions (10 steps for speed)."""
import httpx
import json
import threading
import time
import sys

UI = "http://127.0.0.1:8189"
COMFY = "http://127.0.0.1:8188"
TURN_TIMEOUT = 120


def listen_sse(ui_url, session_id, events, done_event):
    try:
        url = f"{ui_url}/events?session_id={session_id}"
        with httpx.Client(timeout=TURN_TIMEOUT) as c:
            with c.stream("GET", url) as r:
                for line in r.iter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data = json.loads(line.split(":", 1)[1].strip())
                        events.append(data)
                        if data.get("type") in ("result", "error"):
                            done_event.set()
                            return
    except Exception as e:
        events.append({"type": "sse_error", "error": str(e)})
        done_event.set()


def run_turn(session_id, request):
    events = []
    done = threading.Event()
    t = threading.Thread(target=listen_sse, args=(UI, session_id, events, done), daemon=True)
    t.start()
    time.sleep(0.3)

    c = httpx.Client(timeout=TURN_TIMEOUT)
    r = c.post(f"{UI}/turn", json={"session_id": session_id, "request": request})
    if r.status_code != 200:
        return {"error": f"POST failed: {r.status_code}"}

    done.wait(timeout=TURN_TIMEOUT)
    return events


def main():
    c = httpx.Client(timeout=10)
    try:
        r = c.get(f"{COMFY}/system_stats")
        stats = r.json()
        argv = stats['system']['argv']
        print(f"ComfyUI: OK (v{stats['system']['comfyui_version']})")
        print(f"lowvram: {'--lowvram' in argv}")
    except Exception as e:
        print(f"ComfyUI: FAILED ({e})")
        return 1

    try:
        r = c.get(f"{UI}/api/session")
        print(f"UI: OK")
    except Exception as e:
        print(f"UI: FAILED ({e})")
        return 1

    session_id = f"hw_final_{int(time.time())}"
    print(f"Session: {session_id}\n")

    turns = [
        ("Turn 1: red square 384x384",
         "Create a red square, 384x384, 10 steps"),
        ("Turn 2: blue circle 512x512",
         "Create a blue circle, 512x512, 10 steps"),
        ("Turn 3: green triangle 256x256",
         "Create a green triangle, 256x256, 10 steps"),
    ]

    results = []
    for desc, request in turns:
        print(f"=== {desc} ===")
        t0 = time.time()
        events = run_turn(session_id, request)
        elapsed = time.time() - t0

        result_ev = next((e for e in events if e.get("type") == "result"), None)
        error_ev = next((e for e in events if e.get("type") == "error"), None)

        if result_ev:
            state = result_ev.get("state")
            preview = result_ev.get("preview")
            print(f"  Result: state={state}, preview={preview}, time={elapsed:.1f}s")
            results.append((desc.split(":")[0].strip(), state == "SUCCESS", elapsed))
        elif error_ev:
            err = error_ev.get("error", "unknown")
            print(f"  Error: {err[:120]}, time={elapsed:.1f}s")
            results.append((desc.split(":")[0].strip(), False, elapsed))
        else:
            print(f"  No result (events={len(events)}), time={elapsed:.1f}s")
            results.append((desc.split(":")[0].strip(), False, elapsed))

    # Final session check
    r = c.get(f"{UI}/api/session", params={"session_id": session_id})
    session = r.json()
    print(f"\nSession: exists={session.get('exists')}, turns={len(session.get('history', []))}")
    if session.get("active_asset"):
        print(f"  active_asset: {session['active_asset'][:16]}...")
    if session.get("messages"):
        for msg in session["messages"]:
            cap = msg.get("capability", "?")
            wf = msg.get("workflow", "?")
            print(f"  msg: capability={cap}, workflow={wf}")

    # Check ComfyUI history
    r = c.get(f"{COMFY}/history")
    hist = r.json()
    print(f"\nComfyUI history: {len(hist)} entries")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/3 turns succeeded")
    for name, ok, elapsed in results:
        print(f"  {name}: {'OK' if ok else 'FAILED'} ({elapsed:.1f}s)")
    print(f"{'='*60}")

    return 0 if passed == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
