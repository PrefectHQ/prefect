import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunStartTime } from "./flow-run-start-time";

describe("FlowRunStartTime", () => {
	it("shows lateness for a run that is hours late", () => {
		const flowRun = createFakeFlowRun({
			start_time: null,
			expected_start_time: "2024-01-01T00:00:00.000Z",
			estimated_start_time_delta: 7200,
		});

		render(<FlowRunStartTime flowRun={flowRun} />);

		expect(screen.getByText(/\(2h 0m late\)/)).toBeVisible();
	});

	it("shows lateness in minutes and seconds", () => {
		const flowRun = createFakeFlowRun({
			start_time: null,
			expected_start_time: "2024-01-01T00:00:00.000Z",
			estimated_start_time_delta: 125,
		});

		render(<FlowRunStartTime flowRun={flowRun} />);

		expect(screen.getByText(/\(2m 5s late\)/)).toBeVisible();
	});

	it("omits lateness when the delta is a minute or less", () => {
		const flowRun = createFakeFlowRun({
			start_time: null,
			expected_start_time: "2024-01-01T00:00:00.000Z",
			estimated_start_time_delta: 60,
		});

		render(<FlowRunStartTime flowRun={flowRun} />);

		expect(screen.queryByText(/late/)).not.toBeInTheDocument();
	});
});
