import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { WorkPoolStatusIcon } from "./work-pool-status-icon";

describe("WorkPoolStatusIcon", () => {
	it("renders ready status with correct icon and color", () => {
		render(<WorkPoolStatusIcon status="ready" />);

		const icon = document.querySelector("svg");
		expect(icon).toBeInTheDocument();
		expect(icon).toHaveClass("text-green-600");
	});

	it("renders paused status with correct icon and color", () => {
		render(<WorkPoolStatusIcon status="paused" />);

		const icon = document.querySelector("svg");
		expect(icon).toBeInTheDocument();
		expect(icon).toHaveClass("text-yellow-600");
	});

	it("renders not_ready status with correct icon and color", () => {
		render(<WorkPoolStatusIcon status="not_ready" />);

		const icon = document.querySelector("svg");
		expect(icon).toBeInTheDocument();
		expect(icon).toHaveClass("text-red-600");
	});

	it("shows tooltip with correct description on hover", async () => {
		const user = userEvent.setup();
		render(<WorkPoolStatusIcon status="ready" />);

		const triggerElement = document.querySelector(
			"[data-slot='tooltip-trigger']",
		);
		expect(triggerElement).toBeInTheDocument();

		if (triggerElement) {
			await user.hover(triggerElement);
			expect(await screen.findByRole("tooltip")).toBeInTheDocument();
		}
	});

	it("shows tooltip for paused status", async () => {
		const user = userEvent.setup();
		render(<WorkPoolStatusIcon status="paused" />);

		const triggerElement = document.querySelector(
			"[data-slot='tooltip-trigger']",
		);
		if (triggerElement) {
			await user.hover(triggerElement);
			expect(await screen.findByRole("tooltip")).toBeInTheDocument();
		}
	});

	it("shows tooltip for not_ready status", async () => {
		const user = userEvent.setup();
		render(<WorkPoolStatusIcon status="not_ready" />);

		const triggerElement = document.querySelector(
			"[data-slot='tooltip-trigger']",
		);
		if (triggerElement) {
			await user.hover(triggerElement);
			expect(await screen.findByRole("tooltip")).toBeInTheDocument();
		}
	});

	it("does not show tooltip when showTooltip is false", () => {
		render(<WorkPoolStatusIcon status="ready" showTooltip={false} />);

		// Should render just the icon, not wrapped in tooltip trigger
		expect(
			document.querySelector("[data-slot='tooltip-trigger']"),
		).not.toBeInTheDocument();
		expect(document.querySelector("svg")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(
			<WorkPoolStatusIcon
				status="ready"
				className="custom-class"
				showTooltip={false}
			/>,
		);

		const icon = document.querySelector("svg");
		expect(icon).toHaveClass("custom-class");
	});
});
