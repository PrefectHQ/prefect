import { Toaster } from "@/components/ui/toaster";
import { createFakeAutomation } from "@/mocks";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test, vi } from "vitest";

import { AutomationsDeleteDialog } from "./automations-delete-dialog";

test("AutomationsDeleteDialog can successfully call delete", async () => {
	const MOCK_DATA = createFakeAutomation();
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnDeleteFn = vi.fn();
	render(
		<>
			<Toaster />
			<AutomationsDeleteDialog
				automation={MOCK_DATA}
				onDelete={mockOnDeleteFn}
				onOpenChange={vi.fn()}
			/>
		</>,
		{ wrapper: createWrapper() },
	);

	// ------------ Act
	expect(screen.getByRole("heading", { name: /delete automation/i }));
	await user.click(
		screen.getByRole("button", {
			name: /delete/i,
		}),
	);

	// ------------ Assert
	expect(screen.getByText(/automation deleted/i)).toBeVisible();
	expect(mockOnDeleteFn).toHaveBeenCalledOnce();
});
