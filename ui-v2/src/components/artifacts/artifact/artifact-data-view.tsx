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

/**
 * Returns table rows when the data is a list of row objects, either as a JSON
 * string (what the Python SDK sends) or already parsed. Returns null for
 * anything else, e.g. malformed JSON or column-oriented tables.
 */
const getTableRows = (data: unknown): Record<string, unknown>[] | null => {
	let value = data;
	if (typeof value === "string") {
		try {
			value = JSON.parse(value);
		} catch {
			return null;
		}
	}
	const isRowList =
		Array.isArray(value) &&
		value.every(
			(row) => typeof row === "object" && row !== null && !Array.isArray(row),
		);
	return isRowList ? (value as Record<string, unknown>[]) : null;
};

export const ArtifactDataView = ({
	artifact,
	fallback,
}: ArtifactDataViewProps) => {
	const rawData = fallback ?? (
		<pre>{JSON.stringify(artifact.data, null, 2)}</pre>
	);

	switch (artifact.type) {
		case "markdown":
		case "link":
			return <DetailMarkdown markdown={artifact.data as string} />;
		case "image":
			return <DetailImage url={artifact.data as string} />;
		case "progress":
			return <DetailProgress progress={artifact.data as number} />;
		case "table": {
			const rows = getTableRows(artifact.data);
			return rows ? <DetailTable tableData={JSON.stringify(rows)} /> : rawData;
		}
		default:
			return rawData;
	}
};
