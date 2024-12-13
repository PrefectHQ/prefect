import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icons";
import { ScheduleBadgeGroup } from "@/components/ui/schedule-badge";
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
	onQuickRun: (deployment: DeploymentWithFlow) => void;
	onCustomRun: (deployment: DeploymentWithFlow) => void;
	onEdit: (deployment: DeploymentWithFlow) => void;
	onDelete: (deployment: DeploymentWithFlow) => void;
	onDuplicate: (deployment: DeploymentWithFlow) => void;
};

const columnHelper = createColumnHelper<DeploymentWithFlow>();

const createColumns = ({
	onQuickRun,
	onCustomRun,
	onEdit,
	onDelete,
	onDuplicate,
}: {
	onQuickRun: (deployment: DeploymentWithFlow) => void;
	onCustomRun: (deployment: DeploymentWithFlow) => void;
	onEdit: (deployment: DeploymentWithFlow) => void;
	onDelete: (deployment: DeploymentWithFlow) => void;
	onDuplicate: (deployment: DeploymentWithFlow) => void;
}) => [
	columnHelper.display({
		id: "name",
		header: "Deployment",
		cell: ({ row }) => (
			<div className="flex flex-col">
				<span
					className="text-sm font-medium truncate"
					title={row.original.name}
				>
					{row.original.name}
				</span>
				<span className="text-xs text-muted-foreground flex items-center gap-1">
					<Icon id="Workflow" size={12} />
					<span className="truncate" title={row.original.flow.name}>
						{row.original.flow.name}
					</span>
				</span>
			</div>
		),
		size: 100,
	}),
	columnHelper.accessor("status", {
		id: "status",
		header: "Status",
		cell: ({ row }) => {
			const status = row.original.status;
			if (!status) return null;
			return (
				<div className="min-w-28">
					<StatusBadge status={status} />
				</div>
			);
		},
		size: 50,
	}),
	columnHelper.display({
		id: "activity",
		header: "Activity",
		cell: () => (
			<div className="flex flex-row gap-2 items-center min-w-28">
				<span className="text-sm text-muted-foreground">TODO</span>
			</div>
		),
		size: 300,
	}),
	columnHelper.display({
		id: "tags",
		header: () => null,
		cell: ({ row }) => <TagBadgeGroup tags={row.original.tags ?? []} />,
	}),
	columnHelper.display({
		id: "schedules",
		header: "Schedules",
		cell: ({ row }) => {
			const schedules = row.original.schedules;
			if (!schedules || schedules.length === 0) return null;
			return <ScheduleBadgeGroup schedules={schedules} />;
		},
		size: 150,
	}),
	columnHelper.display({
		id: "actions",
		cell: (props) => (
			<ActionsCell
				{...props}
				onQuickRun={onQuickRun}
				onCustomRun={onCustomRun}
				onEdit={onEdit}
				onDelete={onDelete}
				onDuplicate={onDuplicate}
			/>
		),
	}),
];

export const DeploymentsDataTable = ({
	deployments,
	onQuickRun,
	onCustomRun,
	onEdit,
	onDelete,
	onDuplicate,
}: DeploymentsDataTableProps) => {
	const table = useReactTable({
		data: deployments,
		columns: createColumns({
			onQuickRun,
			onCustomRun,
			onEdit,
			onDelete,
			onDuplicate,
		}),
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		defaultColumn: {
			maxSize: 300,
		},
	});
	return <DataTable table={table} />;
};
