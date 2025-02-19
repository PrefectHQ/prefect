import type { Deployment } from "@/api/deployments";
import {
	FlowRun,
	type FlowRunWithDeploymentAndFlow,
	type FlowRunWithFlow,
} from "@/api/flow-runs";
import { DataTable } from "@/components/ui/data-table";
import { StateBadge } from "@/components/ui/state-badge";
import { TagBadgeGroup } from "@/components/ui/tag-badge-group";
import {
	createColumnHelper,
	getCoreRowModel,
	getPaginationRowModel,
	useReactTable,
} from "@tanstack/react-table";
import { useMemo } from "react";

import { Flow } from "@/api/flows";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";
import { DeploymentCell } from "./deployment-cell";
import { DurationCell } from "./duration-cell";
import { NameCell } from "./name-cell";
import { ParametersCell } from "./parameters-cell";
import { RunNameSearch } from "./run-name-search";
import { SortFilter } from "./sort-filter";
import { StartTimeCell } from "./start-time-cell";
import { StateFilter } from "./state-filter";

export type FlowRunsDataTableRow = FlowRun & {
	flow: Flow;
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

type FlowRunsDataTableProps = {
	flowRunsCount: number;
	flowRuns: Array<FlowRunWithDeploymentAndFlow | FlowRunWithFlow>;
};
export const FlowRunsDataTable = ({
	flowRunsCount,
	flowRuns,
}: FlowRunsDataTableProps) => {
	const showDeployment = useMemo(
		() => flowRuns.some((flowRun) => "deployment" in flowRun),
		[flowRuns],
	);

	const table = useReactTable({
		data: flowRuns,
		columns: createColumns({
			showDeployment,
		}),
		getCoreRowModel: getCoreRowModel(),
		getPaginationRowModel: getPaginationRowModel(), // TODO: use server-side pagination
	});

	return (
		<div>
			<div className="grid sm:grid-cols-2 md:grid-cols-6 lg:grid-cols-12 gap-2 pb-4 items-center">
				<div className="sm:col-span-2 md:col-span-6 lg:col-span-4 order-last lg:order-first">
					<Typography variant="bodySmall" className="text-muted-foreground">
						{flowRunsCount} {pluralize(flowRunsCount, "Flow run")}
					</Typography>
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
	);
};
