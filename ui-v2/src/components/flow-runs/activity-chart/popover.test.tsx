import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { Popover, type PopoverProps } from "./popover";

// Wraps component in test with a Tanstack router provider
const PopoverRouter = (props: PopoverProps) => {
	const rootRoute = createRootRoute({
		component: () => <Popover {...props} />,
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

describe("Flow Run Activity Chart Popover", () => {
	const flowRun = createFakeFlowRun({
		name: "test-flow-run",
		estimated_run_time: 1,
		start_time: "2025-01-01T12:00:00.000Z",
	});

	it("renders popover", async () => {
		render(<PopoverRouter name="test-flow" flowRun={flowRun} />);

		expect(await screen.findByTestId("popover")).toBeInTheDocument();
	});

	it("renders popover with expected content", async () => {
		render(<PopoverRouter name="testFlow" flowRun={flowRun} />);

		expect(await screen.findByText("test-flow-run")).toBeInTheDocument();
		expect(await screen.findByText("1 second")).toBeInTheDocument();
		expect(
			await screen.findByText(
				new Date(
					flowRun.start_time ?? flowRun.expected_start_time ?? "",
				).toLocaleString(),
			),
		).toBeInTheDocument();
	});
});
