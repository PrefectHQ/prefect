import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";
import { TaskRunConcurrencyLimitsResetDialog } from "./task-run-concurrency-limits-reset-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [] as Array<string>,
};

test("TaskRunConcurrencyLimitsResetDialog can successfully call delete", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnResetFn = vi.fn();
	render(
		<TaskRunConcurrencyLimitsResetDialog
			data={MOCK_DATA}
			onReset={mockOnResetFn}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// ------------ Act
	expect(
		screen.getByRole("heading", {
			name: /reset concurrency limit for tag my tag 0/i,
		}),
	);
	await user.click(
		screen.getByRole("button", {
			name: /reset/i,
		}),
	);

	// ------------ Assert
	expect(mockOnResetFn).toHaveBeenCalledOnce();
});
