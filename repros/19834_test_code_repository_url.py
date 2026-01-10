"""
Test script for issue #19834: code_repository_url field on Deployment

Usage:
    uv run repros/19834_test_code_repository_url.py
"""

import asyncio
from prefect import flow
from prefect.client.orchestration import get_client


@flow
def test_flow():
    print("Hello from test flow!")
    return 42


async def main():
    async with get_client() as client:
        # 1. Create a flow first
        flow_id = await client.create_flow_from_name("test-flow-with-repo")
        print(f"Created flow: {flow_id}")

        # 2. Create deployment with code_repository_url
        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name="test-deployment-with-repo",
            version="v1.0.0",
            code_repository_url="https://github.com/PrefectHQ/prefect",
        )
        print(f"Created deployment: {deployment_id}")

        # 3. Read back the deployment to verify
        deployment = await client.read_deployment(deployment_id)
        print(f"\n=== Deployment Details ===")
        print(f"Name: {deployment.name}")
        print(f"Version: {deployment.version}")
        print(f"Code Repository URL: {deployment.code_repository_url}")
        
        # 4. Verify the field was saved
        if deployment.code_repository_url == "https://github.com/PrefectHQ/prefect":
            print("\n✅ SUCCESS: code_repository_url field works correctly!")
        else:
            print(f"\n❌ FAILED: Expected URL not found. Got: {deployment.code_repository_url}")
        
        print(f"\n🌐 View in UI: http://localhost:4200/deployments/deployment/{deployment_id}")


if __name__ == "__main__":
    asyncio.run(main())
