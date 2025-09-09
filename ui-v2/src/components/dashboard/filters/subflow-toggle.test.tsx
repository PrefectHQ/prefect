import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import { SubflowToggle } from "./subflow-toggle";

describe("SubflowToggle", () => {
	test("renders with correct label", () => {
		const onChange = vi.fn();

		render(<SubflowToggle onChange={onChange} />);

		expect(screen.getByText("Hide subflows")).toBeInTheDocument();
		expect(screen.getByLabelText("Hide subflows")).toBeInTheDocument();
	});

	test("renders unchecked by default", () => {
		const onChange = vi.fn();

		render(<SubflowToggle onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).not.toBeChecked();
	});

	test("renders checked when value is true", () => {
		const onChange = vi.fn();

		render(<SubflowToggle value={true} onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).toBeChecked();
	});

	test("renders unchecked when value is false", () => {
		const onChange = vi.fn();

		render(<SubflowToggle value={false} onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).not.toBeChecked();
	});

	test("calls onChange with true when clicked and unchecked", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<SubflowToggle value={false} onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		await user.click(checkbox);

		expect(onChange).toHaveBeenCalledWith(true);
	});

	test("calls onChange with false when clicked and checked", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<SubflowToggle value={true} onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		await user.click(checkbox);

		expect(onChange).toHaveBeenCalledWith(false);
	});

	test("can be clicked via label", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<SubflowToggle value={false} onChange={onChange} />);

		const label = screen.getByText("Hide subflows");
		await user.click(label);

		expect(onChange).toHaveBeenCalledWith(true);
	});

	test("is disabled when disabled prop is true", () => {
		const onChange = vi.fn();

		render(<SubflowToggle value={false} onChange={onChange} disabled={true} />);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).toBeDisabled();
	});

	test("is not disabled when disabled prop is false", () => {
		const onChange = vi.fn();

		render(
			<SubflowToggle value={false} onChange={onChange} disabled={false} />,
		);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).not.toBeDisabled();
	});

	test("applies custom className", () => {
		const onChange = vi.fn();

		const { container } = render(
			<SubflowToggle onChange={onChange} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});

	test("checkbox has correct id attribute", () => {
		const onChange = vi.fn();

		render(<SubflowToggle onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");
		expect(checkbox).toHaveAttribute("id", "hide-subflows");
	});

	test("label has correct htmlFor attribute", () => {
		const onChange = vi.fn();

		render(<SubflowToggle onChange={onChange} />);

		const label = screen.getByText("Hide subflows");
		expect(label).toHaveAttribute("for", "hide-subflows");
	});

	test("handles indeterminate state correctly", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<SubflowToggle onChange={onChange} />);

		const checkbox = screen.getByRole("checkbox");

		// Check that clicking from default state (false) calls onChange with true
		await user.click(checkbox);
		expect(onChange).toHaveBeenCalledWith(true);

		// Reset the mock
		onChange.mockClear();

		// Re-render with value=true
		render(<SubflowToggle value={true} onChange={onChange} />);

		const checkedBox = screen.getByRole("checkbox");
		await user.click(checkedBox);
		expect(onChange).toHaveBeenCalledWith(false);
	});
});
