# prefect-aws

Prefect integration for AWS services: ECS workers, S3 storage, and related utilities.

## ECS Infrastructure Templates

The JSON files in `prefect_aws/templates/ecs/` are **CDK-generated CloudFormation templates** — do not edit them directly. They are synthesized from CDK stacks in `infra/worker/` (`service_stack.py` and `events_stack.py`).

To update ECS infrastructure:
1. Modify the CDK stack in `infra/worker/`
2. Run `just generate-cfn` from the `infra/` directory (requires Node.js; run `npm ci` first)
3. Commit both the stack code and the updated JSON templates together

The CI release workflow verifies templates are in sync via `git diff --exit-code` before building — commits that modify a CDK stack without regenerating the templates will fail CI.

`infra/cdk.json` sets `"versionReporting": false` — do not remove this flag. Without it, CDK embeds non-deterministic version analytics in the templates, causing spurious diffs that break CI verification.
