import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useDeferredValue, useMemo, useState } from "react";
import type { Deployment } from "@/api/deployments";
import { DataTable } from "@/components/ui/data-table";
import { SearchInput } from "@/components/ui/input";
import { Typography } from "@/components/ui/typography";
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

const columns = [
	columnHelper.accessor("key", { header: "Key" }),
	columnHelper.accessor("value", { header: "Override" }),
	columnHelper.accessor("defaultValue", { header: "Default" }),
	columnHelper.accessor("type", { header: "Type" }),
];

/**
 *
 * @param deployment
 * @returns converts a deployment schema into a parameters table schema
 */
const useDeploymentParametersToTable = (
	deployment: Deployment,
): Array<ParametersTableColumns> =>
	useMemo(() => {
		if (!deployment.parameter_openapi_schema) {
			return [];
		}

		const parameterOpenApiSchema = deployment.parameter_openapi_schema
			.properties as Record<string, ParameterOpenApiSchema>;
		const parameters = deployment.parameters as Record<string, unknown>;
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
				parameter.value
					?.toString()
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()) ||
				parameter.defaultValue
					?.toString()
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()) ||
				parameter.type
					?.toString()
					.toLowerCase()
					.includes(deferredSearch.toLowerCase()),
		);
	}, [data, deferredSearch]);

	const table = useReactTable({
		data: filteredData,

		columns,
		getCoreRowModel: getCoreRowModel(),
		defaultColumn: { maxSize: 300 },
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
	});

	return (
		<div className="flex flex-col gap-4">
			<div className="flex items-center justify-between">
				<Typography variant="bodySmall" className="text-muted-foreground">
					{filteredData.length} {pluralize(filteredData.length, "parameter")}
				</Typography>
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
