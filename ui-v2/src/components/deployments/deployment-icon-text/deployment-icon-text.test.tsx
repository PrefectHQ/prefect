import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { DeploymentIconText } from "./deployment-icon-text";

const mockDeployment = createFakeDeployment({
	id: "deployment-123",
	name: "my-deployment",
});

type DeploymentIconTextRouterProps = {
	deployment: typeof mockDeployment;
};

const DeploymentIconTextRouter = ({
	deployment,
}: DeploymentIconTextRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => <DeploymentIconText deployment={deployment} />,
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

describe("DeploymentIconText", () => {
	it("displays deployment name", async () => {
		render(<DeploymentIconTextRouter deployment={mockDeployment} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});

	it("renders a link to the deployment detail page", async () => {
		render(<DeploymentIconTextRouter deployment={mockDeployment} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute(
				"href",
				"/deployments/deployment/deployment-123",
			);
		});
	});
});
