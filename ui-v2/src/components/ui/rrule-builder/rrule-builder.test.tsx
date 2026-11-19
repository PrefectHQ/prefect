import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RRuleBuilder } from "./rrule-builder";

const initial = "DTSTART;TZID=UTC:20260301T093000\nRRULE:FREQ=DAILY";
function Controlled() {
	const [value, setValue] = useState(initial);
	return (
		<>
			<RRuleBuilder value={value} onChange={setValue} />
			<output>{value}</output>
		</>
	);
}

describe("rrule-builder", () => {
	beforeEach(() => {
		Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
			configurable: true,
			value: vi.fn(),
		});
	});
	afterEach(() => {
		Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
	});
	it("switches to weekly and toggles weekday chips", async () => {
		const user = userEvent.setup();
		render(<Controlled />);
		fireEvent.keyDown(screen.getByRole("combobox", { name: "Frequency" }), {
			key: "Enter",
		});
		await user.click(screen.getByRole("option", { name: "Weekly" }));
		await user.click(screen.getByRole("button", { name: "Monday" }));
		expect(screen.getByRole("status")).toHaveTextContent("BYDAY=MO,SU");
		await user.click(screen.getByRole("button", { name: "Sunday" }));
		expect(screen.getByRole("status")).toHaveTextContent(
			"BYDAY=MO;BYHOUR=9;BYMINUTE=30;BYSECOND=0",
		);
	});
	it("edits end conditions", async () => {
		const user = userEvent.setup();
		render(<Controlled />);
		fireEvent.keyDown(screen.getByRole("combobox", { name: "Ends" }), {
			key: "Enter",
		});
		await user.click(screen.getByRole("option", { name: "After occurrences" }));
		fireEvent.change(screen.getByLabelText("Occurrences"), {
			target: { value: "5" },
		});
		expect(screen.getByRole("status")).toHaveTextContent("COUNT=5");
		fireEvent.keyDown(screen.getByRole("combobox", { name: "Ends" }), {
			key: "Enter",
		});
		await user.click(screen.getByRole("option", { name: "On date" }));
		fireEvent.change(screen.getByLabelText("End date"), {
			target: { value: "2026-12-31" },
		});
		expect(screen.getByRole("status")).toHaveTextContent(
			"UNTIL=20261231T235959Z",
		);
		fireEvent.keyDown(screen.getByRole("combobox", { name: "Ends" }), {
			key: "Enter",
		});
		await user.click(screen.getByRole("option", { name: "Never" }));
		expect(screen.getByRole("status")).not.toHaveTextContent("UNTIL=");
		expect(screen.getByRole("status")).not.toHaveTextContent("COUNT=");
	});
	it("edits the local start and time together with the recurrence time", () => {
		render(<Controlled />);
		fireEvent.change(screen.getByLabelText("Start date"), {
			target: { value: "2026-04-02" },
		});
		fireEvent.change(screen.getByLabelText("Time (UTC)"), {
			target: { value: "16:45" },
		});
		expect(screen.getByRole("status")).toHaveTextContent(
			"DTSTART;TZID=UTC:20260402T164500",
		);
		expect(screen.getByRole("status")).toHaveTextContent(
			"BYHOUR=16;BYMINUTE=45;BYSECOND=0",
		);
	});
	it("keeps empty rules empty until edited", () => {
		const onChange = vi.fn();
		render(<RRuleBuilder value="" onChange={onChange} />);
		expect(screen.getByText("No recurrence rule")).toBeVisible();
		expect(onChange).not.toHaveBeenCalled();
	});
	it("preserves unsupported rules until raw editing is requested", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(<RRuleBuilder value="RRULE:FREQ=HOURLY" onChange={onChange} />);
		expect(screen.getByText("every hour")).toBeVisible();
		expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
		expect(onChange).not.toHaveBeenCalled();
		await user.click(screen.getByRole("button", { name: "Edit raw rule" }));
		fireEvent.change(screen.getByLabelText("Raw recurrence rule"), {
			target: { value: "RRULE:FREQ=MINUTELY" },
		});
		expect(onChange).toHaveBeenCalledWith("RRULE:FREQ=MINUTELY");
	});
	it("offers raw editing for supported rules and a return to the builder", async () => {
		const user = userEvent.setup();
		render(<Controlled />);
		await user.click(screen.getByRole("button", { name: "Edit raw rule" }));
		expect(screen.getByLabelText("Raw recurrence rule")).toHaveValue(initial);
		await user.click(screen.getByRole("button", { name: "Use builder" }));
		expect(screen.getByRole("combobox", { name: "Frequency" })).toBeVisible();
	});
	it("shows invalid input without emitting it", () => {
		const onChange = vi.fn();
		render(<RRuleBuilder value={initial} onChange={onChange} />);
		fireEvent.change(screen.getByLabelText("Repeat every"), {
			target: { value: "0" },
		});
		expect(screen.getByRole("alert")).toBeVisible();
		expect(onChange).not.toHaveBeenCalled();
	});
	it("renders empty and invalid rules without losing their raw text", () => {
		render(<RRuleBuilder value="not a rule" onChange={vi.fn()} />);
		expect(screen.getAllByText("not a rule").length).toBeGreaterThan(0);
	});
});
