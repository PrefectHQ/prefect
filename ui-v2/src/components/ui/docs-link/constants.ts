export const DOCS_LINKS = {
	"automations-guide":
		"https://docs.prefect.io/v3/automate/events/automations-triggers",
	"global-concurrency-guide":
		"https://docs.prefect.io/v3/develop/global-concurrency-limits",
	"task-concurrency-guide":
		"https://docs.prefect.io/v3/develop/task-run-limits",
	"variables-guide": "https://docs.prefect.io/latest/guides/variables/",
	"deployments-guide": "https://docs.prefect.io/v3/deploy/index",
} as const;

export type DocsID = keyof typeof DOCS_LINKS;
