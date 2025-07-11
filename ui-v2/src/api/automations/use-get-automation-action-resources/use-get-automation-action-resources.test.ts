import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import type { BlockDocument } from "@/api/block-documents";
import type { Deployment } from "@/api/deployments";
import type { WorkPool } from "@/api/work-pools";
import type { WorkQueue } from "@/api/work-queues";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import type { Automation } from "../automations";
import {
	getResourceSets,
	useGetAutomationActionResources,
} from "./use-get-automation-action-resources";

describe("getResourceSet", () => {
	it("returns sets for different automation sources", () => {
		// SETUP
		const MOCK_AUTOMATION = createFakeAutomation({
			actions: [
				{
					type: "send-notification",
					block_document_id: "block-document-id-0",
					body: "my body",
					subject: "my subject",
				},
				{
					type: "pause-automation",
					source: "selected",
					automation_id: "automation-id-0",
				},
				{
					type: "resume-automation",
					source: "selected",
					automation_id: "automation-id-1",
				},
				{
					type: "pause-deployment",
					source: "selected",
					deployment_id: "deployment-id-0",
				},
				{
					type: "resume-deployment",
					source: "selected",
					deployment_id: "deployment-id-1",
				},
				{
					type: "run-deployment",
					source: "selected",
					deployment_id: "deployment-id-2",
				},
				{
					type: "pause-work-pool",
					source: "selected",
					work_pool_id: "work-pool-id-0",
				},
				{
					type: "resume-work-pool",
					source: "selected",
					work_pool_id: "work-pool-id-1",
				},
				{
					type: "pause-work-queue",
					source: "selected",
					work_queue_id: "work-queue-id-0",
				},
				{
					type: "resume-work-queue",
					source: "selected",
					work_queue_id: "work-queue-id-1",
				},
			],
		});
		// TEST
		const RESULT = getResourceSets(MOCK_AUTOMATION.actions);

		// ASSERT
		const EXPECTED = {
			automationIds: new Set(["automation-id-0", "automation-id-1"]),
			blockDocumentIds: new Set(["block-document-id-0"]),
			deploymentIds: new Set([
				"deployment-id-0",
				"deployment-id-1",
				"deployment-id-2",
			]),
			workPoolIds: new Set(["work-pool-id-0", "work-pool-id-1"]),
			workQueueIds: new Set(["work-queue-id-0", "work-queue-id-1"]),
		};

		expect(RESULT).toEqual(EXPECTED);
	});
});

