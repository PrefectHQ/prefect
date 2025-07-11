import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

test("GlobalConcurrencyLimitsHeader can successfully call onAdd", async () => {
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnAddFn = vi.fn();
	render(<GlobalConcurrencyLimitsHeader onAdd={mockOnAddFn} />);

	// ------------ Act
	expect(screen.getByText(/global concurrency limits/i)).toBeVisible();
	await user.click(
		screen.getByRole("button", {
			name: /add global concurrency limit/i,
		}),
	);

	// ------------ Assert
	expect(mockOnAddFn).toHaveBeenCalledOnce();
});
