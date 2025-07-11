import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";
import { TaskRunConcurrencyLimitsDeleteDialog } from "./task-run-concurrency-limits-delete-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [] as Array<string>,
};

test("TaskRunConcurrencyLimitsDeleteDialog can successfully call delete", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnDeleteFn = vi.fn();
	render(
		<TaskRunConcurrencyLimitsDeleteDialog
			data={MOCK_DATA}
			onDelete={mockOnDeleteFn}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// ------------ Act
	expect(screen.getByRole("heading", { name: /delete concurrency limit/i }));
	await user.click(
		screen.getByRole("button", {
			name: /delete/i,
		}),
	);

	// ------------ Assert
	expect(mockOnDeleteFn).toHaveBeenCalledOnce();
});
