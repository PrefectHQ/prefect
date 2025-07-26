import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkPoolStatusBadge } from "./work-pool-status-badge";

describe("WorkPoolStatusBadge", () => {
	it("renders ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		expect(screen.getByText("Ready")).toBeInTheDocument();
		// Badge should have default variant (primary) classes
		const badge = screen.getByText("Ready").closest("span");
		expect(badge).toHaveClass("bg-primary", "text-primary-foreground");
	});

	it("renders paused status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="paused" />);

		expect(screen.getByText("Paused")).toBeInTheDocument();
		// Badge should have secondary variant classes
		const badge = screen.getByText("Paused").closest("span");
		expect(badge).toHaveClass("bg-secondary", "text-secondary-foreground");
	});

	it("renders not_ready status with correct label and styling", () => {
		render(<WorkPoolStatusBadge status="not_ready" />);

		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		// Badge should have destructive variant classes
		const badge = screen.getByText("Not Ready").closest("span");
		expect(badge).toHaveClass("bg-destructive", "text-white");
	});

	it("includes status icon without tooltip", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		// Should have an icon but no tooltip trigger button
		const svg = document.querySelector("svg[aria-hidden='true']");
		expect(svg).toBeInTheDocument();
		expect(screen.queryByRole("button")).not.toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(<WorkPoolStatusBadge status="ready" className="custom-class" />);

		const badge = screen.getByText("Ready").closest("span");
		expect(badge).toHaveClass("custom-class");
	});

	it("displays icon with correct size", () => {
		render(<WorkPoolStatusBadge status="ready" />);

		const icon = document.querySelector("svg[aria-hidden='true']");
		expect(icon).toHaveClass("h-3", "w-3");
	});
});
