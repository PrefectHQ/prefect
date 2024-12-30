import type { JSX } from "react";

import { Icon } from "./icons";

import { Button } from "./button";

const DOCS_LINKS = {
	"automations-guide":
		"https://docs.prefect.io/v3/automate/events/automations-triggers",
	"global-concurrency-guide":
		"https://docs.prefect.io/v3/develop/global-concurrency-limits",
	"task-concurrency-guide":
		"https://docs.prefect.io/v3/develop/task-run-limits",
	"variables-guide": "https://docs.prefect.io/latest/guides/variables/",
	"deployments-guide": "https://docs.prefect.io/v3/deploy/index",
} as const;

type DocsID = keyof typeof DOCS_LINKS;

type Props = {
	id: DocsID;
	label?: "View Docs" | "Documentation";
};

export const DocsLink = ({ id, label = "View Docs" }: Props): JSX.Element => {
	return (
		<a href={DOCS_LINKS[id]} target="_blank" rel="noreferrer">
			<Button variant="outline">
				{label} <Icon id="ExternalLink" className="h-4 w-4 ml-2" />
			</Button>
		</a>
	);
};
