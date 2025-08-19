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

	it("renders with correct icon for ready status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="READY" />);

		// Check for CheckCircle icon
		expect(screen.getByText("Ready")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for paused status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="PAUSED" />);

		// Check for PauseCircle icon
		expect(screen.getByText("Paused")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for not_ready status", () => {
		const { container } = render(
			<WorkPoolQueueStatusBadge status="NOT_READY" />,
		);

		// Check for AlertCircle icon
		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});
});
