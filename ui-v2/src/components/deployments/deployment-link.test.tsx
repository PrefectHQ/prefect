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
import { Suspense } from "react";
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { DeploymentLink } from "./deployment-link";

const mockDeployment = createFakeDeployment({
	id: "deployment-123",
	name: "my-deployment",
});

type DeploymentLinkRouterProps = {
	deploymentId: string;
};

const DeploymentLinkRouter = ({ deploymentId }: DeploymentLinkRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<DeploymentLink deploymentId={deploymentId} />
			</Suspense>
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

describe("DeploymentLink", () => {
	it("fetches and displays deployment name", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		render(<DeploymentLinkRouter deploymentId="deployment-123" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});

	it("displays the Deployment label", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		render(<DeploymentLinkRouter deploymentId="deployment-123" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Deployment")).toBeInTheDocument();
		});
	});

	it("renders a link to the deployment detail page", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		render(<DeploymentLinkRouter deploymentId="deployment-123" />, {
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
