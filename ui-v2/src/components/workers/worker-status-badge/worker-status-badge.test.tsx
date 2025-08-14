import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkerStatusBadge } from "./worker-status-badge";

describe("WorkerStatusBadge", () => {
	it("displays online status correctly", () => {
		render(<WorkerStatusBadge status="ONLINE" />);

		expect(screen.getByText("Online")).toBeInTheDocument();
		expect(screen.getByRole("generic")).toHaveClass("bg-green-100");
	});

	it("displays offline status correctly", () => {
		render(<WorkerStatusBadge status="OFFLINE" />);

		expect(screen.getByText("Offline")).toBeInTheDocument();
		expect(screen.getByRole("generic")).toHaveClass("bg-gray-100");
	});

	it("applies custom className", () => {
		render(<WorkerStatusBadge status="ONLINE" className="custom-class" />);

		expect(screen.getByRole("generic")).toHaveClass("custom-class");
	});
});
