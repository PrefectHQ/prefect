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

	test.each(states)(
		"renders correct icon and classes for $type state",
		({ type, name }) => {
			render(<StateBadge type={type} name={name} />);

			// Check if state name is rendered
			expect(screen.getByText(name)).toBeInTheDocument();

			// Check if correct classes are applied based on the CLASSES mapping
			const badge = screen.getByText(name).closest("span");
			const expectedClasses = {
				COMPLETED: "bg-green-50 text-green-600 hover:bg-green-50",
				FAILED: "bg-red-50 text-red-600 hover:bg-red-50",
				RUNNING: "bg-blue-100 text-blue-700 hover:bg-blue-100",
				CANCELLED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
				CANCELLING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
				CRASHED: "bg-orange-50 text-orange-600 hover:bg-orange-50",
				PAUSED: "bg-gray-300 text-gray-800 hover:bg-gray-300",
				PENDING: "bg-gray-300 text-gray-800 hover:bg-gray-300",
				SCHEDULED: "bg-yellow-100 text-yellow-700 hover:bg-yellow-100",
			}[type];

			expect(badge).toHaveClass(...expectedClasses.split(" "));
		},
	);
});
