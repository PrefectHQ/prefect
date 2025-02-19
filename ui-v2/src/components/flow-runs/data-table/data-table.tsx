import type { Deployment } from "@/api/deployments";
import {
	FlowRun,
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";

import {
	RowSelectionState,
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { Suspense, useMemo, useState } from "react";

import { Flow } from "@/api/flows";
import { Checkbox } from "@/components/ui/checkbox";
import { DeleteConfirmationDialog } from "@/components/ui/delete-confirmation-dialog";
import { Icon } from "@/components/ui/icons";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";
import { CheckedState } from "@radix-ui/react-checkbox";
import { DeploymentCell } from "./deployment-cell";
import { DurationCell } from "./duration-cell";
import { NameCell } from "./name-cell";
import { ParametersCell } from "./parameters-cell";
import { RunNameSearch } from "./run-name-search";
import { SortFilter } from "./sort-filter";
import { StartTimeCell } from "./start-time-cell";
import { StateFilter } from "./state-filter";
import { TasksCell } from "./tasks-cell";
import { useDeleteFlowRunsDialog } from "./use-delete-flow-runs-dialog";

export type FlowRunsDataTableRow = FlowRun & {
	flow: Flow;
	numTaskRuns?: number;
	deployment?: Deployment;
};

const columnHelper = createColumnHelper<FlowRunsDataTableRow>();

const createColumns = ({
	showDeployment,
}: {
	showDeployment: boolean;
}) => {
	const ret = [
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
};
export const FlowRunsDataTable = ({
	flowRunsCount,
	flowRuns,
}: FlowRunsDataTableProps) => {
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

	const [deleteConfirmationDialogState, confirmDelete] =
		useDeleteFlowRunsDialog();

	const showDeployment = useMemo(
		() => flowRuns.some((flowRun) => "deployment" in flowRun),
		[flowRuns],
	);

	const table = useReactTable({
		getRowId: (row) => row.id,
		onRowSelectionChange: setRowSelection,
		state: { rowSelection },
		data: flowRuns,
		columns: createColumns({
			showDeployment,
		}),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), // TODO: use server-side pagination
	});

	const selectedRows = Object.keys(rowSelection);

	return (
		<>
			<div>
				<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
					<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
						{selectedRows.length > 0 ? (
							<div className="flex items-center gap-1">
								<Typography
									variant="bodySmall"
									className="text-muted-foreground"
								>
									{selectedRows.length} selected
								</Typography>
								<Button
									aria-label="Delete rows"
									size="icon"
									variant="secondary"
									onClick={() => confirmDelete(selectedRows)}
								>
									<Icon id="Trash2" className="h-4 w-4" />
								</Button>
							</div>
						) : (
							<Typography variant="bodySmall" className="text-muted-foreground">
								{flowRunsCount} {pluralize(flowRunsCount, "Flow run")}
							</Typography>
						)}
					</div>
					<div className="sm:col-span-2 md:col-span-2 lg:col-span-3">
						<RunNameSearch
							// TODO
							placeholder="Search by run name"
						/>
					</div>
					<div className="xs:col-span-1 md:col-span-2 lg:col-span-3">
						<StateFilter
							// TODO
							selectedFilters={new Set([])}
							onSelectFilter={() => {}}
						/>
					</div>
					<div className="xs:col-span-1 md:col-span-2 lg:col-span-2">
						<SortFilter
							// TODO
							value={undefined}
							onSelect={() => {}}
						/>
					</div>
				</div>

				<DataTable table={table} />
			</div>
			<DeleteConfirmationDialog {...deleteConfirmationDialogState} />
		</>
	);
};
