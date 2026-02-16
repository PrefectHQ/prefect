import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import "@/mocks/mock-json-input";
import { TriggerJsonInput } from "./trigger-json-input";

const TriggerJsonInputContainer = ({
	defaultValue = "",
	error,
}: {
	defaultValue?: string;
	error?: string;
}) => {
	const [value, setValue] = useState(defaultValue);
	return <TriggerJsonInput value={value} onChange={setValue} error={error} />;
};

const validEventTrigger = {
	type: "event",
	posture: "Reactive",
	threshold: 1,
	within: 0,
	expect: ["prefect.flow-run.Completed"],
};

describe("TriggerJsonInput", () => {
	it("renders json input", () => {
		render(<TriggerJsonInputContainer />);

		const textarea = screen.getByRole("textbox");
		expect(textarea).toBeVisible();
	});

	it("shows format button", () => {
		render(<TriggerJsonInputContainer />);

		const formatButton = screen.getByRole("button", { name: "Format" });
		expect(formatButton).toBeVisible();
	});

	it("renders label and description", () => {
		render(<TriggerJsonInputContainer />);

		expect(screen.getByText("Trigger Configuration")).toBeVisible();
		expect(
			screen.getByText(/Edit the trigger configuration as JSON/),
		).toBeVisible();
		expect(screen.getByText("View documentation")).toHaveAttribute(
			"href",
			"https://docs.prefect.io/v3/automate/events/automations-triggers",
		);
	});

	it("formats valid JSON when format button is clicked", async () => {
		const user = userEvent.setup();
		const unformattedJson = '{"type":"event","posture":"Reactive"}';

		render(<TriggerJsonInputContainer defaultValue={unformattedJson} />);

		const formatButton = screen.getByRole("button", { name: "Format" });
		await user.click(formatButton);

		const textarea = screen.getByRole("textbox");
		expect(textarea).toHaveValue(
			JSON.stringify({ type: "event", posture: "Reactive" }, null, 2),
		);
	});

	it("does nothing when format button clicked with invalid JSON", async () => {
		const user = userEvent.setup();
		const invalidJson = "{ invalid json";

		render(<TriggerJsonInputContainer defaultValue={invalidJson} />);

		const formatButton = screen.getByRole("button", { name: "Format" });
		await user.click(formatButton);

		const textarea = screen.getByRole("textbox");
		expect(textarea).toHaveValue(invalidJson);
	});

	it("validates JSON syntax on blur", async () => {
		const user = userEvent.setup();
		const invalidJson = "invalid json syntax";

		render(<TriggerJsonInputContainer defaultValue={invalidJson} />);

		const textarea = screen.getByRole("textbox");
		await user.click(textarea);
		await user.tab(); // Trigger blur

		expect(screen.getByText("Invalid JSON syntax")).toBeVisible();
	});

	it("validates against TriggerSchema on blur", async () => {
		const user = userEvent.setup();
		const validJsonButInvalidTrigger = '{"type": "invalid-type"}';

		render(
			<TriggerJsonInputContainer defaultValue={validJsonButInvalidTrigger} />,
		);

		const textarea = screen.getByRole("textbox");
		await user.click(textarea);
		await user.tab(); // Trigger blur

		// Should show a schema validation error (Zod returns "Invalid input" for union type failures)
		expect(
			screen.getByText(/Invalid input|Invalid trigger configuration/),
		).toBeVisible();
	});

	it("clears errors when valid trigger is entered", async () => {
		const user = userEvent.setup();
		const invalidJson = "invalid json";
		const validJson = JSON.stringify(validEventTrigger);

		render(<TriggerJsonInputContainer defaultValue={invalidJson} />);

		const textarea = screen.getByRole("textbox");
		await user.click(textarea);
		await user.tab(); // Trigger blur to show error

		expect(screen.getByText("Invalid JSON syntax")).toBeVisible();

		// Clear and enter valid JSON by setting the value directly
		await user.clear(textarea);
		// Use fireEvent to set value since userEvent.type has issues with curly braces
		await user.click(textarea);
		// Simulate pasting valid JSON
		await user.paste(validJson);
		await user.tab(); // Trigger blur

		expect(screen.queryByText("Invalid JSON syntax")).not.toBeInTheDocument();
	});

	it("shows external error prop", () => {
		render(<TriggerJsonInputContainer error="External validation error" />);

		expect(screen.getByText("External validation error")).toBeVisible();
	});

	it("prioritizes local error over external error", async () => {
		const user = userEvent.setup();

		render(
			<TriggerJsonInputContainer
				defaultValue="invalid json"
				error="External validation error"
			/>,
		);

		const textarea = screen.getByRole("textbox");
		await user.click(textarea);
		await user.tab(); // Trigger blur to generate local error

		// Local error should be shown, not external
		expect(screen.getByText("Invalid JSON syntax")).toBeVisible();
		expect(
			screen.queryByText("External validation error"),
		).not.toBeInTheDocument();
	});

	it("calls onChange when text is typed", async () => {
		const user = userEvent.setup();

		render(<TriggerJsonInputContainer />);

		const textarea = screen.getByRole("textbox");
		await user.type(textarea, "test");

		expect(textarea).toHaveValue("test");
	});

	it("documentation link opens in new tab", () => {
		render(<TriggerJsonInputContainer />);

		const link = screen.getByText("View documentation");
		expect(link).toHaveAttribute("target", "_blank");
		expect(link).toHaveAttribute("rel", "noopener noreferrer");
	});
});
