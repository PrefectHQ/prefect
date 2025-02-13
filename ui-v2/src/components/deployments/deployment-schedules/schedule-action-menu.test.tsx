import { Toaster } from "@/components/ui/toaster";
import { faker } from "@faker-js/faker";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createWrapper } from "@tests/utils";
import { ScheduleActionMenu } from "./schedule-action-menu";

const MOCK_DEPLOYMENT_SCHEDULE = {
	id: faker.string.uuid(),
	created: faker.date.recent().toISOString(),
	updated: faker.date.recent().toISOString(),
	deployment_id: faker.string.uuid(),
	active: true,
	max_scheduled_runs: null,
	schedule: {
		cron: "1 * * * *",
		timezone: "UTC",
		day_or: true,
	},
};

describe("ScheduleActionMenu", () => {
	it("copies the id", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<ScheduleActionMenu
					deploymentSchedule={MOCK_DEPLOYMENT_SCHEDULE}
					onEditSchedule={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: "Copy ID" }));

		// ------------ Assert
		expect(screen.getByText("ID copied")).toBeVisible();
	});

	it("calls edit option", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnEditScheduleFn = vi.fn();
		render(
			<>
				<Toaster />
				<ScheduleActionMenu
					deploymentSchedule={MOCK_DEPLOYMENT_SCHEDULE}
					onEditSchedule={mockOnEditScheduleFn}
				/>
			</>,
			{ wrapper: createWrapper() },
		);
		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /edit/i }));

		// ------------ Assert
		expect(mockOnEditScheduleFn).toBeCalledWith(MOCK_DEPLOYMENT_SCHEDULE.id);
	});

	it("calls delete option and deletes schedule", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<ScheduleActionMenu
					deploymentSchedule={MOCK_DEPLOYMENT_SCHEDULE}
					onEditSchedule={vi.fn()}
				/>
			</>,
			{ wrapper: createWrapper() },
		);
		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));

		await user.click(screen.getByRole("button", { name: /delete/i }));

		// ------------ Assert
		await waitFor(() =>
			expect(screen.getByText("Schedule deleted")).toBeVisible(),
		);
		expect(
			screen.queryByRole("heading", { name: /delete schedule/i }),
		).not.toBeInTheDocument();
	});
});
