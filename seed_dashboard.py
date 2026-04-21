"""Seed flows + flow runs for manual testing of the dashboard accordion pagination."""

import httpx

API = "http://localhost:4200/api"


def ensure_flow(client: httpx.Client, name: str) -> str:
    r = client.post("/flows/", json={"name": name})
    r.raise_for_status()
    return r.json()["id"]


def create_flow_run(client, flow_id: str, name: str, state_type: str) -> None:
    r = client.post(
        "/flow_runs/",
        json={
            "flow_id": flow_id,
            "name": name,
            "state": {
                "type": state_type,
                "name": state_type.title(),
                "message": "seeded",
            },
        },
    )
    r.raise_for_status()


def main():
    with httpx.Client(base_url=API, timeout=30.0) as client:
        flow_a = ensure_flow(client, "seed-flow-a")
        for i in range(5):
            create_flow_run(client, flow_a, f"A-failed-{i + 1}", "FAILED")
        flow_b = ensure_flow(client, "seed-flow-b")
        for i in range(2):
            create_flow_run(client, flow_b, f"B-failed-{i + 1}", "FAILED")
        flow_c = ensure_flow(client, "seed-flow-c")
        for i in range(5):
            create_flow_run(client, flow_c, f"C-running-{i + 1}", "RUNNING")
        print(f"seeded: a={flow_a} b={flow_b} c={flow_c}")


if __name__ == "__main__":
    main()
