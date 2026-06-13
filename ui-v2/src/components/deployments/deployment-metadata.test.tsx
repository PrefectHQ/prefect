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
import { createFakeDeployment } from "@/mocks";
import { DeploymentMetadata } from "./deployment-metadata";

const renderDeploymentMetadata = ({ tags }: { tags: string[] }) => {
	const deployment = createFakeDeployment({ tags });

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
});
