import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { Dialog } from "@/components/ui/dialog";
import { Toaster } from "@/components/ui/sonner";
import {
	CronScheduleForm,
	type CronScheduleFormProps,
} from "./cron-schedule-form";

const CronScheduleFormTest = (props: CronScheduleFormProps) => (
	<>
		<Toaster />
		<Dialog>
			<CronScheduleForm {...props} />
		</Dialog>
	</>
);

describe("CronScheduleForm", () => {
	beforeAll(mockPointerEvents);

	it("is able to create a new cron schedule", async () => {
		// Setup
		const user = userEvent.setup();
		render(<CronScheduleFormTest deployment_id="0" onSubmit={vi.fn()} />, {
			wrapper: createWrapper(),
		});

		// Test
		await user.click(screen.getByLabelText(/active/i));
		await user.clear(screen.getByLabelText(/value/i));
		await user.type(screen.getByLabelText(/value/i), "* * * * 1/2");

		await user.click(screen.getByRole("switch", { name: /day or/i }));
		await user.click(screen.getByLabelText(/select timezone/i));
		await user.click(screen.getByRole("option", { name: /africa \/ asmera/i }));
		await user.click(screen.getByRole("button", { name: /save/i }));

		// ------------ Assert

		expect(screen.getByLabelText(/active/i)).not.toBeChecked();
		expect(screen.getByLabelText(/value/i)).toHaveValue("* * * * 1/2");

		expect(screen.getByRole("switch", { name: /day or/i })).not.toBeChecked();
	});

	it("is able to edit a cron schedule", () => {
		// Setup
		const MOCK_SCHEDULE = {
			active: true,
			created: "0",
			deployment_id: "0",
			id: "123",
			updated: "0",
			schedule: {
				cron: "* * * * 1/2",
				day_or: true,
				timezone: '"Etc/UTC"',
			},
		};

		render(
			<CronScheduleFormTest
				deployment_id="0"
				onSubmit={vi.fn()}
				scheduleToEdit={MOCK_SCHEDULE}
			/>,
			{ wrapper: createWrapper() },
		);

		// ------------ Assert

		expect(screen.getByLabelText(/active/i)).toBeChecked();
		expect(screen.getByLabelText(/value/i)).toHaveValue("* * * * 1/2");
		expect(screen.getByRole("switch", { name: /day or/i })).toBeChecked();
	});
});
