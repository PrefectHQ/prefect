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
import { DeploymentCell } from "./deployment-cell";
import { DurationCell } from "./duration-cell";
import { NameCell } from "./name-cell";
import { ParametersCell } from "./parameters-cell";

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
	flowRuns: Array<FlowRunWithDeploymentAndFlow | FlowRunWithFlow>;
};
export const FlowRunsDataTable = ({ flowRuns }: FlowRunsDataTableProps) => {
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
		<div className="flex flex-col gap-4">
			<DataTable table={table} />
		</div>
	);
};
