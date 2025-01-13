import type { DeploymentWithFlow } from "@/api/deployments";
import { DataTable } from "@/components/ui/data-table";
import { FlowRunActivityBarGraphTooltipProvider } from "@/components/ui/flow-run-acitivity-bar-graph";
import { Icon } from "@/components/ui/icons";
import { ScheduleBadgeGroup } from "@/components/ui/schedule-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import type { OnChangeFn, PaginationState } from "@tanstack/react-table";
import {
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useCallback } from "react";
import { ActionsCell, ActivityCell } from "./cells";

type DeploymentsDataTableProps = {
	deployments: DeploymentWithFlow[];
	pageCount: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
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
				{row.original.flow && (
					<span className="text-xs text-muted-foreground flex items-center gap-1">
						<Icon id="Workflow" size={12} />
						<span className="truncate" title={row.original.flow.name}>
							{row.original.flow.name}
						</span>
					</span>
				)}
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
		cell: (props) => (
			<div className="flex flex-row gap-2 items-center min-w-28">
				<ActivityCell {...props} />
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
	pagination,
	pageCount,
	onPaginationChange,
	onQuickRun,
	onCustomRun,
	onEdit,
	onDelete,
	onDuplicate,
}: DeploymentsDataTableProps) => {
	const handlePaginationChange: OnChangeFn<PaginationState> = useCallback(
		(updater) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			onPaginationChange(newPagination);
		},
		[pagination, onPaginationChange],
	);

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
		pageCount,
		manualPagination: true,
		defaultColumn: {
			maxSize: 300,
		},
		state: {
			pagination,
		},
		onPaginationChange: handlePaginationChange,
	});
	return (
		<FlowRunActivityBarGraphTooltipProvider>
			<DataTable table={table} />
		</FlowRunActivityBarGraphTooltipProvider>
	);
};
