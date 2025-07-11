import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeFlowRuns } from "@/mocks/create-fake-flow-run";
import FlowRunsBarChart from "./activity-chart";

describe("Flow Run Activity Chart", () => {
	const flowRuns = createFakeFlowRuns();
	const flowName = "Test Flow";
	it("should render the number of flow runs", () => {
		const { getByText } = render(
			<FlowRunsBarChart flowRuns={flowRuns} flowName={flowName} />,
		);

		expect(getByText("10")).toBeInTheDocument();
	});
});
