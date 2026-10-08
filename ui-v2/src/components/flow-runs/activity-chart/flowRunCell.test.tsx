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
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunCell, type FlowRunCellProps } from "./flowRunCell";

const renderFlowRunCell = (props: FlowRunCellProps) => {
	const rootRoute = createRootRoute({
		component: () => (
			<TooltipProvider>
				<FlowRunCell {...props} />
			</TooltipProvider>
		),
	});
	const flowRunRoute = createRoute({
		getParentRoute: () => rootRoute,
		path: "/runs/flow-run/$id",
	});
	const router = createRouter({
		routeTree: rootRoute.addChildren([flowRunRoute]),
		history: createMemoryHistory({ initialEntries: ["/"] }),
		context: { queryClient: new QueryClient() },
	});

	render(<RouterProvider router={router} />);
	return router;
};

describe("Flow Run Activity Chart Cells", () => {
	const flowRun = createFakeFlowRun({ name: "test-flow-run" });
	const props = {
		flowRun,
		flowName: "test-flow",
		width: "10px",
		height: "10px",
		className: "bg-blue-500",
	};

	it("renders bar", async () => {
		renderFlowRunCell(props);

		await waitFor(() =>
			expect(
				screen.getByTestId(`flow-run-cell-${flowRun.id}`),
			).toBeInTheDocument(),
		);
	});

	it("navigates to the flow run when a populated cell is clicked", async () => {
		const user = userEvent.setup();
		const router = renderFlowRunCell(props);
		const cell = await screen.findByTestId(`flow-run-cell-${flowRun.id}`);

		expect(cell).toHaveAttribute("href", `/runs/flow-run/${flowRun.id}`);
		expect(cell).toHaveAccessibleName("Open flow run test-flow-run");

		await user.click(cell);

		await waitFor(() =>
			expect(router.state.location.pathname).toBe(
				`/runs/flow-run/${flowRun.id}`,
			),
		);
	});

	it("preserves the flow run tooltip", async () => {
		const user = userEvent.setup();
		renderFlowRunCell(props);
		const cell = await screen.findByTestId(`flow-run-cell-${flowRun.id}`);

		await user.hover(cell);

		expect(await screen.findByTestId("popover")).toBeInTheDocument();
	});

	it("keeps gap cells non-interactive", async () => {
		renderFlowRunCell({
			...props,
			flowRun: null,
			height: "5px",
		});

		const cell = await screen.findByTestId("flow-run-cell-undefined");
		expect(cell.tagName).toBe("DIV");
		expect(cell).not.toHaveAttribute("href");
	});
});
