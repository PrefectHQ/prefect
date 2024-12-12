import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { GlobalConcurrencyLimitEmptyState } from "./global-concurrency-limit-empty-state";

test("GlobalConcurrencyLimitEmptyState", async () => {
	const user = userEvent.setup();

	const mockFn = vi.fn();

	render(<GlobalConcurrencyLimitEmptyState onAdd={mockFn} />);
	await user.click(
		screen.getByRole("button", { name: /Add Concurrency Limit/i }),
	);
	expect(mockFn).toHaveBeenCalledOnce();
});
