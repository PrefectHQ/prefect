import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { format, set } from "date-fns";
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

const baseSchedule = {
	active: true,
	created: "0",
	deployment_id: "0",
	id: "123",
	updated: "0",
};

describe("IntervalScheduleForm", () => {
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
			...baseSchedule,
			schedule: {
				interval: 3600,
				anchor_date: new Date().toISOString(),
				timezone: "Etc/UTC",
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
		expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent("UTC");
	});

	it("defaults to UTC for new schedules", () => {
		render(<IntervalScheduleFormTest deployment_id="0" onSubmit={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent("UTC");
	});

	it("is able to select a time of day for the anchor date", async () => {
		const user = userEvent.setup();
		render(<IntervalScheduleFormTest deployment_id="0" onSubmit={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		await user.click(screen.getByLabelText(/anchor date/i));
		fireEvent.change(screen.getByLabelText("Time"), {
			target: { value: "14:35" },
		});

		expect(screen.getByLabelText("Time")).toHaveValue("14:35");
		expect(screen.getByLabelText(/anchor date/i)).toHaveTextContent(/02:35 PM/);
	});

	it("keeps the selected time when picking another day", async () => {
		const user = userEvent.setup();
		render(<IntervalScheduleFormTest deployment_id="0" onSubmit={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		const fifteenth = set(new Date(), { date: 15 });

		await user.click(screen.getByLabelText(/anchor date/i));
		fireEvent.change(screen.getByLabelText("Time"), {
			target: { value: "14:35" },
		});
		await user.click(
			screen.getByRole("button", {
				name: format(fifteenth, "EEEE, MMMM do, yyyy"),
			}),
		);

		expect(screen.getByLabelText(/anchor date/i)).toHaveTextContent(
			`${format(fifteenth, "MMM do, yyyy")} at 02:35 PM`,
		);
	});

	it("displays UTC when editing a schedule stored as UTC", () => {
		const MOCK_SCHEDULE = {
			...baseSchedule,
			schedule: {
				interval: 3600,
				anchor_date: new Date().toISOString(),
				timezone: "UTC",
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

		expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent("UTC");
	});
});
