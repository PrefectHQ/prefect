import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { expect, test, vi } from "vitest";

import { StateSelect } from ".";

test("StateSelect renders with placeholder when no value selected", () => {
	mockPointerEvents();
	const mockOnValueChange = vi.fn();

	render(<StateSelect onValueChange={mockOnValueChange} />);

	expect(screen.getByRole("combobox")).toBeVisible();
	expect(screen.getByText("Select state")).toBeVisible();
});

test("StateSelect shows all states when terminalOnly is false", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnValueChange = vi.fn();

	render(<StateSelect onValueChange={mockOnValueChange} />);

	await user.click(screen.getByRole("combobox"));

	expect(screen.getByRole("option", { name: /completed/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /running/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /scheduled/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /pending/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /failed/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /cancelled/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /cancelling/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /crashed/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /paused/i })).toBeVisible();
});

test("StateSelect shows only terminal states when terminalOnly is true", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnValueChange = vi.fn();

	render(<StateSelect onValueChange={mockOnValueChange} terminalOnly />);

	await user.click(screen.getByRole("combobox"));

	expect(screen.getByRole("option", { name: /completed/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /failed/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /cancelled/i })).toBeVisible();
	expect(screen.getByRole("option", { name: /crashed/i })).toBeVisible();

	expect(screen.queryByRole("option", { name: /running/i })).toBeNull();
	expect(screen.queryByRole("option", { name: /scheduled/i })).toBeNull();
	expect(screen.queryByRole("option", { name: /pending/i })).toBeNull();
	expect(screen.queryByRole("option", { name: /cancelling/i })).toBeNull();
	expect(screen.queryByRole("option", { name: /paused/i })).toBeNull();
});

test("StateSelect calls onValueChange when state is selected", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnValueChange = vi.fn();

	render(<StateSelect onValueChange={mockOnValueChange} />);

	await user.click(screen.getByRole("combobox"));
	await user.click(screen.getByRole("option", { name: /completed/i }));

	expect(mockOnValueChange).toHaveBeenCalledWith("COMPLETED");
});

test("StateSelect displays selected value with StateBadge", () => {
	mockPointerEvents();
	const mockOnValueChange = vi.fn();

	render(<StateSelect value="RUNNING" onValueChange={mockOnValueChange} />);

	expect(screen.getByText("Running")).toBeVisible();
});

test("StateSelect excludes specified state when excludeState is provided", async () => {
	mockPointerEvents();
	const user = userEvent.setup();
	const mockOnValueChange = vi.fn();

	render(
		<StateSelect onValueChange={mockOnValueChange} excludeState="RUNNING" />,
	);

	await user.click(screen.getByRole("combobox"));

	expect(screen.queryByRole("option", { name: /^running$/i })).toBeNull();
	expect(screen.getByRole("option", { name: /completed/i })).toBeVisible();
});

test("StateSelect uses custom placeholder when provided", () => {
	mockPointerEvents();
	const mockOnValueChange = vi.fn();

	render(
		<StateSelect
			onValueChange={mockOnValueChange}
			placeholder="Choose a state"
		/>,
	);

	expect(screen.getByText("Choose a state")).toBeVisible();
});
