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
});
