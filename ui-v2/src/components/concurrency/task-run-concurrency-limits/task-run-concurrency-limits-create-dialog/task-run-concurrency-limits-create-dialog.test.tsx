import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";

import { TaskRunConcurrencyLimitsCreateDialog } from "./task-run-concurrency-limits-create-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [] as Array<string>,
};

describe("TaskRunConcurrencyLimitsCreateDialog", () => {
	it.skip("calls onSubmit upon entering form data", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(
			<TaskRunConcurrencyLimitsCreateDialog
				onOpenChange={vi.fn()}
				onSubmit={mockOnSubmitFn}
			/>,
			{ wrapper: createWrapper() },
		);

		// ------------ Act
		await user.type(screen.getByLabelText(/tag/i), MOCK_DATA.tag);
		await user.type(
			screen.getByLabelText("Concurrency Limit"),
			String(MOCK_DATA.concurrency_limit),
		);

		await user.click(screen.getByRole("button", { name: /add/i }));

		// ------------ Assert
		expect(mockOnSubmitFn).toHaveBeenCalledOnce();
	});
});
