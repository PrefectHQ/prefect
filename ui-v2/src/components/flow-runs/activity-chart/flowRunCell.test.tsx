import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunCell } from "./flowRunCell";

describe("Flow Run Activity Chart Cells", () => {
	const flowRun = createFakeFlowRun();

	it("renders bar", async () => {
		const { getByTestId } = render(
			<TooltipProvider>
				<FlowRunCell
					flowRun={flowRun}
					flowName="test-flow"
					width="10px"
					height="10px"
					className="bg-blue-500"
				/>
			</TooltipProvider>,
		);

		await waitFor(() =>
			expect(getByTestId(`flow-run-cell-${flowRun.id}`)).toBeInTheDocument(),
		);
	});
});
