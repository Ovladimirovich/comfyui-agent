"""
Gemma E2B Experiment — Test Suite T1-T8

Controlled experiment comparing Gemma E2B + comfyui-mcp
with production Agent's WorkflowEngine.

Metrics:
- Tool call accuracy
- Latency per round
- Token usage
- Success/failure rate
- Error recovery
"""

import json
import time
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Конфигурация
ADAPTER_PATH = Path(__file__).parent / "gemma_e2b_adapter.js"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Тесты T1-T8
TESTS = [
    {
        "id": "T1",
        "name": "Simple txt2img",
        "prompt": "Create an image of a cat sitting on a windowsill",
        "expected_tools": ["create_workflow", "enqueue_workflow", "generate_image"],
        "success_criteria": "Image generated successfully"
    },
    {
        "id": "T2",
        "name": "Workflow construction",
        "prompt": "Create a workflow for txt2img with SDXL model",
        "expected_tools": ["create_workflow"],
        "success_criteria": "Valid workflow JSON created"
    },
    {
        "id": "T3",
        "name": "Workflow modification",
        "prompt": "Add an upscale node to the workflow",
        "expected_tools": ["create_workflow", "node_snapshot"],
        "success_criteria": "Workflow modified with upscale node"
    },
    {
        "id": "T4",
        "name": "Node discovery",
        "prompt": "Find a node for face swap",
        "expected_tools": ["search_custom_nodes", "list_api_nodes"],
        "success_criteria": "Face swap node identified"
    },
    {
        "id": "T5",
        "name": "Multi-step generation",
        "prompt": "Generate an image and then upscale it to 2x",
        "expected_tools": ["create_workflow", "enqueue_workflow"],
        "success_criteria": "Both generation and upscale completed"
    },
    {
        "id": "T6",
        "name": "Error recovery",
        "prompt": "Run a workflow with invalid node type 'NonExistentNode'",
        "expected_tools": ["create_workflow", "enqueue_workflow"],
        "success_criteria": "Error handled gracefully, helpful message returned"
    },
    {
        "id": "T7",
        "name": "Image input",
        "prompt": "Upload this image and apply style transfer to make it look like a painting",
        "expected_tools": ["upload_image", "create_workflow", "enqueue_workflow"],
        "success_criteria": "Image processed with style transfer"
    },
    {
        "id": "T8",
        "name": "Verification",
        "prompt": "What's in the image at C:\\output\\test.png?",
        "expected_tools": ["get_image"],
        "success_criteria": "Image description returned"
    }
]


def run_test(test: dict) -> dict:
    """Запуск одного теста."""
    print(f"\n{'='*60}")
    print(f"TEST {test['id']}: {test['name']}")
    print(f"PROMPT: {test['prompt']}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ["node", str(ADAPTER_PATH), test["prompt"]],
            capture_output=True,
            text=True,
            timeout=600,  # 10 минут максимум
            encoding="utf-8",
            errors="replace"
        )
        
        elapsed = time.time() - start_time
        
        # Парсим результат
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        # Извлекаем метрики
        metrics = {
            "test_id": test["id"],
            "test_name": test["name"],
            "prompt": test["prompt"],
            "success": success,
            "elapsed_seconds": round(elapsed, 2),
            "return_code": result.returncode,
            "output_lines": len(output.splitlines()),
            "has_tool_calls": "TOOL CALL:" in output,
            "has_final_answer": "GEMMA FINAL:" in output,
            "timestamp": datetime.now().isoformat()
        }
        
        # Проверяем какие tools были вызваны
        called_tools = []
        for line in output.splitlines():
            if line.startswith("TOOL CALL:"):
                tool_name = line.split("TOOL CALL:")[1].strip()
                called_tools.append(tool_name)
        metrics["called_tools"] = called_tools
        
        # Проверяем expected tools
        if test["expected_tools"]:
            expected_set = set(test["expected_tools"])
            called_set = set(called_tools)
            metrics["expected_tools_match"] = bool(expected_set & called_set)
        
        print(f"\nRESULT: {'PASS' if success else 'FAIL'}")
        print(f"TIME: {elapsed:.1f}s")
        print(f"TOOLS CALLED: {called_tools}")
        
        return metrics
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return {
            "test_id": test["id"],
            "test_name": test["name"],
            "prompt": test["prompt"],
            "success": False,
            "elapsed_seconds": round(elapsed, 2),
            "error": "Timeout (600s)",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "test_id": test["id"],
            "test_name": test["name"],
            "prompt": test["prompt"],
            "success": False,
            "elapsed_seconds": round(elapsed, 2),
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def run_experiment(test_ids: list[str] = None):
    """Запуск эксперимента."""
    print("Gemma E2B Experiment — T1-T8")
    print(f"Start: {datetime.now().isoformat()}")
    
    tests_to_run = TESTS
    if test_ids:
        tests_to_run = [t for t in TESTS if t["id"] in test_ids]
    
    results = []
    for test in tests_to_run:
        result = run_test(test)
        results.append(result)
        
        # Сохраняем промежуточные результаты
        results_file = RESULTS_DIR / "experiment_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Итоги
    print(f"\n{'='*60}")
    print("EXPERIMENT SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"  {r['test_id']}: {status} ({r['elapsed_seconds']}s)")
    
    return results


if __name__ == "__main__":
    #可以选择性运行某些测试
    test_ids = sys.argv[1:] if len(sys.argv) > 1 else None
    results = run_experiment(test_ids)
    
    # Сохраняем итоговые результаты
    results_file = RESULTS_DIR / "experiment_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {results_file}")
