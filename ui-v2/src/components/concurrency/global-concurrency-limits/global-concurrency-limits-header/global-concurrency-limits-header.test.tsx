import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GlobalConcurrencyLimitsHeader } from "./global-concurrency-limits-header";

describe("GlobalConcurrencyLimitsHeader", () => {
	it("can successfully call onAdd", async () => {
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

	it("hides add button when canCreate is false", () => {
		render(<GlobalConcurrencyLimitsHeader onAdd={vi.fn()} canCreate={false} />);

		expect(screen.getByText(/global concurrency limits/i)).toBeVisible();
		expect(
			screen.queryByRole("button", {
				name: /add global concurrency limit/i,
			}),
		).not.toBeInTheDocument();
	});

	it("shows add button when canCreate is true", () => {
		render(<GlobalConcurrencyLimitsHeader onAdd={vi.fn()} canCreate={true} />);

		expect(
			screen.getByRole("button", {
				name: /add global concurrency limit/i,
			}),
		).toBeVisible();
	});
});
