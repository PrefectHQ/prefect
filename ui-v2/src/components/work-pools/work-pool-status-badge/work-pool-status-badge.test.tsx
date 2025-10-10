import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkPoolStatusBadge } from "./work-pool-status-badge";

describe("WorkPoolStatusBadge", () => {
	it("renders ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="READY" />);

		expect(screen.getByText("Ready")).toBeInTheDocument();
		// Badge should have secondary variant (grey) classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders paused status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="PAUSED" />);

		expect(screen.getByText("Paused")).toBeInTheDocument();
		// Badge should have secondary variant classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders not_ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="NOT_READY" />);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		// Badge should have secondary variant (grey) classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("includes status circle without tooltip", () => {
		render(<WorkPoolStatusBadge status="READY" />);

		// Should have a colored circle but no tooltip trigger button
		const circle = document.querySelector(".h-2.w-2.rounded-full");
		expect(circle).toBeInTheDocument();
		expect(screen.queryByRole("button")).not.toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(<WorkPoolStatusBadge status="READY" className="custom-class" />);

		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("custom-class");
	});

	it("displays circle with correct color", () => {
		render(<WorkPoolStatusBadge status="READY" />);

		const circle = document.querySelector(".h-2.w-2.rounded-full");
		expect(circle).toHaveClass("bg-green-500");
	});
});
