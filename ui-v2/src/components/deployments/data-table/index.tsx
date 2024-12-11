import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icons";
import { StatusBadge } from "@/components/ui/status-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import type { DeploymentWithFlow } from "@/hooks/deployments";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { ActionsCell } from "./cells";

type DeploymentsDataTableProps = {
	deployments: DeploymentWithFlow[];
};

const columnHelper = createColumnHelper<DeploymentWithFlow>();

const createColumns = () => [
	columnHelper.display({
		id: "name",
		header: "Deployment",
		cell: ({ row }) => (
			<div className="flex flex-col">
				<span className="text-sm font-medium truncate">
					{row.original.name}
				</span>
				<span className="text-xs text-muted-foreground flex items-center gap-1 truncate">
					<Icon id="Workflow" size={12} /> {row.original.flow.name}
				</span>
			</div>
		),
		maxSize: 150,
	}),
	columnHelper.accessor("status", {
		id: "status",
		header: "Status",
		cell: ({ row }) => {
			const status = row.original.status;
			if (!status) return null;
			return <StatusBadge status={status} />;
		},
		maxSize: 50,
	}),
	columnHelper.display({
		id: "activity",
		header: "Activity",
		cell: () => "TODO",
	}),
	columnHelper.display({
		id: "tags",
		header: () => null,
		cell: ({ row }) => <TagBadgeGroup tags={row.original.tags ?? []} />,
	}),
	columnHelper.display({
		id: "schedules",
		header: "Schedules",
		cell: () => "TODO",
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => <ActionsCell {...props} />,
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
		defaultColumn: {
			maxSize: 300,
		},
	});
	return <DataTable table={table} />;
};
