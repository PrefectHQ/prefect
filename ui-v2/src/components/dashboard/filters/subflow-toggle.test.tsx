import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { SubflowToggle } from "./subflow-toggle";

describe("SubflowToggle", () => {
	const mockOnChange = vi.fn();

	beforeEach(() => {
		mockOnChange.mockClear();
	});

	it("renders with default label", () => {
		render(<SubflowToggle value={false} onChange={mockOnChange} />);

		expect(screen.getByText("Hide subflows")).toBeInTheDocument();
	});

	it("renders with custom label", () => {
		render(
			<SubflowToggle
				value={false}
				onChange={mockOnChange}
				label="Custom label"
			/>,
		);

		expect(screen.getByText("Custom label")).toBeInTheDocument();
	});

	it("displays unchecked state when value is false", () => {
		render(<SubflowToggle value={false} onChange={mockOnChange} />);

		const toggle = screen.getByRole("switch");
		expect(toggle).not.toBeChecked();
	});

	it("displays checked state when value is true", () => {
		render(<SubflowToggle value={true} onChange={mockOnChange} />);

		const toggle = screen.getByRole("switch");
		expect(toggle).toBeChecked();
	});

	it("calls onChange when clicked", async () => {
		const user = userEvent.setup();
		render(<SubflowToggle value={false} onChange={mockOnChange} />);

		const toggle = screen.getByRole("switch");
		await user.click(toggle);

		expect(mockOnChange).toHaveBeenCalledWith(true);
	});

	it("calls onChange with opposite value when clicked", async () => {
		const user = userEvent.setup();
		render(<SubflowToggle value={true} onChange={mockOnChange} />);

		const toggle = screen.getByRole("switch");
		await user.click(toggle);

		expect(mockOnChange).toHaveBeenCalledWith(false);
	});

	it("has correct accessibility attributes", () => {
		render(
			<SubflowToggle
				value={false}
				onChange={mockOnChange}
				label="Hide subflows"
			/>,
		);

		const toggle = screen.getByRole("switch");
		expect(toggle).toHaveAttribute("aria-label", "Hide subflows");
		expect(toggle).toHaveAttribute("id", "hide-subflows");

		const label = screen.getByText("Hide subflows");
		expect(label).toHaveAttribute("for", "hide-subflows");
	});
});
