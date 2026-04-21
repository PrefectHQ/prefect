import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { TaskRunConcurrencyLimitActiveTaskRuns } from "./task-run-concurrency-limit-active-task-runs";

describe("TaskRunConcurrencyLimitActiveTaskRuns", () => {
	it("renders an empty-state message when there are no active task runs", () => {
		render(<TaskRunConcurrencyLimitActiveTaskRuns data={[]} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("No active task runs")).toBeInTheDocument();
	});
});
