import { DetailsStep } from "./details-step";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

describe("DetailsStep", () => {
	it("able to add details about an automation", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSaveFn = vi.fn();
		render(<DetailsStep onPrevious={vi.fn()} onSave={mockOnSaveFn} />);

		// ------------ Act

		await user.type(screen.getByLabelText(/automation name/i), "My Automation");
		await user.type(
			screen.getByLabelText(/description \(optional\)/i),
			"My Description",
		);

		await user.click(screen.getByRole("button", { name: /save/i }));

		// ------------ Assert
		expect(mockOnSaveFn).toBeCalledWith({
			name: "My Automation",
			description: "My Description",
		});
	});
});
