import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { createFakeSimpleFlowRuns } from "@/mocks";
import { FlowRunsScatterPlot } from "./flow-runs-scatter-plot";

describe("FlowRunsScatterPlot", () => {
	it("renders the scatter plot when history data is provided", () => {
		const history = createFakeSimpleFlowRuns(10);

		render(<FlowRunsScatterPlot history={history} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByTestId("scatter-plot")).toBeInTheDocument();
	});

	it("returns null when history is empty", () => {
		const { container } = render(<FlowRunsScatterPlot history={[]} />, {
			wrapper: createWrapper(),
		});

		expect(container.firstChild).toBeNull();
	});

	it("renders with custom start and end dates", () => {
		const history = createFakeSimpleFlowRuns(5);
		const startDate = new Date("2024-01-01");
		const endDate = new Date("2024-01-31");

		render(
			<FlowRunsScatterPlot
				history={history}
				startDate={startDate}
				endDate={endDate}
			/>,
			{ wrapper: createWrapper() },
		);

		expect(screen.getByTestId("scatter-plot")).toBeInTheDocument();
	});

	it("is hidden on small screens via CSS class", () => {
		const history = createFakeSimpleFlowRuns(3);

		render(<FlowRunsScatterPlot history={history} />, {
			wrapper: createWrapper(),
		});

		const scatterPlot = screen.getByTestId("scatter-plot");
		expect(scatterPlot).toHaveClass("hidden", "md:block");
	});
});
