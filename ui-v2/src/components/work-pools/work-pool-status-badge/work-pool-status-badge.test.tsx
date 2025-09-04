import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkPoolStatusBadge } from "./work-pool-status-badge";

describe("WorkPoolStatusBadge", () => {
	it("renders ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		expect(screen.getByText("Ready")).toBeInTheDocument();
		// Badge should have secondary variant (grey) classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders paused status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="paused" />);

		expect(screen.getByText("Paused")).toBeInTheDocument();
		// Badge should have secondary variant classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders not_ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="not_ready" />);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		// Badge should have secondary variant (grey) classes
		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("includes status circle without tooltip", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		// Should have a colored circle but no tooltip trigger button
		const circle = document.querySelector(".h-2.w-2.rounded-full");
		expect(circle).toBeInTheDocument();
		expect(screen.queryByRole("button")).not.toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(<WorkPoolStatusBadge status="ready" className="custom-class" />);

		const badge = document.querySelector("[data-slot='badge']");
		expect(badge).toHaveClass("custom-class");
	});

	it("displays circle with correct color", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		const circle = document.querySelector(".h-2.w-2.rounded-full");
		expect(circle).toHaveClass("bg-green-500");
	});
});
