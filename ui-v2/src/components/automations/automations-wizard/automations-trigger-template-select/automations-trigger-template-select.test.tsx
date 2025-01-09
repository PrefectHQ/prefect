import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { AutomationsTriggerTemplateSelect } from "./automations-trigger-template-select";

test("AutomationsTriggerTemplateSelect can select an option", async () => {
	/**
	 * JSDOM doesn't implement PointerEvent so we need to mock our own implementation
	 * Default to mouse left click interaction
	 * https://github.com/radix-ui/primitives/issues/1822
	 * https://github.com/jsdom/jsdom/pull/2666
	 */
	class MockPointerEvent extends Event {
		button: number;
		ctrlKey: boolean;
		pointerType: string;

		constructor(type: string, props: PointerEventInit) {
			super(type, props);
			this.button = props.button || 0;
			this.ctrlKey = props.ctrlKey || false;
			this.pointerType = props.pointerType || "mouse";
		}
	}
	window.PointerEvent = MockPointerEvent as never;
	window.HTMLElement.prototype.scrollIntoView = vi.fn();
	window.HTMLElement.prototype.releasePointerCapture = vi.fn();
	window.HTMLElement.prototype.hasPointerCapture = vi.fn();

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
