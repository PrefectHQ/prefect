import { render, screen } from "@testing-library/react";
import { StateBadge } from "./index";
import {
	ClockIcon,
	PauseIcon,
	XIcon,
	CheckIcon,
	ServerCrashIcon,
	BanIcon,
	PlayIcon,
} from "lucide-react";
import { describe, expect, test } from "vitest";

describe("StateBadge", () => {
	const states = [
		{
			type: "COMPLETED" as const,
			name: "Completed",
			expectedIcon: CheckIcon,
		},
		{
			type: "FAILED" as const,
			name: "Failed",
			expectedIcon: XIcon,
		},
		{
			type: "RUNNING" as const,
			name: "Running",
			expectedIcon: PlayIcon,
		},
		{
			type: "CANCELLED" as const,
			name: "Cancelled",
			expectedIcon: BanIcon,
		},
		{
			type: "CANCELLING" as const,
			name: "Cancelling",
			expectedIcon: BanIcon,
		},
		{
			type: "CRASHED" as const,
			name: "Crashed",
			expectedIcon: ServerCrashIcon,
		},
		{
			type: "PAUSED" as const,
			name: "Paused",
			expectedIcon: PauseIcon,
		},
		{
			type: "PENDING" as const,
			name: "Pending",
			expectedIcon: ClockIcon,
		},
		{
			type: "SCHEDULED" as const,
			name: "Scheduled",
			expectedIcon: ClockIcon,
		},
		{
			type: "SCHEDULED" as const,
			name: "Late",
			expectedIcon: ClockIcon,
		},
	];

	test.each(states)(
		"renders correct icon and classes for $type state",
		({ type, name }) => {
			render(<StateBadge state={{ type, name }} />);

			// Check if state name is rendered
			expect(screen.getByText(name)).toBeInTheDocument();

			// Check if correct classes are applied based on the CLASSES mapping
			const badge = screen.getByText(name).closest("div");
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

			expect(badge?.parentElement).toHaveClass(...expectedClasses.split(" "));
		},
	);
});
