import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import { ICONS } from "@/components/ui/icons";
import { StateBadge } from "./index";

describe("StateBadge", () => {
	const states = [
		{
			type: "COMPLETED" as const,
			name: "Completed",
			expectedIcon: ICONS.Check,
		},
		{
			type: "FAILED" as const,
			name: "Failed",
			expectedIcon: ICONS.X,
		},
		{
			type: "RUNNING" as const,
			name: "Running",
			expectedIcon: ICONS.Play,
		},
		{
			type: "CANCELLED" as const,
			name: "Cancelled",
			expectedIcon: ICONS.Ban,
		},
		{
			type: "CANCELLING" as const,
			name: "Cancelling",
			expectedIcon: ICONS.Ban,
		},
		{
			type: "CRASHED" as const,
			name: "Crashed",
			expectedIcon: ICONS.ServerCrash,
		},
		{
			type: "PAUSED" as const,
			name: "Paused",
			expectedIcon: ICONS.Pause,
		},
		{
			type: "PENDING" as const,
			name: "Pending",
			expectedIcon: ICONS.Clock,
		},
		{
			type: "SCHEDULED" as const,
			name: "Scheduled",
			expectedIcon: ICONS.Clock,
		},
		{
			type: "SCHEDULED" as const,
			name: "Late",
			expectedIcon: ICONS.Clock,
		},
	];

	test.each(states)("renders correct icon and classes for $type state", ({
		type,
		name,
	}) => {
		render(<StateBadge type={type} name={name} />);

		// Check if state name is rendered
		expect(screen.getByText(name)).toBeInTheDocument();

		// Check if correct classes are applied based on the CLASSES mapping
		const badge = screen.getByText(name).closest("span");
		const expectedClasses = {
			COMPLETED:
				"bg-state-completed-50 text-state-completed-600 hover:bg-state-completed-100",
			FAILED:
				"bg-state-failed-50 text-state-failed-700 hover:bg-state-failed-100",
			RUNNING:
				"bg-state-running-50 text-state-running-700 hover:bg-state-running-100",
			CANCELLED:
				"bg-state-cancelled-50 text-state-cancelled-600 hover:bg-state-cancelled-100",
			CANCELLING:
				"bg-state-cancelling-50 text-state-cancelling-600 hover:bg-state-cancelling-100",
			CRASHED:
				"bg-state-crashed-50 text-state-crashed-600 hover:bg-state-crashed-100",
			PAUSED:
				"bg-state-paused-100 text-state-paused-700 hover:bg-state-paused-200",
			PENDING:
				"bg-state-pending-100 text-state-pending-700 hover:bg-state-pending-200",
			SCHEDULED:
				"bg-state-scheduled-50 text-state-scheduled-700 hover:bg-state-scheduled-100",
		}[type];

		expect(badge).toHaveClass(...expectedClasses.split(" "));
	});
});
