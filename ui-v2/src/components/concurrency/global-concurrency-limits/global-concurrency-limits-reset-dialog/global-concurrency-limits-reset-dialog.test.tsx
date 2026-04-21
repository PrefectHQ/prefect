import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";
import { GlobalConcurrencyLimitsResetDialog } from "./global-concurrency-limits-reset-dialog";

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

test("GlobalConcurrencyLimitsResetDialog can successfully call reset", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnResetFn = vi.fn();
	render(
		<GlobalConcurrencyLimitsResetDialog
			limit={MOCK_DATA}
			onReset={mockOnResetFn}
			onOpenChange={vi.fn()}
		/>,
		{ wrapper: createWrapper() },
	);

	// ------------ Act
	expect(
		screen.getByRole("heading", {
			name: /reset concurrency limit for global concurrency limit 0/i,
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
