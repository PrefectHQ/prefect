import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkerStatusBadge } from "./worker-status-badge";

describe("WorkerStatusBadge", () => {
	it("displays online status correctly", () => {
		render(<WorkerStatusBadge status="ONLINE" />);

		expect(screen.getByText("Online")).toBeInTheDocument();
		const badge = screen.getByText("Online").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("bg-green-100");
	});

	it("displays offline status correctly", () => {
		render(<WorkerStatusBadge status="OFFLINE" />);

		expect(screen.getByText("Offline")).toBeInTheDocument();
		const badge = screen.getByText("Offline").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("bg-gray-100");
	});

	it("applies custom className", () => {
		render(<WorkerStatusBadge status="ONLINE" className="custom-class" />);

		const badge = screen.getByText("Online").closest('[data-slot="badge"]');
		expect(badge).toHaveClass("custom-class");
	});
});
