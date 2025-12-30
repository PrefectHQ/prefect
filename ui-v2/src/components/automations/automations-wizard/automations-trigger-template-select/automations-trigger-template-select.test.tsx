import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, test, vi } from "vitest";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";

import {
	AutomationsTriggerTemplateSelect,
	TriggerTemplateSelectField,
} from "./automations-trigger-template-select";

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

const TriggerTemplateSelectFieldFormContainer = ({
	onTemplateChange,
}: {
	onTemplateChange?: (template: string) => void;
}) => {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture: "Reactive" as const,
				threshold: 1,
				within: 0,
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<TriggerTemplateSelectField onTemplateChange={onTemplateChange} />
			</form>
		</Form>
	);
};

describe("TriggerTemplateSelectField", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	test("renders within form context", () => {
		render(<TriggerTemplateSelectFieldFormContainer />);

		expect(screen.getByLabelText("Trigger Template")).toBeVisible();
	});

	test("updates form state when selecting an option", async () => {
		const user = userEvent.setup();

		render(<TriggerTemplateSelectFieldFormContainer />);

		// ------------ Act
		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Deployment status" }));

		// ------------ Assert
		expect(screen.getByRole("combobox")).toHaveTextContent("Deployment status");
	});

	test("calls onTemplateChange callback when selecting an option", async () => {
		const user = userEvent.setup();
		const mockOnTemplateChange = vi.fn();

		render(
			<TriggerTemplateSelectFieldFormContainer
				onTemplateChange={mockOnTemplateChange}
			/>,
		);

		// ------------ Act
		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Deployment status" }));

		// ------------ Assert
		expect(mockOnTemplateChange).toHaveBeenCalledWith("deployment-status");
	});

	test("works without onTemplateChange callback", async () => {
		const user = userEvent.setup();

		render(<TriggerTemplateSelectFieldFormContainer />);

		// ------------ Act
		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Flow run state" }));

		// ------------ Assert
		expect(screen.getByRole("combobox")).toHaveTextContent("Flow run state");
	});
});
