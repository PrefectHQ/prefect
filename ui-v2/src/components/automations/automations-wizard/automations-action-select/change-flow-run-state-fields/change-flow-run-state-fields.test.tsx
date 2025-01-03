import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { useState } from "react";
import { ChangeFlowRunStateFields } from "./change-flow-run-state-fields";

function TestComponent() {
	const [values, setValues] = useState<Record<string, unknown>>({});
	return <ChangeFlowRunStateFields values={values} onChange={setValues} />;
}

test("ChangeFlowRunStateFields can select an option", async () => {
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

	render(<TestComponent />);

	// ------------ Act
	await user.click(screen.getByLabelText("State"));
	await user.click(screen.getByRole("option", { name: "Running" }));

	await user.type(screen.getByLabelText("Name"), "my name");
	await user.type(screen.getByLabelText("Message"), "my message");

	// ------------ Assert
	expect(screen.getByText("Running")).toBeVisible();
	expect(screen.getByLabelText("Name")).toHaveValue("my name");
	expect(screen.getByLabelText("Message")).toHaveValue("my message");
});
