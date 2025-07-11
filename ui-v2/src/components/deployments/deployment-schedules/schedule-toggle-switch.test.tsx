import { randRecentDate, randUuid } from "@ngneat/falso";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { expect, test } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { ScheduleToggleSwitch } from "./schedule-toggle-switch";

const MOCK_DEPLOYMENT_SCHEDULE = {
	id: randUuid(),
	created: randRecentDate().toISOString(),
	updated: randRecentDate().toISOString(),
	deployment_id: randUuid(),
	active: true,
	max_scheduled_runs: null,
	schedule: {
		interval: 3600,
		anchor_date: randRecentDate().toISOString(),
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

	await waitFor(() => {
		expect(screen.getByText(/Deployment schedule paused/i)).toBeVisible();
	});
});
