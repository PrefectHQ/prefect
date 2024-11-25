import type { components } from "@/api/prefect";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo } from "react";
import { DataTable } from "@/components/ui/data-table";

type DeploymentsDataTableProps = {
	deployments: components["schemas"]["DeploymentResponse"][];
};

export const DeploymentsDataTable = ({
	deployments,
}: DeploymentsDataTableProps) => {
	const columns = useMemo(() => createColumns(), []);

	const table = useReactTable({
		data: deployments,
		columns: columns,
		getCoreRowModel: getCoreRowModel(),
	});

	return <DataTable table={table} />;
};

const columnHelper =
	createColumnHelper<components["schemas"]["DeploymentResponse"]>();

const createColumns = () => {
	return [
		columnHelper.accessor("name", {
			header: "Name",
		}),
	];
};
