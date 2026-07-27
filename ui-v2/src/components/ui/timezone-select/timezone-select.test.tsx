import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { expect, test, vi } from "vitest";

import { TimezoneSelect } from "./timezone-select";

test("TimezoneSelect can select an option", async () => {
	mockPointerEvents();
	const user = userEvent.setup();

	// ------------ Setup
	const mockOnSelectFn = vi.fn();

	render(<TimezoneSelect onSelect={mockOnSelectFn} selectedValue="" />);

	// ------------ Act
	await user.click(screen.getByLabelText(/select timezone/i));

	expect(screen.getByText(/suggested timezones/i)).toBeVisible();
	expect(screen.getByText(/all timezones/i)).toBeVisible();

	await user.click(screen.getByRole("option", { name: /africa \/ abidjan/i }));

	// ------------ Assert
	expect(mockOnSelectFn).toBeCalledWith("Africa/Abidjan");
});

test("TimezoneSelect displays UTC when selectedValue is UTC", () => {
	mockPointerEvents();

	render(<TimezoneSelect onSelect={vi.fn()} selectedValue="UTC" />);

	expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent("UTC");
});

test("TimezoneSelect displays UTC when selectedValue is Etc/UTC", () => {
	mockPointerEvents();

	render(<TimezoneSelect onSelect={vi.fn()} selectedValue="Etc/UTC" />);

	expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent("UTC");
});

test("TimezoneSelect selects the canonical UTC option", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnSelectFn = vi.fn();

	render(<TimezoneSelect onSelect={mockOnSelectFn} selectedValue="" />);

	await user.click(screen.getByLabelText(/select timezone/i));
	await user.click(screen.getByRole("option", { name: /^utc$/i }));

	expect(mockOnSelectFn).toBeCalledWith("UTC");
});
