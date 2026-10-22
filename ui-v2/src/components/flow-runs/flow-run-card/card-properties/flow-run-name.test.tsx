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
import type { FlowRunCardData } from "@/components/flow-runs/flow-run-card";
import { createFakeFlow, createFakeFlowRun } from "@/mocks";
import { FlowRunName } from "./flow-run-name";

const FlowRunNameRouter = ({ flowRun }: { flowRun: FlowRunCardData }) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunName flowRun={flowRun} />,
	});
	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});
	return <RouterProvider router={router} />;
};

describe("FlowRunName", () => {
	it("renders the run name as a link to the flow run page", async () => {
		const flow = createFakeFlow({ id: "flow-id", name: "my-flow" });
		const flowRun = {
			...createFakeFlowRun({ id: "run-id", name: "my-run", flow_id: flow.id }),
			flow,
		};

		await waitFor(() =>
			render(<FlowRunNameRouter flowRun={flowRun} />, {
				wrapper: createWrapper(),
			}),
		);

		const runLink = await screen.findByRole("link", { name: "my-run" });
		expect(runLink.getAttribute("href")).toBe("/runs/flow-run/run-id");
		expect(runLink).toHaveClass("text-link");

		const flowLink = screen.getByRole("link", { name: "my-flow" });
		expect(flowLink.getAttribute("href")).toBe("/flows/flow/flow-id");
	});

	it("omits the flow breadcrumb when no flow is provided", async () => {
		const flowRun = createFakeFlowRun({ id: "run-id", name: "my-run" });

		await waitFor(() =>
			render(<FlowRunNameRouter flowRun={flowRun} />, {
				wrapper: createWrapper(),
			}),
		);

		expect(await screen.findByRole("link", { name: "my-run" })).toBeVisible();
		expect(screen.getAllByRole("link")).toHaveLength(1);
	});
});
