import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TaskRunConcurrencyLimitEmptyState } from "./task-run-concurrency-limit-empty-state";

describe("TaskRunConcurrencyLimitEmptyState", () => {
	it("when adding task run concurrency limit, callback gets fired", async () => {
		const user = userEvent.setup();

		const mockFn = vi.fn();

		render(<TaskRunConcurrencyLimitEmptyState onClick={mockFn} />);
		await user.click(
			screen.getByRole("button", { name: /Add Concurrency Limit/i }),
		);
		expect(mockFn).toHaveBeenCalledOnce();
	});
});
