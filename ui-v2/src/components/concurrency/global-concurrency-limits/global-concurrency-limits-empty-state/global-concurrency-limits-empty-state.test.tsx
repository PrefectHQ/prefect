import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GlobalConcurrencyLimitsEmptyState } from "./global-concurrency-limits-empty-state";

describe("GlobalConcurrencyLimitsEmptyState", () => {
	it("calls onAdd when add button is clicked", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(<GlobalConcurrencyLimitsEmptyState onAdd={mockFn} />);
		await user.click(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		);
		expect(mockFn).toHaveBeenCalledOnce();
	});

	it("hides add button when canCreate is false", () => {
		render(
			<GlobalConcurrencyLimitsEmptyState onAdd={vi.fn()} canCreate={false} />,
		);

		expect(
			screen.queryByRole("button", { name: /Add Concurrency Limit/i }),
		).not.toBeInTheDocument();
	});

	it("shows add button when canCreate is true", () => {
		render(
			<GlobalConcurrencyLimitsEmptyState onAdd={vi.fn()} canCreate={true} />,
		);

		expect(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		).toBeVisible();
	});
});
