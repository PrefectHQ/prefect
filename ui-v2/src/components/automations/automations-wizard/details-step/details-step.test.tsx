import { zodResolver } from "@hookform/resolvers/zod";
import { DetailsStep } from "./details-step";

import {
	AutomationWizardSchema,
	type AutomationWizardSchema as TAutomationWizardSchema,
} from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

const DetailsStepFormContainer = () => {
	const form = useForm<TAutomationWizardSchema>({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: { actions: [{ type: undefined }] },
	});

	return (
		<Form {...form}>
			<form>
				<DetailsStep />
			</form>
		</Form>
	);
};

describe("DetailsStep", () => {
	it("able to add details about an automation", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		render(<DetailsStepFormContainer />);

		// ------------ Act
		await user.type(screen.getByLabelText(/automation name/i), "My Automation");
		await user.type(
			screen.getByLabelText(/description \(optional\)/i),
			"My Description",
		);

		// ------------ Assert
		expect(
			screen.getByRole("textbox", { name: /automation name/i }),
		).toHaveValue("My Automation");
		expect(
			screen.getByRole("textbox", { name: /description \(optional\)/i }),
		).toHaveValue("My Description");
	});
});
