import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { FlowRunStateTriggerFields } from "./flow-run-state-trigger-fields";

type MatchRelated = Record<string, string | string[]> | undefined;

const FlowRunStateTriggerFieldsContainer = ({
	defaultPosture = "Reactive" as const,
	defaultMatchRelated,
}: {
	defaultPosture?: "Reactive" | "Proactive";
	defaultMatchRelated?: MatchRelated;
}) => {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture: defaultPosture,
				threshold: 1,
				within: 0,
				match_related: defaultMatchRelated,
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<FlowRunStateTriggerFields />
			</form>
		</Form>
	);
};

describe("FlowRunStateTriggerFields", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders posture select with Reactive as default", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("select posture")).toBeVisible();
		// The select should show "Enters" as the selected value
		expect(
			screen.getByRole("combobox", { name: "select posture" }),
		).toHaveTextContent("Enters");
	});

	it("renders threshold input", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		const thresholdInput = screen.getByLabelText("Threshold");
		expect(thresholdInput).toBeVisible();
		expect(thresholdInput).toHaveValue(1);
	});

	it("does not show within field when posture is Reactive", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByLabelText("Within (seconds)")).not.toBeInTheDocument();
	});

	it("shows within field when posture is Proactive", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		// Change posture to Proactive
		await user.click(screen.getByLabelText("select posture"));
		await user.click(screen.getByRole("option", { name: "Stays in" }));

		expect(screen.getByLabelText("Within (seconds)")).toBeVisible();
	});

	it("sets default within value to 30 when switching to Proactive", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		// Change posture to Proactive
		await user.click(screen.getByLabelText("select posture"));
		await user.click(screen.getByRole("option", { name: "Stays in" }));

		const withinInput = screen.getByLabelText("Within (seconds)");
		expect(withinInput).toHaveValue(30);
	});

	it("renders state multi-select", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Any state")).toBeVisible();
	});

	it("can select states from the multi-select", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		// Open the state multi-select
		await user.click(screen.getByText("Any state"));

		// Select a state
		await user.click(screen.getByRole("option", { name: /Completed/i }));

		// The state should now be selected
		expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
	});

	it("can change threshold value", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		const thresholdInput = screen.getByLabelText("Threshold");
		await user.clear(thresholdInput);
		await user.type(thresholdInput, "5");

		expect(thresholdInput).toHaveValue(5);
	});

	it("renders flow multi-select with 'Any flow' placeholder", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Any flow")).toBeVisible();
	});

	it("renders tags input field", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("Enter tags")).toBeVisible();
	});

	it("displays selected tags from match_related", () => {
		render(
			<FlowRunStateTriggerFieldsContainer
				defaultMatchRelated={{
					"prefect.resource.role": "flow",
					"prefect.resource.id": [
						"prefect.tag.production",
						"prefect.tag.critical",
					],
				}}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.getByText("production")).toBeVisible();
		expect(screen.getByText("critical")).toBeVisible();
	});

	it("can add a tag using the tags input", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		const tagsInput = screen.getByLabelText("Enter tags");
		await user.type(tagsInput, "new-tag{Enter}");

		expect(screen.getByText("new-tag")).toBeVisible();
	});
});
