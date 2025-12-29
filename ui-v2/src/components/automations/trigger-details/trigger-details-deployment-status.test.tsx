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
import { describe, expect, it } from "vitest";
import { createFakeDeployment } from "@/mocks";
import { TriggerDetailsDeploymentStatus } from "./trigger-details-deployment-status";

const mockDeployments = {
	"deployment-1": createFakeDeployment({
		id: "deployment-1",
		name: "my-app",
	}),
	"deployment-2": createFakeDeployment({
		id: "deployment-2",
		name: "other-app",
	}),
	"deployment-3": createFakeDeployment({
		id: "deployment-3",
		name: "third-app",
	}),
};

type TriggerDetailsDeploymentStatusRouterProps = {
	deploymentIds: string[];
	posture: "Reactive" | "Proactive";
	status: "ready" | "not_ready";
	time?: number;
};

const TriggerDetailsDeploymentStatusRouter = (
	props: TriggerDetailsDeploymentStatusRouterProps,
) => {
	const rootRoute = createRootRoute({
		component: () => <TriggerDetailsDeploymentStatus {...props} />,
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

const setupMockServer = () => {
	server.use(
		http.get(buildApiUrl("/deployments/:id"), ({ params }) => {
			const deployment =
				mockDeployments[params.id as keyof typeof mockDeployments];
			if (deployment) {
				return HttpResponse.json(deployment);
			}
			return new HttpResponse(null, { status: 404 });
		}),
	);
};

describe("TriggerDetailsDeploymentStatus", () => {
	describe("any deployment (empty deploymentIds)", () => {
		it("renders 'any deployment' when deploymentIds is empty", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("When")).toBeInTheDocument();
			expect(screen.getByText("any deployment")).toBeInTheDocument();
		});

		it("renders reactive posture as 'enters'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("enters")).toBeInTheDocument();
		});

		it("renders proactive posture as 'stays in'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(screen.getByText("stays in")).toBeInTheDocument();
		});
	});

	describe("status display", () => {
		it("renders 'ready' status in lowercase", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(screen.getByText("ready")).toBeInTheDocument();
		});

		it("renders 'not_ready' status as 'not ready'", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="not_ready"
				/>,
			);
			expect(screen.getByText("not ready")).toBeInTheDocument();
		});
	});

	describe("time duration for proactive posture", () => {
		it("shows time duration for proactive posture", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
		});

		it("shows longer time duration correctly", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={3600}
				/>,
			);
			expect(screen.getByText("for 1 hour")).toBeInTheDocument();
		});

		it("does not show time for reactive posture", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
					time={30}
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});

		it("does not show time when time is 0", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={0}
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});

		it("does not show time when time is undefined", () => {
			render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
				/>,
			);
			expect(screen.queryByText(/for \d+/)).not.toBeInTheDocument();
		});
	});

	describe("specific deployments with DeploymentLink", () => {
		it("renders deployment link for single deployment", async () => {
			setupMockServer();

			render(
				<TriggerDetailsDeploymentStatusRouter
					deploymentIds={["deployment-1"]}
					posture="Reactive"
					status="ready"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("my-app")).toBeInTheDocument();
			});
			expect(screen.getByText("Deployment")).toBeInTheDocument();
		});

		it("renders 'or' between two deployments", async () => {
			setupMockServer();

			render(
				<TriggerDetailsDeploymentStatusRouter
					deploymentIds={["deployment-1", "deployment-2"]}
					posture="Reactive"
					status="ready"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("my-app")).toBeInTheDocument();
				expect(screen.getByText("other-app")).toBeInTheDocument();
			});
			expect(screen.getByText("or")).toBeInTheDocument();
		});

		it("renders 'or' only before the last deployment for three deployments", async () => {
			setupMockServer();

			render(
				<TriggerDetailsDeploymentStatusRouter
					deploymentIds={["deployment-1", "deployment-2", "deployment-3"]}
					posture="Reactive"
					status="ready"
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("my-app")).toBeInTheDocument();
				expect(screen.getByText("other-app")).toBeInTheDocument();
				expect(screen.getByText("third-app")).toBeInTheDocument();
			});
			const orElements = screen.getAllByText("or");
			expect(orElements).toHaveLength(1);
		});

		it("renders deployment with proactive posture and time", async () => {
			setupMockServer();

			render(
				<TriggerDetailsDeploymentStatusRouter
					deploymentIds={["deployment-1", "deployment-2"]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
				{ wrapper: createWrapper() },
			);

			await waitFor(() => {
				expect(screen.getByText("my-app")).toBeInTheDocument();
				expect(screen.getByText("other-app")).toBeInTheDocument();
			});
			expect(screen.getByText("stays in")).toBeInTheDocument();
			expect(screen.getByText("not ready")).toBeInTheDocument();
			expect(screen.getByText("for 30 seconds")).toBeInTheDocument();
		});
	});

	describe("complete output scenarios", () => {
		it("renders 'When any deployment enters ready'", () => {
			const { container } = render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Reactive"
					status="ready"
				/>,
			);
			expect(container.textContent).toContain("When");
			expect(container.textContent).toContain("any deployment");
			expect(container.textContent).toContain("enters");
			expect(container.textContent).toContain("ready");
		});

		it("renders 'When any deployment stays in not ready for 30 seconds'", () => {
			const { container } = render(
				<TriggerDetailsDeploymentStatus
					deploymentIds={[]}
					posture="Proactive"
					status="not_ready"
					time={30}
				/>,
			);
			expect(container.textContent).toContain("When");
			expect(container.textContent).toContain("any deployment");
			expect(container.textContent).toContain("stays in");
			expect(container.textContent).toContain("not ready");
			expect(container.textContent).toContain("for 30 seconds");
		});
	});
});
