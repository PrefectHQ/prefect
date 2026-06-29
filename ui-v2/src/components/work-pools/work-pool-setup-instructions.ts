type WorkPoolCategory = "push" | "managed" | "kubernetes" | "worker";

export const categorizeWorkPoolType = (type: string): WorkPoolCategory => {
	if (type.endsWith(":push")) return "push";
	if (type.endsWith(":managed")) return "managed";
	if (type === "kubernetes") return "kubernetes";
	return "worker";
};

const WORK_POOL_TYPE_DOCS: Record<string, string> = {
	kubernetes:
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/kubernetes",
	ecs: "https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"ecs:push":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"cloud-run":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"cloud-run:push":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"cloud-run-v2":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"cloud-run-v2:push":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"azure-container-instance":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	"azure-container-instance:push":
		"https://docs.prefect.io/v3/deploy/infrastructure-examples/serverless",
	docker: "https://docs.prefect.io/v3/deploy/infrastructure-examples/docker",
	process:
		"https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools",
};

const DEFAULT_DOCS_URL =
	"https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools";

export const getWorkPoolDocsUrl = (type: string): string => {
	return WORK_POOL_TYPE_DOCS[type] ?? DEFAULT_DOCS_URL;
};

type SetupInstructions = {
	title: string;
	description: string;
	command?: string;
	docsUrl: string;
};

export const getWorkPoolSetupInstructions = (
	workPoolName: string,
	workPoolType: string,
): SetupInstructions => {
	const category = categorizeWorkPoolType(workPoolType);
	const docsUrl = getWorkPoolDocsUrl(workPoolType);

	switch (category) {
		case "managed":
			return {
				title: "Your work pool is ready!",
				description:
					"Prefect manages the infrastructure for this work pool. No additional setup is required.",
				docsUrl,
			};
		case "push":
			return {
				title: "Your work pool is almost ready!",
				description:
					"This is a push work pool. Workers are not required — runs are submitted directly to your cloud infrastructure. Check the docs for credential setup.",
				docsUrl,
			};
		case "kubernetes":
			return {
				title: "Your work pool is almost ready!",
				description:
					"For production, deploy a worker using the Prefect Helm chart.",
				command: `helm install prefect-worker prefect/prefect-worker --set worker.config.workPool="${workPoolName}"`,
				docsUrl,
			};
		default:
			return {
				title: "Your work pool is almost ready!",
				description: "Run this command to start a worker.",
				command: `prefect worker start --pool "${workPoolName}"`,
				docsUrl,
			};
	}
};
