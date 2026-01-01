import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Form } from "@/components/ui/form";
import { CustomPostureSelect } from "./index";

const CustomPostureSelectFormContainer = ({
	defaultPosture = "Reactive",
	defaultExpect = [],
	defaultAfter = [],
	defaultWithin = 0,
}: {
	defaultPosture?: "Reactive" | "Proactive";
	defaultExpect?: string[];
	defaultAfter?: string[];
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
				expect: defaultExpect,
				after: defaultAfter,
			},
		},
	});

	return (
		<Form {...form}>
			<form>
				<CustomPostureSelect />
				<div data-testid="form-values">
					<span data-testid="posture">{form.watch("trigger.posture")}</span>
					<span data-testid="expect">
						{JSON.stringify(form.watch("trigger.expect"))}
					</span>
					<span data-testid="after">
						{JSON.stringify(form.watch("trigger.after"))}
					</span>
					<span data-testid="within">{form.watch("trigger.within")}</span>
				</div>
			</form>
		</Form>
	);
};

describe("CustomPostureSelect", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders with 'When I' label", () => {
		render(<CustomPostureSelectFormContainer />, { wrapper: createWrapper() });

		expect(screen.getByText("When I")).toBeVisible();
	});

	it("renders 'Observe' and 'Don't observe' radio options", () => {
		render(<CustomPostureSelectFormContainer />, { wrapper: createWrapper() });

		expect(screen.getByLabelText("Observe")).toBeVisible();
		expect(screen.getByLabelText("Don't observe")).toBeVisible();
	});

	it("has 'Observe' selected by default when posture is Reactive", () => {
		render(<CustomPostureSelectFormContainer defaultPosture="Reactive" />, {
			wrapper: createWrapper(),
		});

		const observeRadio = screen.getByLabelText("Observe");
		expect(observeRadio).toBeChecked();
	});

	it("has 'Don't observe' selected when posture is Proactive", () => {
		render(<CustomPostureSelectFormContainer defaultPosture="Proactive" />, {
			wrapper: createWrapper(),
		});

		const dontObserveRadio = screen.getByLabelText("Don't observe");
		expect(dontObserveRadio).toBeChecked();
	});

	it("switches from Reactive to Proactive when clicking 'Don't observe'", async () => {
		const user = userEvent.setup();

		render(<CustomPostureSelectFormContainer defaultPosture="Reactive" />, {
			wrapper: createWrapper(),
		});

		const dontObserveRadio = screen.getByLabelText("Don't observe");
		await user.click(dontObserveRadio);

		expect(screen.getByTestId("posture")).toHaveTextContent("Proactive");
	});

	it("switches from Proactive to Reactive when clicking 'Observe'", async () => {
		const user = userEvent.setup();

		render(<CustomPostureSelectFormContainer defaultPosture="Proactive" />, {
			wrapper: createWrapper(),
		});

		const observeRadio = screen.getByLabelText("Observe");
		await user.click(observeRadio);

		expect(screen.getByTestId("posture")).toHaveTextContent("Reactive");
	});

	it("moves expect values to after when switching from Reactive to Proactive", async () => {
		const user = userEvent.setup();

		render(
			<CustomPostureSelectFormContainer
				defaultPosture="Reactive"
				defaultExpect={["prefect.flow-run.Completed"]}
			/>,
			{ wrapper: createWrapper() },
		);

		// Verify initial state
		expect(screen.getByTestId("expect")).toHaveTextContent(
			'["prefect.flow-run.Completed"]',
		);
		expect(screen.getByTestId("after")).toHaveTextContent("[]");

		// Switch to Proactive
		const dontObserveRadio = screen.getByLabelText("Don't observe");
		await user.click(dontObserveRadio);

		// Values should be moved from expect to after
		expect(screen.getByTestId("expect")).toHaveTextContent("[]");
		expect(screen.getByTestId("after")).toHaveTextContent(
			'["prefect.flow-run.Completed"]',
		);
	});

	it("moves after values to expect when switching from Proactive to Reactive", async () => {
		const user = userEvent.setup();

		render(
			<CustomPostureSelectFormContainer
				defaultPosture="Proactive"
				defaultAfter={["prefect.flow-run.Failed"]}
				defaultWithin={30}
			/>,
			{ wrapper: createWrapper() },
		);

		// Verify initial state
		expect(screen.getByTestId("after")).toHaveTextContent(
			'["prefect.flow-run.Failed"]',
		);
		expect(screen.getByTestId("expect")).toHaveTextContent("[]");

		// Switch to Reactive
		const observeRadio = screen.getByLabelText("Observe");
		await user.click(observeRadio);

		// Values should be moved from after to expect
		expect(screen.getByTestId("after")).toHaveTextContent("[]");
		expect(screen.getByTestId("expect")).toHaveTextContent(
			'["prefect.flow-run.Failed"]',
		);
	});

	it("sets within to 30 when switching to Proactive if within is 0", async () => {
		const user = userEvent.setup();

		render(
			<CustomPostureSelectFormContainer
				defaultPosture="Reactive"
				defaultWithin={0}
			/>,
			{ wrapper: createWrapper() },
		);

		// Verify initial within is 0
		expect(screen.getByTestId("within")).toHaveTextContent("0");

		// Switch to Proactive
		const dontObserveRadio = screen.getByLabelText("Don't observe");
		await user.click(dontObserveRadio);

		// Within should be set to 30
		expect(screen.getByTestId("within")).toHaveTextContent("30");
	});

	it("preserves within value when switching to Proactive if within is not 0", async () => {
		const user = userEvent.setup();

		render(
			<CustomPostureSelectFormContainer
				defaultPosture="Reactive"
				defaultWithin={60}
			/>,
			{ wrapper: createWrapper() },
		);

		// Verify initial within is 60
		expect(screen.getByTestId("within")).toHaveTextContent("60");

		// Switch to Proactive
		const dontObserveRadio = screen.getByLabelText("Don't observe");
		await user.click(dontObserveRadio);

		// Within should remain 60
		expect(screen.getByTestId("within")).toHaveTextContent("60");
	});
});
