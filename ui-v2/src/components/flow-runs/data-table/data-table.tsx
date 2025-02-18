import {
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

import type { Deployment } from "@/api/deployments";
import { useMemo } from "react";
import { DeploymentCell } from "./deployment-cell";
import { NameCell } from "./name-cell";
import { ParametersCell } from "./parameters-cell";
import { RunTimeCell } from "./run-time-cell";

const columnHelper = createColumnHelper<
	FlowRunWithDeploymentAndFlow | FlowRunWithFlow
>();

const createColumns = ({
	showDeployment,
}: {
	showDeployment: boolean;
}) => {
	let ret = [
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
					throw new Error("Expecting 'state'");
				}
				return <StateBadge type={state.type} name={state.name} />;
			},
		}),
		columnHelper.display({
			id: "schedule",
			header: "Schedule",
			cell: ({ row }) => <RunTimeCell flowRun={row.original} />,
		}),
		columnHelper.accessor("parameters", {
			id: "parameters",
			header: "Parameters",
			cell: ParametersCell,
		}),
		columnHelper.accessor("deployment", {
			id: "deployment",
			header: "Deployment",
			cell: (props) => {
				const deployment = props.getValue() as Deployment;
				return <DeploymentCell deployment={deployment} />;
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
	if (!showDeployment) {
		ret = ret.filter((column) => column.id !== "deployment");
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
		getPaginationRowModel: getPaginationRowModel(), //load client-side pagination code
	});

	return (
		<div className="flex flex-col gap-4">
			<DataTable table={table} />
		</div>
	);
};
