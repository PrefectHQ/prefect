import type { Deployment } from "@/api/deployments";
import {
	FlowRun,
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { DataTable } from "@/components/ui/data-table";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";

import { Flow } from "@/api/flows";
import { Checkbox } from "@/components/ui/checkbox";

import { Skeleton } from "@/components/ui/skeleton";

import { CheckedState } from "@radix-ui/react-checkbox";
import {
	OnChangeFn,
	PaginationState,
	TableOptions,
	createColumnHelper,
	getCoreRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { Suspense, use, useCallback, useMemo } from "react";

import { DeploymentCell } from "./flow-runs-cells/deployment-cell";
import { DurationCell } from "./flow-runs-cells/duration-cell";
import { NameCell } from "./flow-runs-cells/name-cell";
import { ParametersCell } from "./flow-runs-cells/parameters-cell";
import { StartTimeCell } from "./flow-runs-cells/start-time-cell";
import { TasksCell } from "./flow-runs-cells/tasks-cell";
import { RowSelectionContext } from "./row-selection-context";

export type FlowRunsDataTableRow = FlowRun & {
	flow: Flow;
	numTaskRuns?: number;
	deployment?: Deployment;
};

const columnHelper = createColumnHelper<FlowRunsDataTableRow>();

const createColumns = ({
	isSelectable = false,
	showDeployment,
}: {
	isSelectable?: boolean;
	showDeployment: boolean;
}) => {
	const ret = [
		columnHelper.display({
			size: 320,
			id: "name",
			header: "Name",
			cell: ({ row }) => <NameCell flowRun={row.original} />,
		}),
		columnHelper.accessor("state", {
			id: "state",
			header: "State",
			cell: (props) => {
				const state = props.getValue();
				if (!state) {
					return null;
				}
				return <StateBadge type={state.type} name={state.name} />;
			},
		}),
		columnHelper.display({
			id: "startTime",
			header: "Start Time",
			cell: ({ row }) => <StartTimeCell flowRun={row.original} />,
		}),
		columnHelper.accessor("parameters", {
			id: "parameters",
			header: "Parameters",
			cell: ParametersCell,
		}),
		columnHelper.display({
			id: "duration",
			header: "Duration",
			cell: ({ row }) => {
				const flowRun = row.original;
				if (flowRun.state?.type === "SCHEDULED") {
					return null;
				}
				return <DurationCell flowRun={flowRun} />;
			},
		}),
		columnHelper.display({
			size: 200,
			id: "taskRuns",
			header: "Task Runs",
			cell: ({ row }) => {
				const flowRun = row.original;
				if (flowRun.state?.type === "SCHEDULED") {
					return null;
				}
				// nb: Defer data loading since this column is not guaranteed
				return (
					<Suspense fallback={<Skeleton className="p-4 h-2 w-full" />}>
						<TasksCell flowRun={flowRun} />
					</Suspense>
				);
			},
		}),
		columnHelper.accessor("tags", {
			id: "tags",
			header: "Tags",
			cell: (props) => (
				<TagBadgeGroup tags={props.getValue()} maxTagsDisplayed={4} />
			),
		}),
	];

	if (isSelectable) {
		ret.unshift(
			columnHelper.display({
				size: 40,
				id: "select",
				header: ({ table }) => {
					let checkedState: CheckedState = false;
					if (table.getIsAllRowsSelected()) {
						checkedState = true;
					} else if (table.getIsSomePageRowsSelected()) {
						checkedState = "indeterminate";
					}
					return (
						<Checkbox
							checked={checkedState}
							onCheckedChange={(value) =>
								table.toggleAllPageRowsSelected(Boolean(value))
							}
							aria-label="Select all"
						/>
					);
				},
				cell: ({ row }) => (
					<Checkbox
						checked={row.getIsSelected()}
						onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
						aria-label="Select row"
					/>
				),
				enableSorting: false,
				enableHiding: false,
			}),
		);
	}
	if (showDeployment) {
		ret.push(
			columnHelper.display({
				size: 200,
				id: "deployment",
				header: "Deployment",
				cell: ({ row }) => {
					const { deployment } = row.original;
					if (!deployment) {
						return null;
					}
					return <DeploymentCell deployment={deployment} />;
				},
			}),
		);
	}
	return ret;
};

export type FlowRunsDataTableProps = {
	flowRunsCount: number;
	flowRuns: Array<FlowRunWithDeploymentAndFlow | FlowRunWithFlow>;
	pageCount: number;
	pagination: PaginationState;
	onPaginationChange: (pagination: PaginationState) => void;
};
export const FlowRunsDataTable = ({
	pagination,
	onPaginationChange,
	flowRunsCount,
	flowRuns,
}: FlowRunsDataTableProps) => {
	const rowSelectionCtx = use(RowSelectionContext);
	const showDeployment = useMemo(
		() => flowRuns.some((flowRun) => "deployment" in flowRun),
		[flowRuns],
	);

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

	let tableOptions: TableOptions<
		FlowRunWithDeploymentAndFlow | FlowRunWithFlow
	> = {
		columns: createColumns({ showDeployment }),
		data: flowRuns,
		defaultColumn: { maxSize: 300 },
		getCoreRowModel: getCoreRowModel(),
		manualPagination: true,
		onPaginationChange: handlePaginationChange,
		rowCount: flowRunsCount,
		state: { pagination },
	};

	if (rowSelectionCtx) {
		const { rowSelection, setRowSelection } = rowSelectionCtx;
		tableOptions = {
			...tableOptions,
			columns: createColumns({ showDeployment, isSelectable: true }),
			getRowId: (row) => row.id,
			onRowSelectionChange: setRowSelection,
			state: { pagination, rowSelection },
		};
	}

	const table = useReactTable(tableOptions);

	return <DataTable table={table} />;
};
