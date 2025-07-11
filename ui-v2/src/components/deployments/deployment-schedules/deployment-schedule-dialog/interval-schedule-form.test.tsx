import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/dialog";
import {
	IntervalScheduleForm,
	type IntervalScheduleFormProps,
} from "./interval-schedule-form";

const IntervalScheduleFormTest = (props: IntervalScheduleFormProps) => (
	<>
		<Dialog>
			<IntervalScheduleForm {...props} />
		</Dialog>
	</>
);

describe("CronScheduleForm", () => {
	beforeAll(mockPointerEvents);

	it("is able to create a new interval schedule", async () => {
		// Setup
		const user = userEvent.setup();
		render(<IntervalScheduleFormTest deployment_id="0" onSubmit={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		// Test
		await user.click(screen.getByLabelText(/active/i));
		await user.clear(screen.getByLabelText(/value/i));
		await user.type(screen.getByLabelText(/value/i), "100");

		await user.click(screen.getByLabelText(/interval/i));
		await user.click(screen.getByRole("option", { name: /hours/i }));

		await user.click(screen.getByLabelText(/select timezone/i));
		await user.click(screen.getByRole("option", { name: /africa \/ asmera/i }));
		await user.click(screen.getByRole("button", { name: /save/i }));

		// ------------ Assert

		expect(screen.getByLabelText(/active/i)).not.toBeChecked();
		expect(screen.getByLabelText(/value/i)).toHaveValue("100");
	});

	it("is able to edit an interval schedule", () => {
		// Setup
		const MOCK_SCHEDULE = {
			active: true,
			created: "0",
			deployment_id: "0",
			id: "123",
			updated: "0",
			schedule: {
				interval: 3600,
				anchor_date: new Date().toISOString(),
				timezone: '"Etc/UTC"',
			},
		};

		render(
			<IntervalScheduleFormTest
				deployment_id="0"
				onSubmit={vi.fn()}
				scheduleToEdit={MOCK_SCHEDULE}
			/>,
			{ wrapper: createWrapper() },
		);

		// ------------ Assert

		expect(screen.getByLabelText(/active/i)).toBeChecked();
		expect(screen.getByLabelText(/value/i)).toHaveValue("1");
	});
});
