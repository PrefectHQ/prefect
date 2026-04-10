import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskRunConcurrencyLimitsEmptyState } from "./task-run-concurrency-limits-empty-state";

describe("TaskRunConcurrencyLimitsEmptyState", () => {
	it("when adding task run concurrency limit, callback gets fired", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(<TaskRunConcurrencyLimitsEmptyState onAdd={mockFn} />);
		await user.click(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		);
		expect(mockFn).toHaveBeenCalledOnce();
	});

	it("hides add button when canCreate is false", () => {
		render(
			<TaskRunConcurrencyLimitsEmptyState onAdd={vi.fn()} canCreate={false} />,
		);

		expect(
			screen.queryByRole("button", { name: /Add Concurrency Limit/i }),
		).not.toBeInTheDocument();
	});

	it("shows add button when canCreate is true", () => {
		render(
			<TaskRunConcurrencyLimitsEmptyState onAdd={vi.fn()} canCreate={true} />,
		);

		expect(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		).toBeVisible();
	});
});
