import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { DurationInput } from "./duration-input";

describe("DurationInput", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders with initial value in seconds", () => {
		render(<DurationInput value={30} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(30);
		expect(screen.getByRole("combobox")).toHaveTextContent("Seconds");
	});

	it("renders with initial value in minutes", () => {
		render(<DurationInput value={120} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(2);
		expect(screen.getByRole("combobox")).toHaveTextContent("Minutes");
	});

	it("renders with initial value in hours", () => {
		render(<DurationInput value={7200} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(2);
		expect(screen.getByRole("combobox")).toHaveTextContent("Hours");
	});

	it("renders with initial value in days", () => {
		render(<DurationInput value={172800} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(2);
		expect(screen.getByRole("combobox")).toHaveTextContent("Days");
	});

	it("calls onChange with correct value when quantity changes", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<DurationInput value={60} onChange={onChange} />);

		const input = screen.getByRole("spinbutton");
		await user.click(input);
		await user.keyboard("{Control>}a{/Control}5");

		expect(onChange).toHaveBeenLastCalledWith(300);
	});

	it("calls onChange with correct value when unit changes", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<DurationInput value={60} onChange={onChange} />);

		await user.click(screen.getByRole("combobox"));
		await user.click(screen.getByRole("option", { name: "Hours" }));

		expect(onChange).toHaveBeenCalledWith(3600);
	});

	it("filters available units based on min prop", async () => {
		const user = userEvent.setup();

		render(<DurationInput value={3600} onChange={vi.fn()} min={60} />);

		await user.click(screen.getByRole("combobox"));

		expect(
			screen.queryByRole("option", { name: "Seconds" }),
		).not.toBeInTheDocument();
		expect(screen.getByRole("option", { name: "Minutes" })).toBeVisible();
		expect(screen.getByRole("option", { name: "Hours" })).toBeVisible();
		expect(screen.getByRole("option", { name: "Days" })).toBeVisible();
	});

	it("renders as disabled when disabled prop is true", () => {
		render(<DurationInput value={60} onChange={vi.fn()} disabled />);

		expect(screen.getByRole("spinbutton")).toBeDisabled();
		expect(screen.getByRole("combobox")).toBeDisabled();
	});

	it("uses provided id for the input", () => {
		render(<DurationInput value={60} onChange={vi.fn()} id="test-id" />);

		expect(screen.getByRole("spinbutton")).toHaveAttribute("id", "test-id");
	});

	it("defaults to seconds for values that don't divide evenly", () => {
		render(<DurationInput value={45} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(45);
		expect(screen.getByRole("combobox")).toHaveTextContent("Seconds");
	});

	it("defaults to seconds for zero value", () => {
		render(<DurationInput value={0} onChange={vi.fn()} />);

		expect(screen.getByRole("spinbutton")).toHaveValue(0);
		expect(screen.getByRole("combobox")).toHaveTextContent("Seconds");
	});
});
