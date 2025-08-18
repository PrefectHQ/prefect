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
			status: "ready",
			expectedLabel: "Ready",
		},
		{
			status: "paused",
			expectedLabel: "Paused",
		},
		{
			status: "not_ready",
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
			<WorkPoolQueueStatusBadge status="ready" className="custom-class" />,
		);

		const badge = container.querySelector(".custom-class");
		expect(badge).toBeInTheDocument();
	});

	it("renders with correct icon for ready status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="ready" />);

		// Check for CheckCircle icon
		expect(screen.getByText("Ready")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for paused status", () => {
		const { container } = render(<WorkPoolQueueStatusBadge status="paused" />);

		// Check for PauseCircle icon
		expect(screen.getByText("Paused")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for not_ready status", () => {
		const { container } = render(
			<WorkPoolQueueStatusBadge status="not_ready" />,
		);

		// Check for AlertCircle icon
		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		expect(container.querySelector("svg")).toBeInTheDocument();
	});
});
