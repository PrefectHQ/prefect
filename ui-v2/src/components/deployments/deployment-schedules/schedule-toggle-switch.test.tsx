import { Toaster } from "@/components/ui/toaster";
import { faker } from "@faker-js/faker";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test } from "vitest";
import { ScheduleToggleSwitch } from "./schedule-toggle-switch";

const MOCK_DEPLOYMENT_SCHEDULE = {
	id: faker.string.uuid(),
	created: faker.date.recent().toISOString(),
	updated: faker.date.recent().toISOString(),
	deployment_id: faker.string.uuid(),
	active: true,
	max_scheduled_runs: null,
	schedule: {
		interval: 3600,
		anchor_date: faker.date.recent().toISOString(),
		timezone: "UTC",
	},
};

test("AutomationEnableToggle can toggle switch", async () => {
	const user = userEvent.setup();

	render(
		<>
			<Toaster />
			<ScheduleToggleSwitch deploymentSchedule={MOCK_DEPLOYMENT_SCHEDULE} />
		</>,
		{ wrapper: createWrapper() },
	);

	expect(
		screen.getByRole("switch", { name: /toggle every 1 hour/i }),
	).toBeChecked();

	await user.click(
		screen.getByRole("switch", { name: /toggle every 1 hour/i }),
	);
	expect(screen.getByText(/Deployment schedule inactive/i)).toBeVisible();
});
