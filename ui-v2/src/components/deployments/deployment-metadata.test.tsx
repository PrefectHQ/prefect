import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import type { Deployment } from "@/api/deployments";
import { createFakeDeployment } from "@/mocks";
import { DeploymentMetadata } from "./deployment-metadata";

const renderDeploymentMetadata = (
	overrides: Partial<Deployment> = { tags: [] },
) => {
	const deployment = createFakeDeployment(overrides);

	const rootRoute = createRootRoute();
	const deploymentsRoute = createRoute({
		path: "/deployments",
		getParentRoute: () => rootRoute,
		component: () => <div>Deployments List</div>,
	});
	const deploymentRoute = createRoute({
		path: "/deployments/deployment/$id",
		getParentRoute: () => rootRoute,
		component: () => <DeploymentMetadata deployment={deployment} />,
	});

	const routeTree = rootRoute.addChildren([deploymentsRoute, deploymentRoute]);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({
			initialEntries: [`/deployments/deployment/${deployment.id}`],
		}),
		context: { queryClient: new QueryClient() },
	});

	return {
		...render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		}),
		router,
	};
};

describe("DeploymentMetadata", () => {
	it("renders tags", async () => {
		renderDeploymentMetadata({ tags: ["tag1", "tag2"] });

		await waitFor(() => {
			expect(screen.getByText("tag1")).toBeInTheDocument();
		});
		expect(screen.getByText("tag2")).toBeInTheDocument();
	});

	it("navigates to deployments list with tag filter on tag click", async () => {
		const user = userEvent.setup();
		const { router } = renderDeploymentMetadata({ tags: ["my-tag"] });

		await waitFor(() => {
			expect(screen.getByText("my-tag")).toBeInTheDocument();
		});

		await user.click(screen.getByText("my-tag"));

		await waitFor(() => {
			expect(router.state.location.pathname).toBe("/deployments");
			expect(router.state.location.search).toEqual(
				expect.objectContaining({ tags: ["my-tag"] }),
			);
		});
	});

	it("shows 'None' when no tags are present", async () => {
		renderDeploymentMetadata({ tags: [] });

		await waitFor(() => {
			expect(screen.getByText("Tags")).toBeInTheDocument();
		});

		const tagsDt = screen.getByText("Tags");
		const tagsDd = tagsDt.parentElement?.querySelector("dd");
		expect(tagsDd).toHaveTextContent("None");
	});

	describe("timestamps", () => {
		const created = "2026-09-14T14:57:45.535230Z";
		const updated = "2026-09-15T03:05:09.000000Z";

		it("renders Created and Updated in readable date-time format", async () => {
			renderDeploymentMetadata({ created, updated });

			expect(
				await screen.findByText("Sep 14, 2026 at 2:57 PM"),
			).toBeInTheDocument();
			expect(screen.getByText("Sep 15, 2026 at 3:05 AM")).toBeInTheDocument();
			expect(screen.queryByText(created)).not.toBeInTheDocument();
			expect(screen.queryByText(updated)).not.toBeInTheDocument();
		});

		it("exposes the precise timestamp in a tooltip", async () => {
			const user = userEvent.setup();
			renderDeploymentMetadata({ created, updated });

			await user.hover(await screen.findByText("Sep 14, 2026 at 2:57 PM"));

			expect(await screen.findByRole("tooltip")).toHaveTextContent(created);
		});

		it("shows 'None' when timestamps are missing", async () => {
			renderDeploymentMetadata({ created: undefined, updated: undefined });

			const createdDt = await screen.findByText("Created");
			expect(createdDt.parentElement?.querySelector("dd")).toHaveTextContent(
				"None",
			);
			const updatedDt = screen.getByText("Updated");
			expect(updatedDt.parentElement?.querySelector("dd")).toHaveTextContent(
				"None",
			);
		});
	});
});
