import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import {
	createFakeDeployment,
	createFakeFlowRunWithFlow,
	createFakeState,
	createFakeWorkQueue,
} from "@/mocks";
import { FlowRunCard, type FlowRunCardData } from "./flow-run-card";

const FlowRunCardRouter = ({ flowRun }: { flowRun: FlowRunCardData }) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunCard flowRun={flowRun} />,
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("FlowRunCard", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/ui/flow_runs/count-task-runs"), () =>
				HttpResponse.json({}),
			),
			http.get(
				buildApiUrl("/work_pools/:work_pool_name/queues/:name"),
				({ params }) =>
					HttpResponse.json(
						createFakeWorkQueue({
							name: String(params.name),
							work_pool_name: String(params.work_pool_name),
						}),
					),
			),
		);
	});

	it("renders deployment, work pool, and work queue links", async () => {
		const deployment = createFakeDeployment({
			id: "deployment-1",
			name: "my-deployment",
		});
		const flowRun: FlowRunCardData = {
			...createFakeFlowRunWithFlow({
				deployment_id: deployment.id,
				work_pool_name: "my-work-pool",
				work_queue_name: "my-work-queue",
				state: createFakeState({ type: "COMPLETED", name: "Completed" }),
			}),
			deployment,
		};

		render(<FlowRunCardRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		expect(
			await screen.findByRole("link", { name: /my-deployment/ }),
		).toHaveAttribute("href", "/deployments/deployment/deployment-1");
		expect(screen.getByRole("link", { name: /my-work-pool/ })).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-work-pool",
		);
		expect(
			await screen.findByRole("link", { name: /my-work-queue/ }),
		).toHaveAttribute(
			"href",
			"/work-pools/work-pool/my-work-pool/queue/my-work-queue",
		);
	});

	it("does not render a relationships row when the run has no associations", async () => {
		const flowRun = createFakeFlowRunWithFlow({
			deployment_id: null,
			work_pool_name: null,
			work_queue_name: null,
		});

		render(<FlowRunCardRouter flowRun={flowRun} />, {
			wrapper: createWrapper(),
		});

		await screen.findByText(flowRun.name ?? "");
		expect(screen.queryByText("Deployment")).not.toBeInTheDocument();
		expect(screen.queryByText("Work Pool")).not.toBeInTheDocument();
		expect(screen.queryByText("Work Queue")).not.toBeInTheDocument();
	});
});
