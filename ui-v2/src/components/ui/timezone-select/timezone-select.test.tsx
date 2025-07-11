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
