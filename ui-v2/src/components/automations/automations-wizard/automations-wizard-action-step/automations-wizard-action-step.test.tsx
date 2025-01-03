import { AutomationsWizardActionStep } from "./automations-wizard-action-step";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

describe("AutomationsWizardActionStep", () => {
	beforeAll(() => {
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
	});

	it("able to select a basic action", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(<AutomationsWizardActionStep onSubmit={mockOnSubmitFn} />);

		// ------------ Act
		await user.click(screen.getByRole("combobox", { name: /select action/i }));
		await user.click(screen.getByRole("option", { name: "Cancel a flow run" }));

		// ------------ Assert
		expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
	});

	it("able to configure change flow run's state action", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(<AutomationsWizardActionStep onSubmit={mockOnSubmitFn} />);

		// ------------ Act
		await user.click(screen.getByRole("combobox", { name: /select action/i }));
		await user.click(
			screen.getByRole("option", { name: "Change flow run's state" }),
		);

		await user.click(screen.getByRole("combobox", { name: /select state/i }));
		await user.click(screen.getByRole("option", { name: "Failed" }));
		await user.type(screen.getByPlaceholderText("Failed"), "test name");
		await user.type(screen.getByLabelText("Message"), "test message");

		// ------------ Assert
		expect(screen.getAllByText("Change flow run's state")).toBeTruthy();
		expect(screen.getAllByText("Failed")).toBeTruthy();
		expect(screen.getByLabelText("Name")).toHaveValue("test name");
		expect(screen.getByLabelText("Message")).toHaveValue("test message");
	});
});
