import { DeleteLimitDialog } from "./delete-dialog";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	tag: "my tag 0",
	concurrency_limit: 1,
	active_slots: [] as Array<string>,
};

test("DeleteLimitDialog can successfully call delete", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnDeleteFn = vi.fn();
	render(
		<DeleteLimitDialog
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
