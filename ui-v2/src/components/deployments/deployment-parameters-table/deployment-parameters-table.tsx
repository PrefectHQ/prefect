import { useDeferredValue, useMemo, useState } from "react";
import type { Deployment } from "@/api/deployments";
import { DataTable } from "@/components/ui/data-table";
import { SearchInput } from "@/components/ui/input";
import { createColumnHelper, useTable } from "@/lib/tanstack-table";
import { pluralize } from "@/utils";

type DeploymentParametersTableProps = {
	deployment: Deployment;
};

type ParameterOpenApiSchema = {
	default: unknown;
	position: number;
	title: string;
	type: "boolean" | "number" | "null" | "string";
};

type ParametersTableColumns = {
	key: string;
	value: unknown;
	defaultValue: unknown;
	type: string | undefined;
};

const columnHelper = createColumnHelper<ParametersTableColumns>();

/**
 * Formats object-valued parameters as JSON while preserving existing scalar and
 * array output.
 */
const formatParameterValue = (value: unknown): string => {
	if (value === null || value === undefined) {
		return "";
	}
	if (Array.isArray(value)) {
		return value.join(",");
	}
	if (typeof value === "object") {
		return JSON.stringify(value);
	}
	if (
		typeof value === "string" ||
		typeof value === "number" ||
		typeof value === "boolean" ||
		typeof value === "bigint"
	) {
		return value.toString();
	}
	return JSON.stringify(value) ?? "";
};

const columns = columnHelper.columns([
	columnHelper.accessor("key", {
		header: "Key",
		cell: ({ row }) => (
			<span
				className="font-mono text-sm truncate block max-w-[200px]"
				title={row.original.key}
			>
				{row.original.key}
			</span>
		),
	}),
	columnHelper.accessor("value", {
		header: "Override",
		cell: ({ getValue }) => (
			<span className="whitespace-normal break-words font-mono text-sm">
				{formatParameterValue(getValue())}
			</span>
		),
	}),
	columnHelper.accessor("defaultValue", {
		header: "Default",
		cell: ({ getValue }) => (
			<span className="whitespace-normal break-words font-mono text-sm">
				{formatParameterValue(getValue())}
			</span>
		),
	}),
	columnHelper.accessor("type", { header: "Type" }),
]);

/**
 *
 * @param deployment
 * @returns converts a deployment schema into a parameters table schema
 */
const useDeploymentParametersToTable = (
	deployment: Deployment,
): Array<ParametersTableColumns> =>
	useMemo(() => {
		const parameterOpenApiSchema = deployment.parameter_openapi_schema
			?.properties as Record<string, ParameterOpenApiSchema> | undefined;
		if (!parameterOpenApiSchema) {
			return [];
		}

		const parameters = (deployment.parameters ?? {}) as Record<string, unknown>;
		return Object.keys(parameterOpenApiSchema)
			.sort((a, b) => {
				return (
					parameterOpenApiSchema[a].position -
					parameterOpenApiSchema[b].position
				);
			})
			.map((key) => {
				const parameter = parameterOpenApiSchema[key];
				return {
					key,
					value: parameters[key],
					defaultValue: parameter.default,
					type: parameter.type,
				};
			});
	}, [deployment]);

export const DeploymentParametersTable = ({
	deployment,
}: DeploymentParametersTableProps) => {
	const [search, setSearch] = useState("");
	const data = useDeploymentParametersToTable(deployment);

	// nb: This table does search via client side
	const deferredSearch = useDeferredValue(search);
	const filteredData = useMemo(() => {
		return data.filter(
			(parameter) =>
				parameter.key.toLowerCase().includes(deferredSearch.toLowerCase()) ||
				formatParameterValue(parameter.value)
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()) ||
				formatParameterValue(parameter.defaultValue)
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()) ||
				parameter.type
					?.toString()
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const table = useTable({
		data: filteredData,

		columns,
		defaultColumn: { maxSize: 300 },
	});

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<p className="text-sm text-muted-foreground">
					{filteredData.length.toLocaleString()}{" "}
					{pluralize(filteredData.length, "parameter")}
				</p>
				<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
					<SearchInput
						className="sm:col-span-2 md:col-span-2 lg:col-span-3"
						placeholder="Search parameters"
						value={search}
						onChange={(e) => setSearch(e.target.value)}
					/>
				</div>
			</div>
			<DataTable table={table} />
		</div>
	);
};
