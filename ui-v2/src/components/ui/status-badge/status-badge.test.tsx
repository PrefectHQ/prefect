import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from ".";

describe("StatusBadge", () => {
	it("renders READY status correctly", () => {
		render(<StatusBadge status="READY" />);
		expect(screen.getByText("Ready")).toBeInTheDocument();
		const badge = screen.getByText("Ready").closest("span");
		expect(badge).toHaveClass("bg-green-100");
	});

	it("renders NOT_READY status correctly", () => {
		render(<StatusBadge status="NOT_READY" />);
		expect(screen.getByText("Not Ready")).toBeInTheDocument();
		const badge = screen.getByText("Not Ready").closest("span");
		expect(badge).toHaveClass("bg-red-100");
	});

	it("renders PAUSED status correctly", () => {
		render(<StatusBadge status="PAUSED" />);
		expect(screen.getByText("Paused")).toBeInTheDocument();
		const badge = screen.getByText("Paused").closest("span");
		expect(badge).toHaveClass("bg-gray-300");
	});
});
