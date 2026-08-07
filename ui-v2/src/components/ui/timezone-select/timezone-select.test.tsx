import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { expect, test, vi } from "vitest";

// The platform reports ~450 timezones, and rendering all of them makes opening
// the combobox and typing in it slow enough to time out in CI. Exercise the
// component against a small, deterministic list instead.
const SUPPORTED_TIMEZONES = [
	"Africa/Abidjan",
	"America/Chicago",
	"America/New_York",
	"Asia/Kolkata",
	"Asia/Tokyo",
	"Australia/Sydney",
	"Europe/London",
	"Europe/Paris",
	"Pacific/Auckland",
	"Asia/Singapore",
];

vi.spyOn(Intl, "supportedValuesOf").mockImplementation((key) =>
	key === "timeZone" ? SUPPORTED_TIMEZONES : [],
);

const { TimezoneSelect } = await import("./timezone-select");

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

test("TimezoneSelect can select a timezone late in the list", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnSelectFn = vi.fn();

	render(<TimezoneSelect onSelect={mockOnSelectFn} selectedValue="" />);

	await user.click(screen.getByLabelText(/select timezone/i));
	await user.type(screen.getByPlaceholderText(/search/i), "Singapore");
	await user.click(screen.getByRole("option", { name: /asia \/ singapore/i }));

	expect(mockOnSelectFn).toBeCalledWith("Asia/Singapore");
});

test("TimezoneSelect displays a selected timezone that is not in the list", () => {
	mockPointerEvents();

	render(<TimezoneSelect onSelect={vi.fn()} selectedValue="US/Pacific" />);

	expect(screen.getByLabelText(/select timezone/i)).toHaveTextContent(
		"US / Pacific",
	);
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
