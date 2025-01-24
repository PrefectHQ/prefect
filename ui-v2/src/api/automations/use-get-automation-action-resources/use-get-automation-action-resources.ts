import { Automation, buildGetAutomationQuery } from "@/api/automations";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { buildFilterWorkQueuesQuery } from "@/api/work-queues";
import { useQueries } from "@tanstack/react-query";

// TODO: Add to this hooks to support blocks and other missing sources

/**
 *
 * @param automation
 * @returns an object of maps to get information about an action's selected source (automations, deployments, work pools, and work queues)
 *
 * @example
 * ```ts
 * const { pending, data } = useGetAutomationActionResources(MY_AUTOMATION);
 *
 *
 * if (pending) {
 *   return "Loading..."
 * }
 *
 * const { automationsMap, deploymentsMap, workPoolsMap, workQueuesMap } = data
 * return (
 * 		<ActionDetails
 *			automation={MY_AUTOMATION}
 *			automations={automationsMap}
 *			deployments={deploymentsMap}
 *			workPools={workPoolsMap}
 *			workQueues={workQueuesMap}
 *		/>)
 * ```
 */
export const useGetAutomationActionResources = (automation: Automation) => {
	const { automationIds, deploymentIds, workPoolIds, workQueueIds } =
		getResourceSets(automation.actions);

	// nb: Automations /filter doesn't support `id`. Need to do it per GET call
	const { data: automationsData, pending: automationsPending } =
		useListAutomationsQueries(Array.from(automationIds));

	// Need to do deployments filter API
	const remainingQueries = useQueries({
		queries: [
			buildFilterDeploymentsQuery({
				offset: 0,
				sort: "CREATED_DESC",
				deployments: {
					id: { any_: Array.from(deploymentIds) },
					operator: "and_",
				},
			}),
			buildFilterWorkPoolsQuery({
				offset: 0,
				work_pools: {
					id: { any_: Array.from(workPoolIds) },
					operator: "and_",
				},
			}),
			buildFilterWorkQueuesQuery({
				offset: 0,
				work_queues: {
					id: { any_: Array.from(workQueueIds) },
					operator: "and_",
				},
			}),
		],
		combine: (results) => {
			const [deployments, workPools, workQueues] = results;
			return {
				data: {
					deployments: deployments.data,
					workPools: workPools.data,
					workQueues: workQueues.data,
				},
				pending: results.some((result) => result.isPending),
			};
		},
	});

	return {
		pending: automationsPending || remainingQueries.pending,
		data: {
			automationsMap: automationsData,
			deploymentsMap: listToMap(remainingQueries.data.deployments),
			workPoolsMap: listToMap(remainingQueries.data.workPools),
			workQueuesMap: listToMap(remainingQueries.data.workQueues),
		},
	};
};

const useListAutomationsQueries = (automationIds: Array<string>) =>
	useQueries({
		queries: Array.from(automationIds).map((automationId) =>
			buildGetAutomationQuery(automationId),
		),
		combine: (results) => {
			const retMap = new Map<string, Automation>();
			results.forEach((result) => {
				if (result.data) {
					retMap.set(result.data.id, result.data);
				}
			});
			return {
				data: retMap,
				pending: results.some((result) => result.isPending),
			};
		},
	});

export const getResourceSets = (actions: Automation["actions"]) => {
	const automationIds = new Set<string>();
	const deploymentIds = new Set<string>();
	const workPoolIds = new Set<string>();
	const workQueueIds = new Set<string>();

	actions.forEach((action) => {
		switch (action.type) {
			case "run-deployment":
			case "pause-deployment":
			case "resume-deployment":
				if (action.deployment_id) {
					deploymentIds.add(action.deployment_id);
				}
				return;
			case "pause-work-queue":
			case "resume-work-queue":
				if (action.work_queue_id) {
					workQueueIds.add(action.work_queue_id);
				}
				return;
			case "pause-automation":
			case "resume-automation":
				if (action.automation_id) {
					automationIds.add(action.automation_id);
				}
				return;
			case "pause-work-pool":
			case "resume-work-pool":
				if (action.work_pool_id) {
					workPoolIds.add(action.work_pool_id);
				}
				return;
			case "do-nothing":
			case "cancel-flow-run":
			case "change-flow-run-state":
			case "send-notification":
			case "call-webhook":
			case "suspend-flow-run":
			case "resume-flow-run":
			default:
				return;
		}
	});

	return {
		automationIds,
		deploymentIds,
		workPoolIds,
		workQueueIds,
	};
};

function listToMap<T extends { id: string }>(
	list: T[] | undefined,
): Map<T["id"], T> {
	const map = new Map<T["id"], T>();
	list?.forEach((item) => {
		map.set(item.id, item);
	});
	return map;
}
