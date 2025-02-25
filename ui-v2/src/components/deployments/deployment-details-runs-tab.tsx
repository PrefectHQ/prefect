import { Deployment } from "@/api/deployments";
import { useFilterFlowRunswithFlows } from "@/api/flow-runs/use-filter-flow-runs-with-flows";
import { FlowRunCard } from "@/components/flow-runs/flow-run-card";
import { Typography } from "@/components/ui/typography";
import { useMemo } from "react";

type DeploymentDetailsRunsTabProps = {
	deployment: Deployment;
};

export const DeploymentDetailsRunsTab = ({
	deployment,
}: DeploymentDetailsRunsTabProps) => {
	const nextRun = useGetNextRun(deployment);

	return (
		<div className="flex flex-col">
			{nextRun && (
				<div className="flex flex-col gap-2 border-b py-2">
					<Typography variant="bodyLarge">Next Run</Typography>
					<FlowRunCard flowRun={nextRun} />
				</div>
			)}
		</div>
	);
};

function useGetNextRun(deployment: Deployment) {
	const { data } = useFilterFlowRunswithFlows({
		deployments: { id: { any_: [deployment.id] }, operator: "and_" },
		flow_runs: {
			state: { name: { any_: ["Scheduled"] }, operator: "and_" },
			operator: "and_",
		},
		sort: "NAME_ASC",
		limit: 1,
		offset: 0,
	});

	return useMemo(() => {
		if (!data || !data[0]) {
			return undefined;
		}
		return {
			...data[0],
			deployment,
		};
	}, [data, deployment]);
}
