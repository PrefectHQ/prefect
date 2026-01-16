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
	defaultWithin = 0,
}: {
	defaultPosture?: "Reactive" | "Proactive";
	defaultMatchRelated?: MatchRelated;
	defaultWithin?: number;
}) => {
	const form = useForm({
		resolver: zodResolver(AutomationWizardSchema),
		defaultValues: {
			actions: [{ type: undefined }],
			trigger: {
				type: "event" as const,
				posture: defaultPosture,
				threshold: 1,
				within: defaultWithin,
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
		expect(
			screen.getByRole("combobox", { name: "select posture" }),
		).toHaveTextContent("Enters");
	});

	it("does not show For field when posture is Reactive", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByText("For")).not.toBeInTheDocument();
	});

	it("shows For field with DurationInput when posture is Proactive", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		await user.click(screen.getByLabelText("select posture"));
		await user.click(screen.getByRole("option", { name: "Stays in" }));

		expect(screen.getByText("For")).toBeVisible();
		expect(screen.getByLabelText("Duration quantity")).toBeVisible();
		expect(screen.getByLabelText("Duration unit")).toBeVisible();
	});

	it("sets default within value to 30 when switching to Proactive", async () => {
		const user = userEvent.setup();

		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		await user.click(screen.getByLabelText("select posture"));
		await user.click(screen.getByRole("option", { name: "Stays in" }));

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(30);
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

		await user.click(screen.getByText("Any state"));
		await user.click(screen.getByRole("option", { name: /Completed/i }));

		expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
	});

	it("renders flow multi-select with 'All flows' placeholder", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("All flows")).toBeVisible();
	});

	it("renders tags input field when no flows are selected", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Flow Run Tags")).toBeVisible();
		expect(screen.getByPlaceholderText("All tags")).toBeVisible();
	});

	it("hides tags input field when flows are selected", () => {
		render(
			<FlowRunStateTriggerFieldsContainer
				defaultMatchRelated={{
					"prefect.resource.role": "flow",
					"prefect.resource.id": ["prefect.flow.flow-id-1"],
				}}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(screen.queryByText("Flow Run Tags")).not.toBeInTheDocument();
		expect(screen.queryByPlaceholderText("All tags")).not.toBeInTheDocument();
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

		const tagsInput = screen.getByPlaceholderText("All tags");
		await user.type(tagsInput, "new-tag{Enter}");

		expect(screen.getByText("new-tag")).toBeVisible();
	});

	it("renders Flow Run section label", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Flow Run")).toBeVisible();
	});

	it("does not render threshold field (removed from UI)", () => {
		render(<FlowRunStateTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByLabelText("Threshold")).not.toBeInTheDocument();
	});

	it("displays DurationInput with correct unit for minutes", () => {
		render(
			<FlowRunStateTriggerFieldsContainer
				defaultPosture="Proactive"
				defaultWithin={120}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(2);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Minutes");
	});
});
