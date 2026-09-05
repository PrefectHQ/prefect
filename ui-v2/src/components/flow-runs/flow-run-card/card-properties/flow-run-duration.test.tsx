import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunDuration } from "./flow-run-duration";

describe("FlowRunDuration", () => {
	it("displays a duration of minutes and seconds", () => {
		const flowRun = createFakeFlowRun({
			estimated_run_time: 125,
			total_run_time: 0,
		});

		render(<FlowRunDuration flowRun={flowRun} />);

		expect(screen.getByText("2m 5s")).toBeVisible();
	});

	it("displays long durations in hours and minutes", async () => {
		const user = userEvent.setup();
		const flowRun = createFakeFlowRun({
			estimated_run_time: 42787.67,
			total_run_time: 0,
		});

		render(<FlowRunDuration flowRun={flowRun} />);

		expect(screen.getByText("11h 53m")).toBeVisible();

		await user.hover(screen.getByText("11h 53m"));

		expect(
			await screen.findByText("11 hours 53 minutes 8 seconds"),
		).toBeVisible();
	});

	it("falls back to the total run time", () => {
		const flowRun = createFakeFlowRun({
			estimated_run_time: 0,
			total_run_time: 3661,
		});

		render(<FlowRunDuration flowRun={flowRun} />);

		expect(screen.getByText("1h 1m")).toBeVisible();
	});
});
