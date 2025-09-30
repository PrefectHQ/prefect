import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { buildFilterWorkPoolsQuery } from "@/api/work-pools";
import { createFakeWorkPool } from "@/mocks";
import { DashboardWorkPoolsCard } from "./dashboard-work-pools-card";

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

		expect(await screen.findByText("Work Pools")).toBeInTheDocument();
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
});
