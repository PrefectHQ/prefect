# prefect-aws

AWS integration for Prefect: blocks, tasks, and an ECS worker for running flows on Fargate.

## ECS Worker Infrastructure

The `infra/` directory contains AWS CDK code that **generates** the CloudFormation templates shipped in `prefect_aws/templates/ecs/`. The JSON files there are build artifacts — do not edit them directly.

To update ECS worker configuration:
1. Edit the CDK stacks in `infra/worker/` (e.g., `service_stack.py`)
2. Regenerate templates:
   ```bash
   cd src/integrations/prefect-aws/infra
   npm install            # install pinned CDK version
   just generate-cfn      # synth and copy templates to prefect_aws/templates/ecs/
   ```
3. Commit both the CDK source change and the regenerated JSON together

The CDK package version in `infra/package.json` is pinned to an **exact version** (no `^`) to keep template generation reproducible. When upgrading CDK, bump the version explicitly, regenerate all templates, and verify no unintended changes appear in the diff.

`npx --no-install` in the justfile enforces that the locally-installed pinned CDK is used; the command will fail if `npm install` has not been run first.

## Related

- `src/integrations/AGENTS.md` → General integration conventions and release process
