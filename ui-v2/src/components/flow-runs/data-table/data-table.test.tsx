import { Toaster } from "@/components/ui/toaster";
import { createFakeFlowRunWithDeploymentAndFlow } from "@/mocks/create-fake-flow-run";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { FlowRunsDataTable, type FlowRunsDataTableProps } from "./data-table";

// Wraps component in test with a Tanstack router provider
const FlowRunsDataTableRouter = (props: FlowRunsDataTableProps) => {
	const rootRoute = createRootRoute({
		component: () => <FlowRunsDataTable {...props} />,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
	// @ts-expect-error - Type error from using a test router
	return <RouterProvider router={router} />;
};

describe("Flow Runs DataTable", () => {
	const MOCK_DATA = [
		createFakeFlowRunWithDeploymentAndFlow(),
		createFakeFlowRunWithDeploymentAndFlow(),
		createFakeFlowRunWithDeploymentAndFlow(),
	];

	it("able to delete a single row", async () => {
		// Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<FlowRunsDataTableRouter
					flowRuns={MOCK_DATA}
					flowRunsCount={MOCK_DATA.length}
					pageCount={5}
					pagination={{
						pageSize: 10,
						pageIndex: 2,
					}}
					onPaginationChange={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);
		expect(screen.getByText(/3 flow runs/i)).toBeVisible();
		const row = screen.getAllByRole("row")[1];

		// Act
		await user.click(
			within(row).getByRole("checkbox", { name: /select row/i }),
		);
		expect(screen.getByText("1 selected")).toBeVisible();

		await user.click(screen.getByRole("button", { name: /delete rows/i }));
		await user.click(screen.getByRole("button", { name: /delete/i }));

		// Assert
		expect(screen.getByText("Flow run deleted")).toBeVisible();
	});

	it("able to select all rows and delete", async () => {
		// Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<FlowRunsDataTableRouter
					flowRuns={MOCK_DATA}
					flowRunsCount={MOCK_DATA.length}
					pageCount={5}
					pagination={{
						pageSize: 10,
						pageIndex: 2,
					}}
					onPaginationChange={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);
		expect(screen.getByText(/3 flow runs/i)).toBeVisible();

		// Act
		await user.click(screen.getByRole("checkbox", { name: /select all/i }));
		expect(screen.getByText("3 selected")).toBeVisible();

		await user.click(screen.getByRole("button", { name: /delete rows/i }));
		await user.click(screen.getByRole("button", { name: /delete/i }));

		// Assert
		expect(screen.getByText("3 flow runs deleted")).toBeVisible();
	});
});
