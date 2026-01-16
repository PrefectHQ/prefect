import { useQuery } from "@tanstack/react-query";
import type { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { WorkPoolIconText } from "@/components/work-pools/work-pool-icon-text";

type FlowRun = components["schemas"]["FlowRunResponse"];

export const DeploymentCell = ({ row }: { row: { original: FlowRun } }) => {
	const deploymentId = row.original.deployment_id;
	const { data: deployment } = useQuery({
		queryKey: ["deployment", deploymentId],
		queryFn: async () =>
			(await getQueryService()).GET("/deployments/{id}", {
				params: { path: { id: deploymentId as string } },
			}),
		enabled: !!deploymentId,
	});
	return deployment?.data?.name;
};

export const WorkPoolCell = ({ row }: { row: { original: FlowRun } }) => {
	const deploymentId = row.original.deployment_id;
	const { data: deployment } = useQuery({
		queryKey: ["deployment", deploymentId],
		queryFn: async () =>
			(await getQueryService()).GET("/deployments/{id}", {
				params: { path: { id: deploymentId as string } },
			}),
		enabled: !!deploymentId,
	});

	const workPoolName = deployment?.data?.work_pool_name;
	if (!workPoolName) {
		return null;
	}
	return <WorkPoolIconText workPoolName={workPoolName} />;
};
