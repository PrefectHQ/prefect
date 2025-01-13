import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { expect, test, vi } from "vitest";

import { AutomationsTriggerTemplateSelect } from "./automations-trigger-template-select";

test("AutomationsTriggerTemplateSelect can select an option", async () => {
	mockPointerEvents();
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnValueChangeFn = vi.fn();

	render(
		<AutomationsTriggerTemplateSelect onValueChange={mockOnValueChangeFn} />,
	);

	// ------------ Act
	await user.click(screen.getByLabelText("Trigger Template"));
	await user.click(screen.getByRole("option", { name: "Deployment status" }));

	// ------------ Assert
	expect(screen.getByText("Deployment status")).toBeVisible();
	expect(mockOnValueChangeFn).toBeCalledWith("deployment-status");
});
