import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { GlobalConcurrencyLimitsEmptyState } from "./global-concurrency-limits-empty-state";

test("GlobalConcurrencyLimitEmptyState", async () => {
	const user = userEvent.setup();

	const mockFn = vi.fn();

	render(<GlobalConcurrencyLimitsEmptyState onAdd={mockFn} />);
	await user.click(
		screen.getByRole("button", { name: /Add Concurrency Limit/i }),
	);
	expect(mockFn).toHaveBeenCalledOnce();
});
