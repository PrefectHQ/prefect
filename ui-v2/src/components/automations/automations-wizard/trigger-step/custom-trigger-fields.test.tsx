import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { FormProvider, useForm } from "react-hook-form";
import { beforeAll, describe, expect, it } from "vitest";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { CustomTriggerFields } from "./custom-trigger-fields";

const createWrapper = (defaultValues?: Partial<AutomationWizardSchema>) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const Wrapper = ({ children }: { children: React.ReactNode }) => {
		const form = useForm<AutomationWizardSchema>({
			defaultValues: {
				trigger: {
					type: "event",
					posture: "Reactive",
					threshold: 1,
					within: 0,
					expect: [],
					after: [],
					match: {},
					match_related: {},
					...defaultValues?.trigger,
				},
				...defaultValues,
			},
		});

		return (
			<QueryClientProvider client={queryClient}>
				<FormProvider {...form}>{children}</FormProvider>
			</QueryClientProvider>
		);
	};

	return Wrapper;
};

describe("CustomTriggerFields", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders posture radio buttons", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		expect(screen.getByLabelText("Observe")).toBeVisible();
		expect(screen.getByLabelText("Don't observe")).toBeVisible();
	});

	it("renders expected events combobox", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		expect(screen.getByText("Any event matching")).toBeVisible();
		expect(screen.getByText("All events")).toBeVisible();
	});

	it("renders resource filter combobox", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		expect(screen.getByText("From the following resources")).toBeVisible();
		expect(screen.getByText("All resources")).toBeVisible();
	});

	it("renders threshold input", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		const thresholdInputs = screen.getAllByRole("spinbutton");
		expect(thresholdInputs.length).toBeGreaterThanOrEqual(1);
		expect(thresholdInputs[0]).toBeVisible();
		expect(thresholdInputs[0]).toHaveValue(1);
	});

	it("renders within duration input", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		expect(screen.getByText("time within")).toBeVisible();
	});

	it("renders evaluation options accordion", () => {
		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		expect(screen.getByText("Evaluation Options")).toBeVisible();
	});

	it("can expand evaluation options accordion", async () => {
		const user = userEvent.setup();

		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		await user.click(screen.getByText("Evaluation Options"));

		expect(
			screen.getByText(
				"Evaluate trigger only after observing an event matching",
			),
		).toBeVisible();
		expect(screen.getByText("Filter for events related to")).toBeVisible();
	});

	it("shows plural 'times' when threshold is greater than 1", () => {
		render(<CustomTriggerFields />, {
			wrapper: createWrapper({
				trigger: {
					type: "event",
					posture: "Reactive",
					threshold: 5,
					within: 0,
					expect: [],
					after: [],
					match: {},
					match_related: {},
				},
			}),
		});

		expect(screen.getByText("times within")).toBeVisible();
	});

	it("shows singular 'time' when threshold is 1", () => {
		render(<CustomTriggerFields />, {
			wrapper: createWrapper({
				trigger: {
					type: "event",
					posture: "Reactive",
					threshold: 1,
					within: 0,
					expect: [],
					after: [],
					match: {},
					match_related: {},
				},
			}),
		});

		expect(screen.getByText("time within")).toBeVisible();
	});

	it("can switch between postures", async () => {
		const user = userEvent.setup();

		render(<CustomTriggerFields />, { wrapper: createWrapper() });

		const observeRadio = screen.getByLabelText("Observe");
		const dontObserveRadio = screen.getByLabelText("Don't observe");

		expect(observeRadio).toBeChecked();
		expect(dontObserveRadio).not.toBeChecked();

		await user.click(dontObserveRadio);

		expect(observeRadio).not.toBeChecked();
		expect(dontObserveRadio).toBeChecked();
	});
});