describe("useGetAutomationActionResources", () => {
	const mockSourcesAPI = ({
		automations,
		blockDocuments,
		deployments,
		workPools,
		workQueues,
	}: {
		automations: Array<Automation>;
		blockDocuments: Array<BlockDocument>;
		deployments: Array<Deployment>;
		workPools: Array<WorkPool>;
		workQueues: Array<WorkQueue>;
	}) => {
		server.use(
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blockDocuments);
			}),
			http.post(buildApiUrl("/deployments/filter"), () => {
				return HttpResponse.json(deployments);
			}),
			http.post(buildApiUrl("/work_pools/filter"), () => {
				return HttpResponse.json(workPools);
			}),
			http.post(buildApiUrl("/work_queues/filter"), () => {
				return HttpResponse.json(workQueues);
			}),
			...automations.map((automation) =>
				http.get(buildApiUrl("/automations/:id"), () => {
					return HttpResponse.json(automation);
				}),
			),
		);
	};

	const MOCK_AUTOMATION = createFakeAutomation({
		actions: [
			{
				type: "send-notification",
				block_document_id: "block-document-id-0",
				body: "my body",
				subject: "my subject",
			},
			{
				type: "pause-automation",
				source: "selected",
				automation_id: "automation-id-0",
			},
			{
				type: "pause-deployment",
				source: "selected",
				deployment_id: "deployment-id-0",
			},
			{
				type: "resume-deployment",
				source: "selected",
				deployment_id: "deployment-id-1",
			},
			{
				type: "run-deployment",
				source: "selected",
				deployment_id: "deployment-id-2",
			},
			{
				type: "pause-work-pool",
				source: "selected",
				work_pool_id: "work-pool-id-0",
			},
			{
				type: "resume-work-pool",
				source: "selected",
				work_pool_id: "work-pool-id-1",
			},
			{
				type: "pause-work-queue",
				source: "selected",
				work_queue_id: "work-queue-id-0",
			},
			{
				type: "resume-work-queue",
				source: "selected",
				work_queue_id: "work-queue-id-1",
			},
		],
	});

	const MOCK_AUTOMATION_0 = createFakeAutomation({ id: "automation-id-0" });

	const MOCK_BLOCK_DOCUMENT_0 = createFakeBlockDocument({
		id: "block-document-id-0",
	});

	const MOCK_DEPLOYMENT_0 = createFakeDeployment({ id: "deployment-id-0" });
	const MOCK_DEPLOYMENT_1 = createFakeDeployment({ id: "deployment-id-1" });
	const MOCK_DEPLOYMENT_2 = createFakeDeployment({ id: "deployment-id-2" });

	const MOCK_WORK_POOL_0 = createFakeWorkPool({ id: "automation-id-0" });
	const MOCK_WORK_POOL_1 = createFakeWorkPool({ id: "automation-id-1" });

	const MOCK_WORK_QUEUE_0 = createFakeWorkQueue({ id: "automation-id-0" });
	const MOCK_WORK_QUEUE_1 = createFakeWorkQueue({ id: "automation-id-1" });

	it("returns maps of the different sources used in an automation", async () => {
		// SETUP
		const queryClient = new QueryClient();
		mockSourcesAPI({
			automations: [MOCK_AUTOMATION_0],
			blockDocuments: [MOCK_BLOCK_DOCUMENT_0],
			deployments: [MOCK_DEPLOYMENT_0, MOCK_DEPLOYMENT_1, MOCK_DEPLOYMENT_2],
			workPools: [MOCK_WORK_POOL_0, MOCK_WORK_POOL_1],
			workQueues: [MOCK_WORK_QUEUE_0, MOCK_WORK_QUEUE_1],
		});

		// TEST
		const { result } = renderHook(
			() => useGetAutomationActionResources(MOCK_AUTOMATION),
			{ wrapper: createWrapper({ queryClient }) },
		);

		await waitFor(() => expect(result.current.loading).toBe(false));

		// ASSERT
		const EXPECTED = {
			automationsMap: new Map<string, Automation>([
				[MOCK_AUTOMATION_0.id, MOCK_AUTOMATION_0],
			]),
			blockDocumentsMap: new Map<string, BlockDocument>([
				[MOCK_BLOCK_DOCUMENT_0.id, MOCK_BLOCK_DOCUMENT_0],
			]),
			deploymentsMap: new Map<string, Deployment>([
				[MOCK_DEPLOYMENT_0.id, MOCK_DEPLOYMENT_0],
				[MOCK_DEPLOYMENT_1.id, MOCK_DEPLOYMENT_1],
				[MOCK_DEPLOYMENT_2.id, MOCK_DEPLOYMENT_2],
			]),
			workPoolsMap: new Map<string, WorkPool>([
				[MOCK_WORK_POOL_0.id, MOCK_WORK_POOL_0],
				[MOCK_WORK_POOL_1.id, MOCK_WORK_POOL_1],
			]),
			workQueuesMap: new Map<string, WorkQueue>([
				[MOCK_WORK_QUEUE_0.id, MOCK_WORK_QUEUE_0],
				[MOCK_WORK_QUEUE_1.id, MOCK_WORK_QUEUE_1],
			]),
		};

		expect(result.current.data).toEqual(EXPECTED);
	});
});
