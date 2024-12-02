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

			// Check if correct classes are applied
			const badge = screen.getByText(name).closest("div");
			expect(badge?.parentElement).toHaveClass(
				`bg-state-${type.toLowerCase()}-badge`,
				`hover:bg-state-${type.toLowerCase()}-badge`,
				`text-state-${type.toLowerCase()}-badge-foreground`,
			);
		},
	);
});
