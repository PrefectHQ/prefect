import { useQueries } from "@tanstack/react-query";
import { type Automation, buildGetAutomationQuery } from "@/api/automations";
import { buildListFilterBlockDocumentsQuery } from "@/api/block-documents";
import { buildFilterDeploymentsQuery } from "@/api/deployments";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { buildFilterWorkQueuesQuery } from "@/api/work-queues";

/**
 *
 * @param automation
 * @returns an object of maps to get information about an action's selected source (automations, deployments, work pools, and work queues)
 *
 * @example
 * ```ts
 * const { loading, data } = useGetAutomationActionResources(MY_AUTOMATION);
 *
 *
 * if (loading) {
 *   return "Loading..."
 * }
 *
 * const { automationsMap, blockDocumentsMap, deploymentsMap, workPoolsMap, workQueuesMap } = data
 * return (
 * 		<ActionDetails
 *			automation={MY_AUTOMATION}
 *			automations={automationsMap}
 *			blockDocumentsMap={blockDocumentsMap}
 *			deployments={deploymentsMap}
 *			workPools={workPoolsMap}
 *			workQueues={workQueuesMap}
 *		/>)
 * ```
 */
export const useGetAutomationActionResources = (automation: Automation) => {
	const {
		automationIds,
		blockDocumentIds,
		deploymentIds,
		workPoolIds,
		workQueueIds,
	} = getResourceSets(automation.actions);

	// nb: Automations /filter doesn't support `id`. Need to do it per GET call
	const { data: automationsData, loading: automationsLoading } =
		useListAutomationsQueries(Array.from(automationIds));

	// Need to do deployments filter API
	const remainingQueries = useQueries({
		queries: [
			buildListFilterBlockDocumentsQuery(
				{
					offset: 0,
					sort: "BLOCK_TYPE_AND_NAME_ASC",
					include_secrets: false,
					block_documents: {
						operator: "and_",
						id: { any_: Array.from(blockDocumentIds) },
						is_anonymous: {},
					},
				},
				{ enabled: blockDocumentIds.size > 0 },
			),
			buildFilterDeploymentsQuery(
				{
					offset: 0,
					sort: "CREATED_DESC",
					deployments: {
						id: { any_: Array.from(deploymentIds) },
						operator: "and_",
					},
				},
				{ enabled: deploymentIds.size > 0 },
			),
			buildFilterWorkPoolsQuery(
				{
					offset: 0,
					work_pools: {
						id: { any_: Array.from(workPoolIds) },
						operator: "and_",
					},
				},
				{ enabled: workPoolIds.size > 0 },
			),
			buildFilterWorkQueuesQuery(
				{
					offset: 0,
					work_queues: {
						id: { any_: Array.from(workQueueIds) },
						operator: "and_",
					},
				},
				{ enabled: workQueueIds.size > 0 },
			),
		],
		combine: (results) => {
			const [blockDocuments, deployments, workPools, workQueues] = results;
			return {
				data: {
					blockDocuments: blockDocuments.data,
					deployments: deployments.data,
					workPools: workPools.data,
					workQueues: workQueues.data,
				},
				loading: results.some((result) => result.isLoading),
			};
		},
	});

	return {
		loading: automationsLoading || remainingQueries.loading,
		data: {
			automationsMap: automationsData,
			blockDocumentsMap: listToMap(remainingQueries.data.blockDocuments),
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
			for (const result of results) {
				if (result.data) {
					retMap.set(result.data.id, result.data);
				}
			}
			return {
				data: retMap,
				loading: results.some((result) => result.isLoading),
			};
		},
	});

export const getResourceSets = (actions: Automation["actions"]) => {
	const automationIds = new Set<string>();
	const blockDocumentIds = new Set<string>();
	const deploymentIds = new Set<string>();
	const workPoolIds = new Set<string>();
	const workQueueIds = new Set<string>();

	for (const action of actions) {
		switch (action.type) {
			case "run-deployment":
			case "pause-deployment":
			case "resume-deployment":
				if (action.deployment_id) {
					deploymentIds.add(action.deployment_id);
				}
				break;
			case "pause-work-queue":
			case "resume-work-queue":
				if (action.work_queue_id) {
					workQueueIds.add(action.work_queue_id);
				}
				break;
			case "pause-automation":
			case "resume-automation":
				if (action.automation_id) {
					automationIds.add(action.automation_id);
				}
				break;
			case "pause-work-pool":
			case "resume-work-pool":
				if (action.work_pool_id) {
					workPoolIds.add(action.work_pool_id);
				}
				break;
			case "send-notification":
			case "call-webhook":
				if (action.block_document_id) {
					blockDocumentIds.add(action.block_document_id);
				}
				break;
			// TODO: add these back when the corresponding actions are implemented
			// case "do-nothing":
			// case "cancel-flow-run":
			// case "change-flow-run-state":
			// case "suspend-flow-run":
			// case "resume-flow-run":
		}
	}

	return {
		automationIds,
		blockDocumentIds,
		deploymentIds,
		workPoolIds,
		workQueueIds,
	};
};

function listToMap<T extends { id: string }>(
	list: T[] | undefined,
): Map<T["id"], T> {
	const map = new Map<T["id"], T>();
	for (const item of list ?? []) {
		map.set(item.id, item);
	}
	return map;
}
