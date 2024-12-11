import { DataTable } from "@/components/ui/data-table";
import type { Deployment } from "@/hooks/deployments";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";

type DeploymentsDataTableProps = {
	deployments: Deployment[];
};

const columnHelper = createColumnHelper<Deployment>();

const createColumns = () => [
	columnHelper.accessor("name", {
		header: "Name",
	}),
];

export const DeploymentsDataTable = ({
	deployments,
}: DeploymentsDataTableProps) => {
	const table = useReactTable({
		data: deployments,
		columns: createColumns(),
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
	});
	return <DataTable table={table} />;
};
