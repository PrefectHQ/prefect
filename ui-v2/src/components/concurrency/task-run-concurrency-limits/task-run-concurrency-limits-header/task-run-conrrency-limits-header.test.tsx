import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskRunConcurrencyLimitsHeader } from "./task-run-concurrency-limits-header";

describe("TaskRunConcurrencyLimitsHeader", () => {
	it("can successfully call onAdd", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnAddFn = vi.fn();
		render(<TaskRunConcurrencyLimitsHeader onAdd={mockOnAddFn} />);

		// ------------ Act
		expect(
			expect(screen.getByText(/task run concurrency limits/i)).toBeVisible(),
		);

		await user.click(
			screen.getByRole("button", {
				name: /add task run concurrency limit/i,
			}),
		);

		// ------------ Assert
		expect(mockOnAddFn).toHaveBeenCalledOnce();
	});

	it("hides add button when canCreate is false", () => {
		render(
			<TaskRunConcurrencyLimitsHeader onAdd={vi.fn()} canCreate={false} />,
		);

		expect(screen.getByText(/task run concurrency limits/i)).toBeVisible();
		expect(
			screen.queryByRole("button", {
				name: /add task run concurrency limit/i,
			}),
		).not.toBeInTheDocument();
	});

	it("shows add button when canCreate is true", () => {
		render(<TaskRunConcurrencyLimitsHeader onAdd={vi.fn()} canCreate={true} />);

		expect(
			screen.getByRole("button", {
				name: /add task run concurrency limit/i,
			}),
		).toBeVisible();
	});
});
