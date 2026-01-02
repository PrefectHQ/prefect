import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { WorkPoolStatusTriggerFields } from "./work-pool-status-trigger-fields";

type Match = Record<string, string | string[]> | undefined;

const WorkPoolStatusTriggerFieldsContainer = ({
	defaultPosture = "Reactive" as const,
	defaultMatch,
	defaultWithin = 0,
	defaultExpect,
}: {
	defaultPosture?: "Reactive" | "Proactive";
	defaultMatch?: Match;
	defaultWithin?: number;
	defaultExpect?: string[];
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
				match: defaultMatch ?? {
					"prefect.resource.id": "prefect.work-pool.*",
				},
				for_each: ["prefect.resource.id"],
				expect: defaultExpect ?? [],
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<WorkPoolStatusTriggerFields />
			</form>
		</Form>
	);
};

describe("WorkPoolStatusTriggerFields", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders posture select with Reactive as default", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("select posture")).toBeVisible();
		expect(
			screen.getByRole("combobox", { name: "select posture" }),
		).toHaveTextContent("Enters");
	});

	it("does not show For field when posture is Reactive", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByText("For")).not.toBeInTheDocument();
	});

	it("shows For field with DurationInput when posture is Proactive", async () => {
		const user = userEvent.setup();

		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		await user.click(screen.getByLabelText("select posture"));
		await user.click(screen.getByRole("option", { name: "Stays in" }));

		expect(screen.getByText("For")).toBeVisible();
		expect(screen.getByLabelText("Duration quantity")).toBeVisible();
		expect(screen.getByLabelText("Duration unit")).toBeVisible();
	});

	it("renders work pool multi-select component", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		// The work pool multi-select button should be rendered
		const workPoolButton = screen.getByRole("button", {
			name: /all work pools|^\+\d+$/i,
		});
		expect(workPoolButton).toBeVisible();
	});

	it("renders Work Pools section label", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Work Pools")).toBeVisible();
	});

	it("renders Work Pool section label for posture and status", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByText("Work Pool")).toBeVisible();
	});

	it("does not render threshold field (removed from UI)", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		expect(screen.queryByLabelText("Threshold")).not.toBeInTheDocument();
	});

	it("renders status select dropdown with Not Ready as default", () => {
		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		// Status defaults to "Not Ready" to match Vue implementation
		const statusTrigger = screen.getByRole("combobox", {
			name: /select status/i,
		});
		expect(statusTrigger).toHaveTextContent("Not Ready");
	});

	it("can select a status from the dropdown", async () => {
		const user = userEvent.setup();

		render(<WorkPoolStatusTriggerFieldsContainer />, {
			wrapper: createWrapper(),
		});

		const statusTrigger = screen.getByRole("combobox", {
			name: /select status/i,
		});
		await user.click(statusTrigger);
		await user.click(screen.getByRole("option", { name: "Ready" }));

		expect(statusTrigger).toHaveTextContent("Ready");
	});

	it("displays DurationInput with correct unit for minutes when Proactive", () => {
		render(
			<WorkPoolStatusTriggerFieldsContainer
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

	it("displays selected status when provided", () => {
		render(
			<WorkPoolStatusTriggerFieldsContainer
				defaultExpect={["prefect.work-pool.ready"]}
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const statusTrigger = screen.getByRole("combobox", {
			name: /select status/i,
		});
		expect(statusTrigger).toHaveTextContent("Ready");
	});
});
