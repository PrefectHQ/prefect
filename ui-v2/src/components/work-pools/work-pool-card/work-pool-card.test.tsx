import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper, server } from "@tests/utils";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeWorkPool, createFakeWorkPoolWorker } from "@/mocks";
import { WorkPoolCard } from "./work-pool-card";

describe("WorkPoolCard", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	// Wraps component in test with a Tanstack router provider
	const WorkPoolCardRouter = ({
		workPool,
	}: {
		workPool: ReturnType<typeof createFakeWorkPool>;
	}) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<WorkPoolCard workPool={workPool} />
				</>
			),
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

	it("renders work pool name", async () => {
		const workPool = createFakeWorkPool({
			name: "my-test-work-pool",
			status: "READY",
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-test-work-pool")).toBeInTheDocument();
		});
	});

	it("renders 'Concurrency Limit' label with value when set", async () => {
		const workPool = createFakeWorkPool({
			name: "limited-work-pool",
			status: "READY",
			concurrency_limit: 10,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Concurrency Limit")).toBeInTheDocument();
			expect(screen.getByText("10")).toBeInTheDocument();
		});
	});

	it("renders 'Unlimited' when concurrency limit is not set", async () => {
		const workPool = createFakeWorkPool({
			name: "unlimited-work-pool",
			status: "READY",
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Concurrency Limit")).toBeInTheDocument();
			expect(screen.getByText("∞")).toBeInTheDocument();
		});
	});

	it("renders work pool type badge", async () => {
		const workPool = createFakeWorkPool({
			name: "process-work-pool",
			status: "READY",
			type: "process",
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Process")).toBeInTheDocument();
		});
	});

	it("renders 'Last Polled' when workers have heartbeats", async () => {
		const workPool = createFakeWorkPool({
			name: "polled-work-pool",
			status: "READY",
			concurrency_limit: null,
		});

		// Use a recent timestamp for the heartbeat
		const recentHeartbeat = new Date(Date.now() - 5 * 60 * 1000).toISOString();

		const mockWorkers = [
			createFakeWorkPoolWorker({
				name: "worker-1",
				last_heartbeat_time: recentHeartbeat,
			}),
		];

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json(mockWorkers);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Last Polled")).toBeInTheDocument();
		});
	});

	it("does not render 'Last Polled' when no workers have heartbeats", async () => {
		const workPool = createFakeWorkPool({
			name: "no-heartbeat-work-pool",
			status: "READY",
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("no-heartbeat-work-pool")).toBeInTheDocument();
		});

		expect(screen.queryByText("Last Polled")).not.toBeInTheDocument();
	});

	it("renders pause/resume toggle", async () => {
		const workPool = createFakeWorkPool({
			name: "toggle-work-pool",
			status: "READY",
			is_paused: false,
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const toggle = screen.getByRole("switch");
			expect(toggle).toBeInTheDocument();
			expect(toggle).toBeChecked();
		});
	});

	it("renders context menu button", async () => {
		const workPool = createFakeWorkPool({
			name: "menu-work-pool",
			status: "READY",
			concurrency_limit: null,
		});

		server.use(
			http.post(
				buildApiUrl(`/work_pools/${workPool.name}/workers/filter`),
				() => {
					return HttpResponse.json([]);
				},
			),
		);

		render(<WorkPoolCardRouter workPool={workPool} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const menuButton = screen.getByRole("button", { name: /open menu/i });
			expect(menuButton).toBeInTheDocument();
		});
	});
});
