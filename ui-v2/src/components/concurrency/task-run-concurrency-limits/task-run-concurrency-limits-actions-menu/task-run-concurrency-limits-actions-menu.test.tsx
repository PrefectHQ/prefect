import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";

import { TaskRunConcurrencyLimitsActionsMenu } from "./task-run-concurrency-limits-actions-menu";

describe("TaskRunConcurrencyLimitsActionsMenu", () => {
	it("copies the id", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<TaskRunConcurrencyLimitsActionsMenu
					id="my-id"
					onDelete={vi.fn()}
					onReset={vi.fn()}
				/>
			</>,
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: "Copy ID" }));

		// ------------ Assert
		await waitFor(() => {
			expect(screen.getByText("ID copied")).toBeVisible();
		});
	});

	it("calls delete option ", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnDeleteFn = vi.fn();

		render(
			<TaskRunConcurrencyLimitsActionsMenu
				id="my-id"
				onDelete={mockOnDeleteFn}
				onReset={vi.fn()}
			/>,
		);

		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));

		// ------------ Assert
		expect(mockOnDeleteFn).toHaveBeenCalledOnce();
	});

	it("calls reset option ", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnResetFn = vi.fn();

		render(
			<TaskRunConcurrencyLimitsActionsMenu
				id="my-id"
				onDelete={vi.fn()}
				onReset={mockOnResetFn}
			/>,
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /reset/i }));

		// ------------ Assert
		expect(mockOnResetFn).toHaveBeenCalledOnce();
	});
});
