import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { createFakeWorkQueue } from "@/mocks";
import {
	TriggerDetailsWorkQueueStatus,
	type TriggerDetailsWorkQueueStatusProps,
} from "./trigger-details-work-queue-status";
import { getWorkQueueStatusLabel } from "./trigger-utils";

const TriggerDetailsWorkQueueStatusRouter = (
	props: TriggerDetailsWorkQueueStatusProps,
) => {
	const rootRoute = createRootRoute({
		component: () => <TriggerDetailsWorkQueueStatus {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("TriggerDetailsWorkQueueStatus", () => {
	const mockWorkQueueAPI = (
		workQueues: Array<{ id: string; name: string; work_pool_name: string }>,
	) => {
		for (const workQueue of workQueues) {
			const fakeWorkQueue = createFakeWorkQueue({
				id: workQueue.id,
				name: workQueue.name,
				work_pool_name: workQueue.work_pool_name,
			});
			server.use(
				http.get(buildApiUrl(`/work_queues/${workQueue.id}`), () => {
					return HttpResponse.json(fakeWorkQueue);
				}),
				http.get(
					buildApiUrl(
						`/work_pools/${workQueue.work_pool_name}/queues/${workQueue.name}`,
					),
					() => {
						return HttpResponse.json(fakeWorkQueue);
					},
				),
			);
		}
	};

	describe("rendering", () => {
		it("renders 'any work queue' when workQueueIds is empty", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("When")).toBeInTheDocument();
				expect(screen.getByText("any work queue")).toBeInTheDocument();
			});
		});

		it("renders work queue links when workQueueIds are provided", async () => {
			mockWorkQueueAPI([
				{ id: "queue-1", name: "default", work_pool_name: "my-pool" },
			]);

			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={["queue-1"]}
					workPoolNames={["my-pool"]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("work queue")).toBeInTheDocument();
			});
		});

		it("renders work pool links when workPoolNames are provided", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={["my-pool"]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("from the work pool")).toBeInTheDocument();
			});
		});

		it("does not render work pool section when workPoolNames is empty", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("When")).toBeInTheDocument();
			});

			expect(screen.queryByText(/from the work pool/)).not.toBeInTheDocument();
		});
	});

	describe("posture labels", () => {
		it("renders 'enters' for Reactive posture", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("enters")).toBeInTheDocument();
			});
		});

		it("renders 'stays in' for Proactive posture", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Proactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("stays in")).toBeInTheDocument();
			});
		});
	});

	describe("status labels", () => {
		it("renders 'ready' for READY status", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("ready")).toBeInTheDocument();
			});
		});

		it("renders 'not ready' for NOT_READY status", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="NOT_READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("not ready")).toBeInTheDocument();
			});
		});

		it("renders 'paused' for PAUSED status", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="PAUSED"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("paused")).toBeInTheDocument();
			});
		});
	});

	describe("time display", () => {
		it("renders time for Proactive posture when time is provided", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Proactive"
					status="READY"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
			});
		});

		it("does not render time for Reactive posture even when time is provided", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Reactive"
					status="READY"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("enters")).toBeInTheDocument();
			});

			expect(screen.queryByText(/for 30 seconds/)).not.toBeInTheDocument();
		});

		it("does not render time for Proactive posture when time is not provided", async () => {
			render(
				<TriggerDetailsWorkQueueStatusRouter
					workQueueIds={[]}
					workPoolNames={[]}
					posture="Proactive"
					status="READY"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("stays in")).toBeInTheDocument();
			});

			expect(screen.queryByText(/for/)).not.toBeInTheDocument();
		});
	});
});

describe("getWorkQueueStatusLabel", () => {
	it("returns 'Ready' for READY status", () => {
		expect(getWorkQueueStatusLabel("READY")).toBe("Ready");
	});

	it("returns 'Not Ready' for NOT_READY status", () => {
		expect(getWorkQueueStatusLabel("NOT_READY")).toBe("Not Ready");
	});

	it("returns 'Paused' for PAUSED status", () => {
		expect(getWorkQueueStatusLabel("PAUSED")).toBe("Paused");
	});
});
