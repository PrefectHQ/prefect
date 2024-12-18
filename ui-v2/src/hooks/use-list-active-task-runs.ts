import { components } from "@/api/prefect";
import { getQueryService } from "@/api/service";
import { useQueries } from "@tanstack/react-query";

/**
 *
 * @param activeSlots
 * @returns A list of queries, used to populate the concurrency limit active task runs list
 *
 * ```tsx
 * 	const activeTaskRuns = useListActiveTaskRuns(active_slots);
 *
 *
 *  return activeTaskRuns.map((activeTaskRun) => {
 *		const { data } = activeTaskRun;
 *			return (
 *				<li key={data.taskRun.id}>
 *					<ConcurrencyLimitTaskRunCard
 *						flow={data.flow}
 *						flowRun={data.flowRun}
 *						taskRun={data.taskRun}
 *					/>
 *				</li>
 *		}
 * ```
 */
export const useListActiveTaskRuns = (activeSlots: Array<string> = []) => {
	return useQueries({
		queries: activeSlots.map((activeSlot) => ({
			queryKey: ["active-task-runs", activeSlot] as const,
			queryFn: async () => {
				const taskRun = await getQueryService().GET("/task_runs/{id}", {
					params: { path: { id: activeSlot } },
				});
				if (!taskRun.data || !taskRun.data.flow_run_id) {
					throw new Error("'flow_run_id' expected");
				}
				const flowRun = await getQueryService().GET("/flow_runs/{id}", {
					params: { path: { id: taskRun.data.flow_run_id } },
				});
				if (!flowRun.data) {
					throw new Error("'data' expected");
				}
				const flow = await getQueryService().GET("/flows/{id}", {
					params: { path: { id: flowRun.data.flow_id } },
				});

				return {
					taskRun: taskRun.data,
					flowRun: flowRun.data,
					flow: flow.data as components["schemas"]["Flow"], // 'as' needed due to some schema typing issues
				};
			},
		})),
	});
};
