import { render, screen } from "@testing-library/react";
import humanizeDuration from "humanize-duration";
import { describe, expect, it } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunDuration } from "./flow-run-duration";

describe("FlowRunDuration", () => {
	it("formats API duration seconds as milliseconds", () => {
		const estimatedRunTime = 125;
		const flowRun = createFakeFlowRun({
			estimated_run_time: estimatedRunTime,
			total_run_time: 0,
		});

		render(<FlowRunDuration flowRun={flowRun} />);

		expect(
			screen.getByText(
				humanizeDuration(estimatedRunTime * 1000, {
					maxDecimalPoints: 2,
					units: ["s"],
				}),
			),
		).toBeVisible();
	});
});
