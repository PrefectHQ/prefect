import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkerStatusBadge } from "./worker-status-badge";

describe("WorkerStatusBadge", () => {
	it("displays online status correctly", () => {
		render(<WorkerStatusBadge status="ONLINE" />);

		expect(screen.getByText("Online")).toBeInTheDocument();
		const badge = screen.getByText("Online").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("bg-secondary");
		// Check for the green circle indicator
		const circle = badge?.querySelector(".bg-green-500");
		expect(circle).toBeInTheDocument();
	});

	it("displays offline status correctly", () => {
		render(<WorkerStatusBadge status="OFFLINE" />);

		expect(screen.getByText("Offline")).toBeInTheDocument();
		const badge = screen.getByText("Offline").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("bg-secondary");
		// Check for the red circle indicator
		const circle = badge?.querySelector(".bg-red-500");
		expect(circle).toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(<WorkerStatusBadge status="ONLINE" className="custom-class" />);

		const badge = screen.getByText("Online").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("custom-class");
	});
});
