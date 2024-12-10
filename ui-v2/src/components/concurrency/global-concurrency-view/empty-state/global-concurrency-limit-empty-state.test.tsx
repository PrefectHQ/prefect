import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GlobalConcurrencyLimitEmptyState } from "./global-concurrency-limit-empty-state";

describe("GlobalConcurrencyLimitEmptyState", () => {
	it("when adding limit, callback gets fired", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(<GlobalConcurrencyLimitEmptyState onAdd={mockFn} />);
		await user.click(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		);
		expect(mockFn).toHaveBeenCalledOnce();
	});
});
