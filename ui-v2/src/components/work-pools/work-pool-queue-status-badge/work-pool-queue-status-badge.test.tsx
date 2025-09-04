import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkPoolQueueStatus } from "@/api/work-pool-queues";
import { WorkPoolQueueStatusBadge } from "./work-pool-queue-status-badge";

describe("WorkPoolQueueStatusBadge", () => {
	const testCases: Array<{
		status: WorkPoolQueueStatus;
		expectedLabel: string;
	}> = [
		{
			status: "READY",
			expectedLabel: "Ready",
		},
		{
			status: "PAUSED",
			expectedLabel: "Paused",
		},
		{
			status: "NOT_READY",
			expectedLabel: "Not Ready",
		},
	];

	testCases.forEach(({ status, expectedLabel }) => {
		it(`displays ${status} status correctly`, () => {
			render(<WorkPoolQueueStatusBadge status={status} />);

			expect(screen.getByText(expectedLabel)).toBeInTheDocument();
		});
	});

	it("applies custom className", () => {
		const { container } = render(
			<WorkPoolQueueStatusBadge status="READY" className="custom-class" />,
		);

		const badge = container.querySelector(".custom-class");
		expect(badge).toBeInTheDocument();
	});

	it("renders with correct circle for ready status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="READY" />);

		// Check for green circle
		expect(screen.getByText("Ready")).toBeInTheDocument();
		const circle = container.querySelector(
			".h-2.w-2.rounded-full.bg-green-500",
		);
		expect(circle).toBeInTheDocument();
	});

	it("renders with correct icon for paused status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="PAUSED" />);

		// Check for pause icon instead of yellow circle
		expect(screen.getByText("Paused")).toBeInTheDocument();
		const pauseIcon = container.querySelector("svg");
		expect(pauseIcon).toBeInTheDocument();
		// Verify it's not looking for the old yellow circle
		const yellowCircle = container.querySelector(
			".h-2.w-2.rounded-full.bg-yellow-500",
		);
		expect(yellowCircle).not.toBeInTheDocument();
	});

	it("renders with correct circle for not_ready status", () => {
		const { container } = render(
			<WorkPoolQueueStatusBadge status="NOT_READY" />,
		);

		// Check for red circle
		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		const circle = container.querySelector(".h-2.w-2.rounded-full.bg-red-500");
		expect(circle).toBeInTheDocument();
	});
});
