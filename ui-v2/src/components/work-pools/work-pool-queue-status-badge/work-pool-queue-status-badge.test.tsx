import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkPoolQueueStatus } from "@/api/work-pool-queues";
import { WorkPoolQueueStatusBadge } from "./work-pool-queue-status-badge";

describe("WorkPoolQueueStatusBadge", () => {
	const testCases: Array<{
		status: WorkPoolQueueStatus;
		expectedLabel: string;
		expectedVariant: string;
	}> = [
		{
			status: "ready",
			expectedLabel: "Ready",
			expectedVariant: "success",
		},
		{
			status: "paused",
			expectedLabel: "Paused",
			expectedVariant: "warning",
		},
		{
			status: "not_ready",
			expectedLabel: "Not Ready",
			expectedVariant: "destructive",
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
		render(<WorkPoolQueueStatusBadge status="ready" />);

		// Check for CheckCircle icon
		expect(screen.getByText("Ready")).toBeInTheDocument();
		const badge = screen.getByText("Ready").closest("span");
		expect(badge?.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for paused status", () => {
		render(<WorkPoolQueueStatusBadge status="paused" />);

		// Check for PauseCircle icon
		expect(screen.getByText("Paused")).toBeInTheDocument();
		const badge = screen.getByText("Paused").closest("span");
		expect(badge?.querySelector("svg")).toBeInTheDocument();
	});

	it("renders with correct icon for not_ready status", () => {
		render(<WorkPoolQueueStatusBadge status="not_ready" />);

		// Check for AlertCircle icon
		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		const badge = screen.getByText("Not Ready").closest("span");
		expect(badge?.querySelector("svg")).toBeInTheDocument();
	});
});
