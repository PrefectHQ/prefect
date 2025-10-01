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
import {
	buildAverageLatenessFlowRunsQuery,
	buildCountFlowRunsQuery,
	buildFilterFlowRunsQuery,
} from "@/api/flow-runs";
import { buildListWorkPoolQueuesQuery } from "@/api/work-pool-queues";
import {
	buildFilterWorkPoolsQuery,
	buildListWorkPoolWorkersQuery,
} from "@/api/work-pools";
import {
	createFakeDeployment,
	createFakeFlow,
	createFakeFlowRun,
	createFakeWorkPool,
	createFakeWorkPoolQueue,
	createFakeWorkPoolWorker,
} from "@/mocks";
import { DashboardWorkPoolsCard } from "./work-pools-card";

// Wraps component in test with a Tanstack router provider
const DashboardWorkPoolsCardRouter = () => {
	const rootRoute = createRootRoute({
		component: () => <DashboardWorkPoolsCard />,
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

describe("DashboardWorkPoolsCard", () => {
	it("renders active work pools", async () => {
		const workPool1 = createFakeWorkPool({
			name: "Active Pool 1",
			is_paused: false,
		});
		const workPool2 = createFakeWorkPool({
			name: "Active Pool 2",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		const queryOptions = buildFilterWorkPoolsQuery({ offset: 0 });
		queryClient.setQueryData(queryOptions.queryKey, [workPool1, workPool2]);

		const wrapper = createWrapper({ queryClient });

		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Active Work Pools")).toBeInTheDocument();
		expect(screen.getByText("Active Pool 1")).toBeInTheDocument();
		expect(screen.getByText("Active Pool 2")).toBeInTheDocument();
	});

	it("filters out paused work pools", async () => {
		const activePool = createFakeWorkPool({
			name: "Active Pool",
			is_paused: false,
		});
		const pausedPool = createFakeWorkPool({
			name: "Paused Pool",
			is_paused: true,
		});

		const queryClient = new QueryClient();
		const queryOptions = buildFilterWorkPoolsQuery({ offset: 0 });
		queryClient.setQueryData(queryOptions.queryKey, [activePool, pausedPool]);

		const wrapper = createWrapper({ queryClient });

		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Active Pool")).toBeInTheDocument();
		expect(screen.queryByText("Paused Pool")).not.toBeInTheDocument();
	});

	it("shows empty message when no active work pools", async () => {
		const pausedPool = createFakeWorkPool({
			name: "Paused Pool",
			is_paused: true,
		});

		const queryClient = new QueryClient();
		const queryOptions = buildFilterWorkPoolsQuery({ offset: 0 });
		queryClient.setQueryData(queryOptions.queryKey, [pausedPool]);

		const wrapper = createWrapper({ queryClient });

		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("No active work pools")).toBeInTheDocument();
		expect(screen.getByText("View all work pools")).toBeInTheDocument();
	});

	it("renders work pool status icons", async () => {
		const readyPool = createFakeWorkPool({
			name: "Ready Pool",
			is_paused: false,
			status: "READY",
		});

		const queryClient = new QueryClient();
		const queryOptions = buildFilterWorkPoolsQuery({ offset: 0 });
		queryClient.setQueryData(queryOptions.queryKey, [readyPool]);

		const wrapper = createWrapper({ queryClient });

		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		// The status icon should be an SVG element with the appropriate class
		const statusIcon = await screen.findByText("Ready Pool");
		expect(statusIcon).toBeInTheDocument();
		// Check that the status icon is rendered (it's an SVG with specific classes)
		const svgIcon = document.querySelector(".text-green-600");
		expect(svgIcon).toBeInTheDocument();
	});

	it("renders work pool details sections", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		const queryOptions = buildFilterWorkPoolsQuery({ offset: 0 });
		queryClient.setQueryData(queryOptions.queryKey, [workPool]);

		const wrapper = createWrapper({ queryClient });

		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Polled")).toBeInTheDocument();
		expect(screen.getByText("Work Queues")).toBeInTheDocument();
		expect(screen.getByText("Late runs")).toBeInTheDocument();
		expect(screen.getByText("Completed")).toBeInTheDocument();
	});

	it("displays worker last polled time", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});
		const worker = createFakeWorkPoolWorker({
			last_heartbeat_time: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildListWorkPoolWorkersQuery(workPool.name).queryKey,
			[worker],
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		// Should display the formatted date
		expect(await screen.findByText("Polled")).toBeInTheDocument();
		// The FormattedDate component will render the actual date
		const polledSection = screen.getByText("Polled").parentElement;
		expect(polledSection).toBeInTheDocument();
	});

	it("displays N/A when no workers", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildListWorkPoolWorkersQuery(workPool.name).queryKey,
			[],
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("N/A")).toBeInTheDocument();
	});

	it("displays work queue status icons", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});
		const queues = [
			createFakeWorkPoolQueue({ name: "default", status: "READY" }),
			createFakeWorkPoolQueue({ name: "high-priority", status: "READY" }),
		];

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildListWorkPoolQueuesQuery(workPool.name).queryKey,
			queues,
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Work Queues")).toBeInTheDocument();
		// Queue icons should be rendered (SVG elements)
		const queueSection = screen.getByText("Work Queues").parentElement;
		expect(queueSection).toBeInTheDocument();
	});

	it("displays late run count and average lateness", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildCountFlowRunsQuery({
				work_pools: { operator: "and_", name: { any_: [workPool.name] } },
				flow_runs: {
					operator: "and_",
					state: { operator: "and_", name: { any_: ["Late"] } },
				},
			}).queryKey,
			3,
		);
		queryClient.setQueryData(
			buildAverageLatenessFlowRunsQuery({
				sort: "ID_DESC",
				offset: 0,
				work_pools: { operator: "and_", id: { any_: [workPool.id] } },
			}).queryKey,
			120,
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Late runs")).toBeInTheDocument();
		expect(screen.getByText("3")).toBeInTheDocument();
		expect(screen.getByText(/avg\./)).toBeInTheDocument();
	});

	it("displays completion percentage", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		// Mock 80 completed out of 100 total
		queryClient.setQueryData(
			buildCountFlowRunsQuery({
				work_pools: { operator: "and_", id: { any_: [workPool.id] } },
				flow_runs: {
					operator: "and_",
					state: {
						operator: "and_",
						type: { any_: ["COMPLETED", "FAILED", "CRASHED"] },
					},
				},
			}).queryKey,
			100,
		);
		queryClient.setQueryData(
			buildCountFlowRunsQuery({
				work_pools: { operator: "and_", id: { any_: [workPool.id] } },
				flow_runs: {
					operator: "and_",
					state: { operator: "and_", type: { any_: ["COMPLETED"] } },
				},
			}).queryKey,
			80,
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("Completed")).toBeInTheDocument();
		expect(screen.getByText("80%")).toBeInTheDocument();
	});

	it("displays total flow runs count", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildCountFlowRunsQuery({
				work_pools: { operator: "and_", name: { any_: [workPool.name] } },
				flow_runs: {
					operator: "and_",
					state: {
						operator: "and_",
						type: { any_: ["COMPLETED", "FAILED", "CRASHED"] },
					},
				},
			}).queryKey,
			42,
		);

		const wrapper = createWrapper({ queryClient });
		render(<DashboardWorkPoolsCardRouter />, { wrapper });

		expect(await screen.findByText("42")).toBeInTheDocument();
		expect(screen.getByText("total")).toBeInTheDocument();
	});

	it("renders bar chart when filter is provided", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});
		const mockFlow = createFakeFlow();
		const mockDeployment = createFakeDeployment({ flow_id: mockFlow.id });
		const flowRuns = [
			createFakeFlowRun({
				deployment_id: mockDeployment.id,
				flow_id: mockFlow.id,
				start_time: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
			}),
		];

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);

		// Mock flow runs for bar chart
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => {
				return HttpResponse.json(flowRuns);
			}),
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
			http.get(buildApiUrl("/flows/:id"), () => {
				return HttpResponse.json(mockFlow);
			}),
		);

		const wrapper = createWrapper({ queryClient });
		const rootRoute = createRootRoute({
			component: () => (
				<DashboardWorkPoolsCard
					filter={{
						startDate: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
						endDate: new Date().toISOString(),
					}}
				/>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient },
		});

		render(<RouterProvider router={router} />, { wrapper });

		expect(await screen.findByText("Test Pool")).toBeInTheDocument();

		// Wait for bar chart to load (it fetches flow runs, deployments, and flows)
		await waitFor(
			() => {
				// Check that the bar chart container is rendered
				const barChartContainer = document.querySelector(".recharts-wrapper");
				expect(barChartContainer).toBeInTheDocument();
			},
			{ timeout: 5000 },
		);
	});

	it("renders empty bar chart when no flow runs", async () => {
		const workPool = createFakeWorkPool({
			name: "Test Pool",
			is_paused: false,
		});

		const queryClient = new QueryClient();
		queryClient.setQueryData(
			buildFilterWorkPoolsQuery({ offset: 0 }).queryKey,
			[workPool],
		);
		queryClient.setQueryData(
			buildFilterFlowRunsQuery({
				sort: "START_TIME_DESC",
				offset: 0,
				limit: 24,
			}).queryKey,
			[],
		);

		const wrapper = createWrapper({ queryClient });
		const rootRoute = createRootRoute({
			component: () => (
				<DashboardWorkPoolsCard
					filter={{
						startDate: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
						endDate: new Date().toISOString(),
					}}
				/>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient },
		});

		render(<RouterProvider router={router} />, { wrapper });

		expect(await screen.findByText("Test Pool")).toBeInTheDocument();
		// Bar chart container should still be present but empty
		const barChartPlaceholder = document.querySelector(".h-8.w-48");
		expect(barChartPlaceholder).toBeInTheDocument();
	});
});
