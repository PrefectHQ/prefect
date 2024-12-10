import {
	createColumnHelper,
	getCoreRowModel,
	type PaginationState,
	type Updater,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo, useCallback } from "react";
import { DataTable } from "@/components/ui/data-table";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import { ActionsCell, ActivityCell } from "./cells";
import { DeploymentStatusBadge } from "@/components/ui/deployment-status-badge";
import type { DeploymentWithFlowName } from "./types";
import { Workflow } from "lucide-react";
import { Link } from "@tanstack/react-router";
import { FlowRunActivityBarChart } from "@/components/ui/flow-run-activity-bar-chart";

type DeploymentsDataTableProps = {
	deployments: DeploymentWithFlowName[];
	pagination: PaginationState;
	onPaginationChange: (newPagination: PaginationState) => void;
	currentDeploymentCount: number;
};

export const DeploymentsDataTable = ({
	deployments,
	pagination,
	onPaginationChange,
	currentDeploymentCount,
}: DeploymentsDataTableProps) => {
	const columns = useMemo(() => createColumns(), []);

	const handlePaginationChange = useCallback(
		(updater: Updater<PaginationState>) => {
			let newPagination = pagination;
			if (typeof updater === "function") {
				newPagination = updater(pagination);
			} else {
				newPagination = updater;
			}
			onPaginationChange(newPagination);
		},
		[onPaginationChange, pagination],
	);

	const table = useReactTable({
		data: deployments,
		columns: columns,
		getCoreRowModel: getCoreRowModel(),
		state: {
			pagination,
		},
		manualPagination: true,
		onPaginationChange: handlePaginationChange,
		rowCount: currentDeploymentCount,
	});

	return <DataTable table={table} />;
};

const columnHelper = createColumnHelper<DeploymentWithFlowName>();

const createColumns = () => {
	return [
		columnHelper.display({
			header: "Deployment",
			cell: (props) => (
				<div className="flex flex-col gap-1">
					<span className="text-sm font-medium">{props.row.original.name}</span>
					<Link
						to="/flows/flow/$id"
						params={{ id: props.row.original.flow_id }}
						className="flex flex-row items-center gap-1 text-sm text-muted-foreground hover:underline cursor-pointer"
					>
						<Workflow className="h-4 w-4" />
						{props.row.original.flowName}
					</Link>
				</div>
			),
		}),
		columnHelper.accessor("status", {
			header: "Status",
			cell: (props) => <DeploymentStatusBadge status={props.getValue()} />,
		}),
		{
			id: "activity",
			header: "Activity",
			cell: ActivityCell,
			minSize: 200,
		},
		columnHelper.accessor("tags", {
			header: () => null,
			cell: (props) => {
				const tags = props.getValue();
				if (!tags) return null;
				return <TagBadgeGroup tags={tags} maxTagsDisplayed={3} />;
			},
		}),
		columnHelper.accessor("schedules", {
			header: "Schedules",
		}),
		columnHelper.display({
			id: "actions",
			cell: (props) => <ActionsCell {...props} />,
		}),
	];
};
