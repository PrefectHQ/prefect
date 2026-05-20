import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it } from "vitest";
import { DeploymentScheduleItem } from "./deployment-schedule-item";

const ACTIVE_SCHEDULE = {
	id: "schedule-1",
	created: new Date().toISOString(),
	updated: new Date().toISOString(),
	deployment_id: "deployment-1",
	active: true,
	max_scheduled_runs: null,
	schedule: {
		interval: 3600,
		anchor_date: new Date().toISOString(),
		timezone: "UTC",
	},
};

const PAUSED_SCHEDULE = {
	id: "schedule-2",
	created: new Date().toISOString(),
	updated: new Date().toISOString(),
	deployment_id: "deployment-1",
	active: false,
	max_scheduled_runs: null,
	schedule: {
		interval: 3600,
		anchor_date: new Date().toISOString(),
		timezone: "UTC",
	},
};

const getStatusIndicator = (container: HTMLElement) => {
	const triggers = container.querySelectorAll('[data-slot="tooltip-trigger"]');
	return triggers[0] as HTMLElement;
};

describe("DeploymentScheduleItem", () => {
	it("shows active status when schedule is active and controls are not disabled", async () => {
		const user = userEvent.setup();

		const { container } = render(
			<DeploymentScheduleItem
				deploymentSchedule={ACTIVE_SCHEDULE}
				disabled={false}
				onEditSchedule={() => {}}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.hover(getStatusIndicator(container));
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toHaveTextContent(
				"Schedule is active",
			);
		});
	});

	it("shows active status when schedule is active even when controls are disabled", async () => {
		const user = userEvent.setup();

		const { container } = render(
			<DeploymentScheduleItem
				deploymentSchedule={ACTIVE_SCHEDULE}
				disabled={true}
				onEditSchedule={() => {}}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.hover(getStatusIndicator(container));
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toHaveTextContent(
				"Schedule is active",
			);
		});
	});

	it("shows paused status when schedule is paused", async () => {
		const user = userEvent.setup();

		const { container } = render(
			<DeploymentScheduleItem
				deploymentSchedule={PAUSED_SCHEDULE}
				disabled={false}
				onEditSchedule={() => {}}
			/>,
			{ wrapper: createWrapper() },
		);

		await user.hover(getStatusIndicator(container));
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toHaveTextContent(
				"Schedule is paused",
			);
		});
	});

	it("disables the toggle switch when disabled prop is true", () => {
		render(
			<DeploymentScheduleItem
				deploymentSchedule={ACTIVE_SCHEDULE}
				disabled={true}
				onEditSchedule={() => {}}
			/>,
			{ wrapper: createWrapper() },
		);

		const toggle = screen.getByRole("switch");
		expect(toggle).toBeDisabled();
	});

	it("enables the toggle switch when disabled prop is false", () => {
		render(
			<DeploymentScheduleItem
				deploymentSchedule={ACTIVE_SCHEDULE}
				disabled={false}
				onEditSchedule={() => {}}
			/>,
			{ wrapper: createWrapper() },
		);

		const toggle = screen.getByRole("switch");
		expect(toggle).toBeEnabled();
	});
});
