import type { ReactNode } from "react";
import type { Artifact } from "@/api/artifacts";
import { DetailImage } from "./detail-image";
import { DetailMarkdown } from "./detail-markdown";
import { DetailProgress } from "./detail-progress";
import { DetailTable } from "./detail-table";

export type ArtifactDataViewProps = {
	artifact: Artifact;
	/** Rendered for artifact types without a dedicated view. Defaults to the data as JSON. */
	fallback?: ReactNode;
};

export const ArtifactDataView = ({
	artifact,
	fallback,
}: ArtifactDataViewProps) => {
	switch (artifact.type) {
		case "markdown":
		case "link":
			return <DetailMarkdown markdown={artifact.data as string} />;
		case "image":
			return <DetailImage url={artifact.data as string} />;
		case "progress":
			return <DetailProgress progress={artifact.data as number} />;
		case "table":
			return <DetailTable tableData={artifact.data as string} />;
		default:
			return fallback ?? <pre>{JSON.stringify(artifact.data, null, 2)}</pre>;
	}
};
