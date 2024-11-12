import { components } from "@/api/prefect";
import { createQueryService } from "@/api/service";
import { useQuery } from "@tanstack/react-query";

type FlowRun = components["schemas"]["FlowRun"];

export const DeploymentCell = ({ row }: { row: { original: FlowRun } }) => {
	const deploymentId = row.original.deployment_id;
	const { data: deployment } = useQuery({
		queryKey: ["deployment", deploymentId],
		queryFn: () =>
			createQueryService().GET("/deployments/{id}", {
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
		queryFn: () =>
			createQueryService().GET("/deployments/{id}", {
				params: { path: { id: deploymentId as string } },
			}),
		enabled: !!deploymentId,
	});

	return deployment?.data?.work_pool_name;
};
