import { TaskRunConcurrencyLimitsHeader } from "./task-run-concurrency-limit-header";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

test("TaskRunConcurrencyLimitsHeader can successfully call onAdd", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnAddFn = vi.fn();
	render(<TaskRunConcurrencyLimitsHeader onAdd={mockOnAddFn} />);

	// ------------ Act
	expect(
		screen.getByRole("heading", { name: /task run concurrency limits/i }),
	).toBeVisible();
	await user.click(
		screen.getByRole("button", {
			name: /add task run concurrency limit/i,
		}),
	);

	// ------------ Assert
	expect(mockOnAddFn).toHaveBeenCalledOnce();
});
