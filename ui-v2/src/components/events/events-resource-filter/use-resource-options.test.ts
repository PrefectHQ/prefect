import { QueryClient } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { useResourceOptions } from "./use-resource-options";

describe("useResourceOptions", () => {
	const mockResourcesAPI = ({
		automations = [],
		blockDocuments = [],
		deployments = [],
		flows = [],
		workPools = [],
		workQueues = [],
	}: {
		automations?: ReturnType<typeof createFakeAutomation>[];
		blockDocuments?: ReturnType<typeof createFakeBlockDocument>[];
		deployments?: ReturnType<typeof createFakeDeployment>[];
		flows?: ReturnType<typeof createFakeFlow>[];
		workPools?: ReturnType<typeof createFakeWorkPool>[];
		workQueues?: ReturnType<typeof createFakeWorkQueue>[];
	} = {}) => {
		server.use(
			http.post(buildApiUrl("/automations/filter"), () => {
				return HttpResponse.json(automations);
			}),
			http.post(buildApiUrl("/block_documents/filter"), () => {
				return HttpResponse.json(blockDocuments);
			}),
			http.post(buildApiUrl("/deployments/filter"), () => {
				return HttpResponse.json(deployments);
			}),
			http.post(buildApiUrl("/flows/filter"), () => {
				return HttpResponse.json(flows);
			}),
			http.post(buildApiUrl("/work_pools/filter"), () => {
				return HttpResponse.json(workPools);
			}),
			http.post(buildApiUrl("/work_queues/filter"), () => {
				return HttpResponse.json(workQueues);
			}),
		);
	};

	it("returns empty array when no resources exist", async () => {
		mockResourcesAPI();
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toEqual([]);
		});
	});

	it("transforms automations into resource options", async () => {
		const automation = createFakeAutomation({
			id: "automation-1",
			name: "Test Automation",
		});
		mockResourcesAPI({ automations: [automation] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "automation-1",
				name: "Test Automation",
				type: "automation",
				resourceId: "prefect.automation.automation-1",
			});
		});
	});

	it("transforms block documents into resource options", async () => {
		const blockDocument = createFakeBlockDocument({
			id: "block-1",
			name: "Test Block",
		});
		mockResourcesAPI({ blockDocuments: [blockDocument] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "block-1",
				name: "Test Block",
				type: "block",
				resourceId: "prefect.block-document.block-1",
			});
		});
	});

	it("transforms deployments into resource options", async () => {
		const deployment = createFakeDeployment({
			id: "deployment-1",
			name: "Test Deployment",
		});
		mockResourcesAPI({ deployments: [deployment] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "deployment-1",
				name: "Test Deployment",
				type: "deployment",
				resourceId: "prefect.deployment.deployment-1",
			});
		});
	});

	it("transforms flows into resource options", async () => {
		const flow = createFakeFlow({
			id: "flow-1",
			name: "Test Flow",
		});
		mockResourcesAPI({ flows: [flow] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "flow-1",
				name: "Test Flow",
				type: "flow",
				resourceId: "prefect.flow.flow-1",
			});
		});
	});

	it("transforms work pools into resource options using name for id and resourceId", async () => {
		const workPool = createFakeWorkPool({
			id: "work-pool-uuid-1",
			name: "my-work-pool",
		});
		mockResourcesAPI({ workPools: [workPool] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "my-work-pool",
				name: "my-work-pool",
				type: "work-pool",
				resourceId: "prefect.work-pool.my-work-pool",
			});
		});
	});

	it("transforms work queues into resource options", async () => {
		const workQueue = createFakeWorkQueue({
			id: "work-queue-1",
			name: "Test Work Queue",
		});
		mockResourcesAPI({ workQueues: [workQueue] });
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toContainEqual({
				id: "work-queue-1",
				name: "Test Work Queue",
				type: "work-queue",
				resourceId: "prefect.work-queue.work-queue-1",
			});
		});
	});

	it("combines all resource types into a single array", async () => {
		const automation = createFakeAutomation({
			id: "auto-1",
			name: "Automation 1",
		});
		const blockDocument = createFakeBlockDocument({
			id: "block-1",
			name: "Block 1",
		});
		const deployment = createFakeDeployment({
			id: "deploy-1",
			name: "Deployment 1",
		});
		const flow = createFakeFlow({ id: "flow-1", name: "Flow 1" });
		const workPool = createFakeWorkPool({
			id: "wp-uuid-1",
			name: "work-pool-1",
		});
		const workQueue = createFakeWorkQueue({
			id: "wq-1",
			name: "Work Queue 1",
		});

		mockResourcesAPI({
			automations: [automation],
			blockDocuments: [blockDocument],
			deployments: [deployment],
			flows: [flow],
			workPools: [workPool],
			workQueues: [workQueue],
		});
		const queryClient = new QueryClient();

		const { result } = renderHook(() => useResourceOptions(), {
			wrapper: createWrapper({ queryClient }),
		});

		await waitFor(() => {
			expect(result.current.resourceOptions).toHaveLength(6);
			expect(result.current.resourceOptions.map((r) => r.type)).toEqual(
				expect.arrayContaining([
					"automation",
					"block",
					"deployment",
					"flow",
					"work-pool",
					"work-queue",
				]),
			);
		});
	});
});
