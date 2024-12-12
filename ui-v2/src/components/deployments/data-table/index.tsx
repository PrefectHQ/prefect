import { DataTable } from "@/components/ui/data-table";
import { Icon } from "@/components/ui/icons";
import { ScheduleBadge } from "@/components/ui/schedule-badge";
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
		cell: ({ row }) =>
			row.original.schedules?.map((entry) => (
				<ScheduleBadge key={entry.id} schedule={entry.schedule} />
			)),
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
