import { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useQuery } from "@tanstack/react-query";

type UseFlowRunsOptions =
	components["schemas"]["Body_read_flow_runs_flow_runs_filter_post"];

export const useFlowRuns = (options?: UseFlowRunsOptions) => {
	return useQuery({
		queryKey: ["flow-runs"],
		queryFn: async () => {
			const response = await getQueryService().POST("/flow_runs/filter", {
				body: options,
			});
			return response.data;
		},
	});
};
