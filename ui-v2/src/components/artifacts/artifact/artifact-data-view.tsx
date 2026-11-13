import type { ReactNode } from "react";
import type { Artifact } from "@/api/artifacts";
import { DetailImage } from "./detail-image";
import { DetailMarkdown } from "./detail-markdown";
import { DetailProgress } from "./detail-progress";
import { DetailTable } from "./detail-table";

export type ArtifactDataViewProps = {
	artifact: Artifact;
	/**
	 * Rendered for artifact types without a dedicated view, or when the data
	 * doesn't have the shape the type's view expects. Defaults to the data as JSON.
	 */
	fallback?: ReactNode;
};

/**
 * Returns table rows when the data is a list of row objects or a list of row
 * arrays, either as a JSON string (what the Python SDK sends) or already
 * parsed. Returns null for anything else, e.g. malformed JSON, null or
 * primitive rows, or column-oriented tables.
 */
const getTableRows = (
	data: unknown,
): (Record<string, unknown> | unknown[])[] | null => {
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
		value.every((row) => typeof row === "object" && row !== null);
	return isRowList ? (value as (Record<string, unknown> | unknown[])[]) : null;
};

export const ArtifactDataView = ({
	artifact,
	fallback,
}: ArtifactDataViewProps) => {
	const { data } = artifact;
	const rawData = fallback ?? <pre>{JSON.stringify(data, null, 2)}</pre>;

	switch (artifact.type) {
		case "markdown":
		case "link":
			return typeof data === "string" ? (
				<DetailMarkdown markdown={data} />
			) : (
				rawData
			);
		case "image":
			return typeof data === "string" ? <DetailImage url={data} /> : rawData;
		case "progress":
			return typeof data === "number" ? (
				<DetailProgress progress={data} />
			) : (
				rawData
			);
		case "table": {
			const rows = getTableRows(data);
			return rows ? <DetailTable tableData={JSON.stringify(rows)} /> : rawData;
		}
		default:
			return rawData;
	}
};
