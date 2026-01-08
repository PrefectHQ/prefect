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
import { DeploymentIconText } from "./deployment-icon-text";

const mockDeployment = createFakeDeployment({
	id: "deployment-123",
	name: "my-deployment",
});

type DeploymentIconTextWithIdRouterProps = {
	deploymentId: string;
};

const DeploymentIconTextWithIdRouter = ({
	deploymentId,
}: DeploymentIconTextWithIdRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<Suspense fallback={<div>Loading...</div>}>
				<DeploymentIconText deploymentId={deploymentId} />
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

describe("DeploymentIconText with deploymentId", () => {
	it("fetches and displays deployment name", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		render(<DeploymentIconTextWithIdRouter deploymentId="deployment-123" />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});

	it("renders a link to the deployment detail page", async () => {
		server.use(
			http.get(buildApiUrl("/deployments/:id"), () => {
				return HttpResponse.json(mockDeployment);
			}),
		);

		render(<DeploymentIconTextWithIdRouter deploymentId="deployment-123" />, {
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

type DeploymentIconTextWithDeploymentRouterProps = {
	deployment: typeof mockDeployment;
	className?: string;
	iconSize?: number;
	onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
};

const DeploymentIconTextWithDeploymentRouter = ({
	deployment,
	className,
	iconSize,
	onClick,
}: DeploymentIconTextWithDeploymentRouterProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<DeploymentIconText
				deployment={deployment}
				className={className}
				iconSize={iconSize}
				onClick={onClick}
			/>
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

describe("DeploymentIconText with deployment prop", () => {
	it("displays deployment name without fetching", async () => {
		render(
			<DeploymentIconTextWithDeploymentRouter deployment={mockDeployment} />,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(screen.getByText("my-deployment")).toBeInTheDocument();
		});
	});

	it("renders a link to the deployment detail page", async () => {
		render(
			<DeploymentIconTextWithDeploymentRouter deployment={mockDeployment} />,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveAttribute(
				"href",
				"/deployments/deployment/deployment-123",
			);
		});
	});

	it("applies custom className", async () => {
		render(
			<DeploymentIconTextWithDeploymentRouter
				deployment={mockDeployment}
				className="custom-class"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			const link = screen.getByRole("link");
			expect(link).toHaveClass("custom-class");
		});
	});
});
