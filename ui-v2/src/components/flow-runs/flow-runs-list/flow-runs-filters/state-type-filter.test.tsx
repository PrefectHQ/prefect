import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { StateType } from "@/api/flow-runs/constants";
import { StateTypeFilter } from "./state-type-filter";

function TestStateTypeFilter({
	initialTypes = [],
	onChange = () => {},
}: {
	initialTypes?: StateType[];
	onChange?: (types: Set<StateType>) => void;
}) {
	const [types, setTypes] = useState(new Set(initialTypes));
	return (
		<StateTypeFilter
			selectedFilters={types}
			onSelectFilter={(next) => {
				setTypes(next);
				onChange(next);
			}}
		/>
	);
}

describe("StateTypeFilter", () => {
	beforeAll(mockPointerEvents);

	it("adds and removes types while preserving the other selections", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();
		render(
			<TestStateTypeFilter initialTypes={["FAILED"]} onChange={onChange} />,
		);
		const trigger = screen.getByRole("button", { name: "State types" });
		expect(trigger).toHaveTextContent("Failed");
		await user.click(trigger);
		await user.click(screen.getByRole("menuitem", { name: "Running" }));
		expect(onChange).toHaveBeenLastCalledWith(new Set(["FAILED", "RUNNING"]));
		expect(trigger).toHaveTextContent("Failed, Running");
		await user.click(screen.getByRole("menuitem", { name: "Failed" }));
		expect(onChange).toHaveBeenLastCalledWith(new Set(["RUNNING"]));
		expect(
			within(screen.getByRole("menuitem", { name: "Failed" })).getByRole(
				"checkbox",
			),
		).not.toBeChecked();
		expect(
			within(screen.getByRole("menuitem", { name: "Running" })).getByRole(
				"checkbox",
			),
		).toBeChecked();
		await user.keyboard("{Escape}");
		expect(trigger).toHaveTextContent("Running");
	});

	it("clears all selected types", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();
		render(
			<TestStateTypeFilter
				initialTypes={["FAILED", "SCHEDULED"]}
				onChange={onChange}
			/>,
		);
		const trigger = screen.getByRole("button", { name: "State types" });
		await user.click(trigger);
		await user.click(screen.getByRole("menuitem", { name: "All state types" }));
		expect(onChange).toHaveBeenLastCalledWith(new Set());
		expect(screen.getAllByRole("checkbox")).toSatisfy((boxes: HTMLElement[]) =>
			boxes.every((box) => box.getAttribute("aria-checked") === "false"),
		);
		await user.keyboard("{Escape}");
		expect(trigger).toHaveTextContent("All state types");
	});

	it("replaces the selection with every type except scheduled", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();
		render(
			<TestStateTypeFilter initialTypes={["SCHEDULED"]} onChange={onChange} />,
		);
		const trigger = screen.getByRole("button", { name: "State types" });
		await user.click(trigger);
		await user.click(
			screen.getByRole("menuitem", { name: "All except scheduled" }),
		);
		expect(onChange).toHaveBeenLastCalledWith(
			new Set<StateType>([
				"COMPLETED",
				"RUNNING",
				"PENDING",
				"FAILED",
				"CANCELLED",
				"CANCELLING",
				"CRASHED",
				"PAUSED",
			]),
		);
		expect(
			within(screen.getByRole("menuitem", { name: "Completed" })).getByRole(
				"checkbox",
			),
		).toBeChecked();
		expect(
			within(screen.getByRole("menuitem", { name: "Scheduled" })).getByRole(
				"checkbox",
			),
		).not.toBeChecked();
		await user.keyboard("{Escape}");
		expect(trigger).toHaveTextContent("All except scheduled");
	});
});
