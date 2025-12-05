export const DOCS_LINKS = {
	"artifacts-guide": "https://docs.prefect.io/v3/develop/artifacts",
	"getting-started":
		"https://docs.prefect.io/v3/get-started/quickstart#open-source",
	"automations-guide":
		"https://docs.prefect.io/v3/automate/events/automations-triggers",
	"blocks-guide": "https://docs.prefect.io/v3/develop/blocks",
	"deployments-guide": "https://docs.prefect.io/v3/deploy/index",
	"flows-guide": "https://docs.prefect.io/v3/develop/flows",
	"global-concurrency-guide":
		"https://docs.prefect.io/v3/develop/global-concurrency-limits",
	"integrations-guide": "https://docs.prefect.io/integrations/integrations",
	"task-concurrency-guide":
		"https://docs.prefect.io/v3/develop/task-run-limits",
	"variables-guide": "https://docs.prefect.io/latest/guides/variables/",
	"work-pools-guide":
		"https://docs.prefect.io/latest/deploy/infrastructure-concepts/work-pools",
} as const;

export type DocsID = keyof typeof DOCS_LINKS;
