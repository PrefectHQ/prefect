import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
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
		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		expect(screen.getByLabelText("Trigger Template")).toBeVisible();
	});

	it("can select deployment-status template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Deployment status" }));

		// Should show the DeploymentStatusTriggerFields component
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByLabelText("Threshold")).toBeVisible();
	});

	it("can select flow-run-state template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Flow run state" }));

		// Should show the FlowRunStateTriggerFields component
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByLabelText("Threshold")).toBeVisible();
	});

	it("can select work-pool-status template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Work pool status" }));

		// Should show the WorkPoolStatusTriggerFields component
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByLabelText("Threshold")).toBeVisible();
	});

	it("can select work-queue-status template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Work queue status" }));

		// Should show the WorkQueueStatusTriggerFields component
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByLabelText("Threshold")).toBeVisible();
	});

	it("can select custom template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Custom" }));

		// Should show the CustomTriggerFields component
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByLabelText("Threshold")).toBeVisible();
		expect(
			screen.getByLabelText("Expected Events (one per line)"),
		).toBeVisible();
	});
});
