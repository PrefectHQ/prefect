import type { JSX } from "react";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";

import { DOCS_LINKS, type DocsID } from "./constants";

type DocsLinkProps = {
	id: DocsID;
	label?: "View Docs" | "Documentation";
};

export const DocsLink = ({
	id,
	label = "View Docs",
}: DocsLinkProps): JSX.Element => {
	return (
		<a href={DOCS_LINKS[id]} target="_blank" rel="noreferrer">
			<Button variant="outline">
				{label} <Icon id="ExternalLink" className="size-4 ml-2" />
			</Button>
		</a>
	);
};
