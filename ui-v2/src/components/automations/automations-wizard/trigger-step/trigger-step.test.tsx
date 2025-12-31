import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import "@/mocks/mock-json-input";
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
		// Note: Flow run state trigger does not have a Threshold field (removed to match Vue)
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByText("Flows")).toBeVisible();
	});

	it("can select work-pool-status template and shows trigger fields", async () => {
		const user = userEvent.setup();

		render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

		await user.click(screen.getByLabelText("Trigger Template"));
		await user.click(screen.getByRole("option", { name: "Work pool status" }));

		// Should show the WorkPoolStatusTriggerFields component
		// Note: Work pool status trigger does not have a Threshold field (removed to match Vue)
		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(screen.getByText("Work Pools")).toBeVisible();
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

	describe("Form/JSON toggle", () => {
		it("renders Form and JSON tabs when a template is selected", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			expect(screen.getByRole("tab", { name: "Form" })).toBeVisible();
			expect(screen.getByRole("tab", { name: "JSON" })).toBeVisible();
		});

		it("shows Form tab as selected by default", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			const formTab = screen.getByRole("tab", { name: "Form" });
			expect(formTab).toHaveAttribute("aria-selected", "true");
		});

		it("switches to JSON mode and displays trigger as JSON", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Should show JSON editor with trigger configuration
			expect(screen.getByText("Trigger Configuration")).toBeVisible();
			expect(screen.getByRole("tab", { name: "JSON" })).toHaveAttribute(
				"aria-selected",
				"true",
			);
		});

		it("switches from JSON to Form with valid JSON", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Switch to JSON mode
			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Switch back to Form mode (JSON should be valid)
			await user.click(screen.getByRole("tab", { name: "Form" }));

			// Should be back in Form mode
			expect(screen.getByRole("tab", { name: "Form" })).toHaveAttribute(
				"aria-selected",
				"true",
			);
			expect(screen.getByLabelText("select posture")).toBeVisible();
		});

		it("blocks switch from JSON to Form with invalid JSON", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Switch to JSON mode
			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Find the JSON input and clear it, then type invalid JSON
			const jsonInput = screen.getByRole("textbox");
			await user.clear(jsonInput);
			await user.type(jsonInput, "{{invalid json");

			// Try to switch back to Form mode
			await user.click(screen.getByRole("tab", { name: "Form" }));

			// Should stay in JSON mode and show error
			expect(screen.getByRole("tab", { name: "JSON" })).toHaveAttribute(
				"aria-selected",
				"true",
			);
			expect(screen.getByText("Invalid JSON syntax")).toBeVisible();
		});

		it("syncs valid JSON changes to form state", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			// Use deployment-status template which has a Threshold field
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(
				screen.getByRole("option", { name: "Deployment status" }),
			);

			// Switch to JSON mode
			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Find the JSON input and modify the threshold value
			// Use user.paste instead of user.type because user.type interprets {} as keyboard modifiers
			const jsonInput = screen.getByRole("textbox");
			await user.clear(jsonInput);
			const validJson = JSON.stringify(
				{
					type: "event",
					posture: "Reactive",
					threshold: 5,
					within: 0,
				},
				null,
				2,
			);
			await user.click(jsonInput);
			await user.paste(validJson);

			// Switch back to Form mode
			await user.click(screen.getByRole("tab", { name: "Form" }));

			// The form should reflect the updated threshold
			const thresholdInput = screen.getByLabelText("Threshold");
			expect(thresholdInput).toHaveValue(5);
		});

		it("resets JSON when template changes", async () => {
			const user = userEvent.setup();

			render(<TriggerStepFormContainer />, { wrapper: createWrapper() });

			// Select first template
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(screen.getByRole("option", { name: "Flow run state" }));

			// Switch to JSON mode
			await user.click(screen.getByRole("tab", { name: "JSON" }));

			// Verify JSON is displayed
			expect(screen.getByText("Trigger Configuration")).toBeVisible();

			// Change template
			await user.click(screen.getByLabelText("Trigger Template"));
			await user.click(
				screen.getByRole("option", { name: "Deployment status" }),
			);

			// Should still show Form/JSON tabs
			expect(screen.getByRole("tab", { name: "Form" })).toBeVisible();
			expect(screen.getByRole("tab", { name: "JSON" })).toBeVisible();
		});
	});
});
