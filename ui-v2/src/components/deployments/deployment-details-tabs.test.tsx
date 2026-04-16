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
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { DeploymentDetailsTabs } from "./deployment-details-tabs";

// Stub out the route API since TanStack Router's getRouteApi is evaluated at
// module load and requires a real route tree registration otherwise.
// @ts-expect-error Ignoring error until @tanstack/react-router has better testing documentation. Ref: https://vitest.dev/api/vi.html#vi-mock
vi.mock(import("@tanstack/react-router"), async (importOriginal) => {
	const mod = await importOriginal();
	return {
		...mod,
		getRouteApi: () => ({
			useSearch: () => ({ tab: "Description" }),
			useNavigate: () => vi.fn(),
		}),
	};
});

describe("DeploymentDetailsTabs", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/flow_runs/filter"), () => HttpResponse.json([])),
			http.post(buildApiUrl("/flow_runs/paginate"), () =>
				HttpResponse.json({
					results: [],
					count: 0,
					page: 1,
					pages: 1,
					limit: 10,
				}),
			),
			http.post(buildApiUrl("/flow_runs/count"), () => HttpResponse.json(0)),
			http.post(buildApiUrl("/flow_runs/history"), () => HttpResponse.json([])),
		);
	});

	const renderTabs = (deployment: Deployment) => {
		const rootRoute = createRootRoute({
			component: () => <DeploymentDetailsTabs deployment={deployment} />,
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

	it("shows Parameters and Configuration tabs for active deployments", async () => {
		renderTabs(createFakeDeployment({ entrypoint: "flows/etl.py:daily_etl" }));

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Runs" })).toBeInTheDocument();
		});

		expect(screen.getByRole("tab", { name: "Parameters" })).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: "Configuration" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: "Description" }),
		).toBeInTheDocument();
	});

	it("hides Parameters and Configuration tabs for deprecated deployments (null entrypoint)", async () => {
		renderTabs(createFakeDeployment({ entrypoint: null }));

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Runs" })).toBeInTheDocument();
		});

		expect(
			screen.queryByRole("tab", { name: "Parameters" }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("tab", { name: "Configuration" }),
		).not.toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: "Description" }),
		).toBeInTheDocument();
	});

	it("hides Parameters and Configuration tabs for deprecated deployments (empty entrypoint)", async () => {
		renderTabs(createFakeDeployment({ entrypoint: "" }));

		await waitFor(() => {
			expect(screen.getByRole("tab", { name: "Runs" })).toBeInTheDocument();
		});

		expect(
			screen.queryByRole("tab", { name: "Parameters" }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("tab", { name: "Configuration" }),
		).not.toBeInTheDocument();
	});

	it("renders the deprecation message in the Description tab for deprecated deployments", async () => {
		renderTabs(createFakeDeployment({ entrypoint: null }));

		await waitFor(() => {
			expect(
				screen.getByText("This deployment is deprecated"),
			).toBeInTheDocument();
		});
	});
});
