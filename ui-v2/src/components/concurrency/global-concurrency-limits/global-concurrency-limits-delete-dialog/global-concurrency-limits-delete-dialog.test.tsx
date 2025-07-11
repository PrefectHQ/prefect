import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";
import { GlobalConcurrencyLimitsDeleteDialog } from "./global-concurrency-limits-delete-dialog";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	active: false,
	name: "global concurrency limit 0",
	limit: 0,
	active_slots: 0,
	slot_decay_per_second: 0,
};

test("GlobalConcurrencyLimitsDeleteDialog can successfully call delete", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnDeleteFn = vi.fn();
	render(
		<GlobalConcurrencyLimitsDeleteDialog
			limit={MOCK_DATA}
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
