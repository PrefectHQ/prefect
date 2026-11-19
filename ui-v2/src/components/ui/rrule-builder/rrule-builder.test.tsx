import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RRuleBuilder } from "./rrule-builder";

const initial = "DTSTART;TZID=UTC:20260301T093000\nRRULE:FREQ=DAILY";
function Controlled({ initialValue = initial }: { initialValue?: string }) {
	const [value, setValue] = useState(initialValue);
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
		fireEvent.keyDown(
			screen.getByRole("combobox", { name: "Recurrence unit" }),
			{
				key: "Enter",
			},
		);
		await user.click(screen.getByRole("option", { name: "week" }));
		expect(screen.getByRole("button", { name: "Monday" })).toHaveTextContent(
			/^M$/,
		);
		expect(screen.getByRole("button", { name: "Thursday" })).toHaveTextContent(
			/^T$/,
		);
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
		expect(screen.getByLabelText("Occurrences")).toBeDisabled();
		await user.click(screen.getByRole("radio", { name: "After" }));
		fireEvent.change(screen.getByLabelText("Occurrences"), {
			target: { value: "5" },
		});
		expect(screen.getByRole("status")).toHaveTextContent("COUNT=5");
		await user.click(screen.getByRole("radio", { name: "On" }));
		fireEvent.change(screen.getByLabelText("End date"), {
			target: { value: "2026-12-31" },
		});
		expect(screen.getByRole("status")).toHaveTextContent(
			"UNTIL=20261231T235959Z",
		);
		await user.click(screen.getByRole("radio", { name: "Never" }));
		expect(screen.getByLabelText("End date")).toBeDisabled();
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
	it("keeps unsupported rules read-only and collapsed until Show rule is clicked", async () => {
		const onChange = vi.fn();
		const user = userEvent.setup();
		render(<RRuleBuilder value="RRULE:FREQ=HOURLY" onChange={onChange} />);
		expect(screen.getByText("every hour")).toBeVisible();
		expect(
			screen.getByText("This schedule can only be edited in code."),
		).toBeVisible();
		expect(
			screen.getByText(
				"The builder requires one DTSTART and one RRULE, without additional rules or dates.",
			),
		).toBeVisible();
		expect(screen.queryByText("RRULE:FREQ=HOURLY")).not.toBeInTheDocument();
		const toggle = screen.getByRole("button", { name: "Show rule" });
		expect(toggle).toHaveAttribute("aria-expanded", "false");
		await user.click(toggle);
		expect(toggle).toHaveAttribute("aria-expanded", "true");
		expect(screen.getByText("RRULE:FREQ=HOURLY")).toBeVisible();
		await user.click(toggle);
		expect(screen.queryByText("RRULE:FREQ=HOURLY")).not.toBeInTheDocument();
		expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
		expect(onChange).not.toHaveBeenCalled();
	});
	it.each([initial, "RRULE:FREQ=HOURLY"])(
		"has no raw editing controls for %s",
		(value) => {
			render(<RRuleBuilder value={value} onChange={vi.fn()} />);
			expect(
				screen.queryByRole("button", { name: "Edit raw rule" }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("button", { name: "Use builder" }),
			).not.toBeInTheDocument();
			expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
		},
	);
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
	it("pluralizes recurrence units and removes the separate frequency label", () => {
		render(<Controlled />);
		expect(
			screen.getByRole("combobox", { name: "Recurrence unit" }),
		).toHaveTextContent("day");
		fireEvent.change(screen.getByLabelText("Repeat every"), {
			target: { value: "2" },
		});
		expect(
			screen.getByRole("combobox", { name: "Recurrence unit" }),
		).toHaveTextContent("days");
		expect(screen.queryByText("Frequency")).not.toBeInTheDocument();
	});
	it("offers start-derived monthly choices while preserving an existing ordinal", async () => {
		const user = userEvent.setup();
		render(
			<Controlled
				initialValue={
					"DTSTART;TZID=UTC:20261119T090000\nRRULE:FREQ=MONTHLY;BYDAY=FR;BYSETPOS=-1"
				}
			/>,
		);
		const choice = screen.getByRole("combobox", { name: "Monthly recurrence" });
		expect(choice).toHaveTextContent("Monthly on the last Friday");
		fireEvent.keyDown(choice, { key: "Enter" });
		expect(
			screen.getByRole("option", { name: "Monthly on day 19" }),
		).toBeVisible();
		await user.click(
			screen.getByRole("option", { name: "Monthly on the third Thursday" }),
		);
		expect(screen.getByRole("status")).toHaveTextContent("BYDAY=TH;BYSETPOS=3");
		fireEvent.keyDown(
			screen.getByRole("combobox", { name: "Monthly recurrence" }),
			{ key: "Enter" },
		);
		await user.click(screen.getByRole("option", { name: "Monthly on day 19" }));
		expect(screen.getByRole("status")).toHaveTextContent("BYMONTHDAY=19");
	});
	it("shows an annual summary and follows start-date edits for matching rules", () => {
		render(
			<Controlled
				initialValue={
					"DTSTART;TZID=UTC:20261119T090000\nRRULE:FREQ=YEARLY;BYMONTH=11;BYMONTHDAY=19"
				}
			/>,
		);
		expect(screen.getByText("Annually on November 19")).toBeVisible();
		fireEvent.change(screen.getByLabelText("Start date"), {
			target: { value: "2026-12-20" },
		});
		expect(screen.getByText("Annually on December 20")).toBeVisible();
		expect(screen.getByRole("status")).toHaveTextContent(
			"BYMONTH=12;BYMONTHDAY=20",
		);
	});
	it("keeps nonmatching annual month and day editable without changing the rule", () => {
		const onChange = vi.fn();
		render(
			<RRuleBuilder
				value={
					"DTSTART;TZID=UTC:20261119T090000\nRRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29"
				}
				onChange={onChange}
			/>,
		);
		expect(screen.getByLabelText("Month of year")).toHaveValue(2);
		expect(screen.getByLabelText("Day of month")).toHaveValue(29);
		expect(onChange).not.toHaveBeenCalled();
	});
});
