import { Icon } from "./icons";

import { Button } from "./button";

const DOCS_LINKS = {
	"global-concurrency-guide":
		"https://docs.prefect.io/v3/develop/global-concurrency-limits",
	"task-concurrency-guide":
		"https://docs.prefect.io/v3/develop/task-run-limits",
	"variables-guide": "https://docs.prefect.io/latest/guides/variables/",
} as const;

type DocsID = keyof typeof DOCS_LINKS;

type Props = {
	id: DocsID;
};

export const DocsLink = ({ id }: Props): JSX.Element => {
	return (
		<a href={DOCS_LINKS[id]} target="_blank" rel="noreferrer">
			<Button variant="outline">
				View Docs <Icon id="ExternalLink" className="h-4 w-4 ml-2" />
			</Button>
		</a>
	);
};
