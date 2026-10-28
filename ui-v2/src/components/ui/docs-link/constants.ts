export const DOCS_LINKS = {
	"artifacts-guide": "https://www.prefect.io/docs/v3/develop/artifacts",
	"getting-started":
		"https://www.prefect.io/docs/v3/get-started/quickstart#open-source",
	"automations-guide":
		"https://www.prefect.io/docs/v3/automate/events/automations-triggers",
	"blocks-guide": "https://www.prefect.io/docs/v3/develop/blocks",
	"deployments-guide": "https://www.prefect.io/docs/v3/deploy/index",
	"flows-guide": "https://www.prefect.io/docs/v3/concepts/flows",
	"global-concurrency-guide":
		"https://www.prefect.io/docs/v3/develop/global-concurrency-limits",
	"integrations-guide": "https://www.prefect.io/docs/integrations/integrations",
	"task-concurrency-guide":
		"https://www.prefect.io/docs/v3/develop/task-run-limits",
	"variables-guide": "https://www.prefect.io/docs/latest/guides/variables/",
	"work-pools-guide":
		"https://www.prefect.io/docs/latest/deploy/infrastructure-concepts/work-pools",
} as const;

export type DocsID = keyof typeof DOCS_LINKS;
