import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { TriggerStep } from "./trigger-step";

const TriggerStepFormContainer = () => {
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
				<TriggerStep />
			</form>
		</Form>
	);
};

describe("TriggerStep", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders trigger template select", () => {
		render(<TriggerStepFormContainer />);

		expect(screen.getByLabelText("Trigger Template")).toBeVisible();
	});

	it("shows placeholder text when template is selected", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />);

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Deployment status" }));

		expect(
			screen.getByText("Template selected: deployment-status"),
		).toBeVisible();
	});

	it("can select flow-run-state template", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />);

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Flow run state" }));

		expect(screen.getByText("Template selected: flow-run-state")).toBeVisible();
	});

	it("can select work-pool-status template", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />);

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Work pool status" }));

		expect(
			screen.getByText("Template selected: work-pool-status"),
		).toBeVisible();
	});

	it("can select work-queue-status template", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />);

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Work queue status" }));

		expect(
			screen.getByText("Template selected: work-queue-status"),
		).toBeVisible();
	});

	it("can select custom template", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />);

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Custom" }));

		expect(screen.getByText("Template selected: custom")).toBeVisible();
	});
});
