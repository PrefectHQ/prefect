import { createFakeFlowRun } from "@/mocks";
import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
import { waitFor } from "@testing-library/dom";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Popover, PopoverProps } from "./popover";

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
		estimated_run_time: 1,
	});

	it("renders popover", async () => {
		const { getByTestId } = render(
			<PopoverRouter name="test-flow" flowRun={flowRun} />,
		);

		await waitFor(() => expect(getByTestId("popover")).toBeInTheDocument());
	});

	it("renders popover with expected content", () => {
		const { getByText } = render(
			<PopoverRouter name="testFlow" flowRun={flowRun} />,
		);

		expect(getByText(flowRun.name ?? "")).toBeInTheDocument();
		expect(getByText("1 second")).toBeInTheDocument();
		expect(
			getByText(
				new Date(
					flowRun.start_time ?? flowRun.expected_start_time ?? "",
				).toLocaleString(),
			),
		).toBeInTheDocument();
	});
});
