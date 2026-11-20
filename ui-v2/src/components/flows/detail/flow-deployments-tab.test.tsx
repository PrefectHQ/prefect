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
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeDeployment } from "@/mocks/create-fake-deployment";
import { FlowDeploymentsTab } from "./flow-deployments-tab";

describe("FlowDeploymentsTab", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => HttpResponse.json([])),
			http.post(buildApiUrl("/ui/flow_runs/history"), () =>
				HttpResponse.json([]),
			),
		);
	});

	const deployment = createFakeDeployment({ name: "Test Deployment" });

	const defaultProps = {
		deployments: [deployment],
		deploymentsCount: 1,
		totalDeploymentsCount: 1,
		deploymentsPages: 1,
		deploymentSearch: undefined,
		onDeploymentSearchChange: vi.fn(),
		deploymentTags: [],
		onDeploymentTagsChange: vi.fn(),
		deploymentSort: "NAME_ASC" as const,
		onDeploymentSortChange: vi.fn(),
		deploymentPagination: { page: 1, limit: 10 },
		onDeploymentPaginationChange: vi.fn(),
		onClearFilters: vi.fn(),
	};

	const renderTab = () => {
		const rootRoute = createRootRoute({
			component: () => <FlowDeploymentsTab {...defaultProps} />,
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient: new QueryClient() },
		});

		return render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		});
	};

	it("links deployment names to the deployment details page", async () => {
		renderTab();

		await waitFor(() => {
			expect(
				screen.getByRole("link", { name: "Test Deployment" }),
			).toHaveAttribute("href", `/deployments/deployment/${deployment.id}`);
		});
	});

	it("limits deployment activity runs to the charted window so future scheduled runs don't crowd out recent runs", async () => {
		const activityRequests: {
			flow_runs?: {
				start_time?: { after_?: string; before_?: string };
			};
		}[] = [];
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), async ({ request }) => {
				const body = (await request.json()) as {
					deployments?: { id?: { any_?: string[] } };
				};
				if (body.deployments?.id?.any_?.includes(deployment.id)) {
					activityRequests.push(body as (typeof activityRequests)[number]);
				}
				return HttpResponse.json([]);
			}),
		);

		const before = Date.now();
		renderTab();

		await waitFor(() => expect(activityRequests.length).toBeGreaterThan(0));

		const window = activityRequests[0].flow_runs?.start_time;
		const after = new Date(window?.after_ ?? "").getTime();
		const beforeTime = new Date(window?.before_ ?? "").getTime();
		expect(beforeTime).toBeGreaterThanOrEqual(before - 1000);
		expect(beforeTime).toBeLessThanOrEqual(Date.now());
		expect(beforeTime - after).toBe(7 * 24 * 60 * 60 * 1000);
	});

	it("shows NOT_READY status even when paused is true", async () => {
		const pausedDeployment = createFakeDeployment({
			paused: true,
			status: "NOT_READY",
			schedules: [],
		});

		const rootRoute = createRootRoute({
			component: () => (
				<FlowDeploymentsTab
					{...defaultProps}
					deployments={[pausedDeployment]}
				/>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient: new QueryClient() },
		});

		render(<RouterProvider router={router} />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getByText("Not Ready")).toBeInTheDocument();
			expect(screen.queryByText("Paused")).not.toBeInTheDocument();
		});
	});

	it("shows None when status is missing", async () => {
		const noStatusDeployment = createFakeDeployment({ status: undefined });

		const rootRoute = createRootRoute({
			component: () => (
				<FlowDeploymentsTab
					{...defaultProps}
					deployments={[noStatusDeployment]}
				/>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({ initialEntries: ["/"] }),
			context: { queryClient: new QueryClient() },
		});

		render(<RouterProvider router={router} />, { wrapper: createWrapper() });

		await waitFor(() => {
			expect(screen.getByText("None")).toBeInTheDocument();
		});
	});
});
