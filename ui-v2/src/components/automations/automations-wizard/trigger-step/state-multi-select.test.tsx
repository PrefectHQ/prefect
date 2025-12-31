import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
	STATE_NAME_TO_TYPE,
	STATE_NAMES,
	STATE_NAMES_WITHOUT_SCHEDULED,
} from "@/api/flow-runs/constants";
import { StateMultiSelect } from "./state-multi-select";

describe("StateMultiSelect", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	it("renders with empty message when no states are selected", () => {
		render(
			<StateMultiSelect
				selectedStates={[]}
				onStateChange={vi.fn()}
				emptyMessage="Any state"
			/>,
		);

		expect(screen.getByText("Any state")).toBeVisible();
	});

	it("displays all 18 state options in the dropdown", async () => {
		const user = userEvent.setup();

		render(<StateMultiSelect selectedStates={[]} onStateChange={vi.fn()} />);

		await user.click(screen.getByRole("button"));

		for (const stateName of STATE_NAMES) {
			expect(screen.getByRole("option", { name: stateName })).toBeVisible();
		}
	});

	it("displays convenience options in the dropdown", async () => {
		const user = userEvent.setup();

		render(<StateMultiSelect selectedStates={[]} onStateChange={vi.fn()} />);

		await user.click(screen.getByRole("button"));

		expect(
			screen.getByRole("option", { name: "All run states" }),
		).toBeVisible();
		expect(
			screen.getByRole("option", { name: "All except scheduled" }),
		).toBeVisible();
	});

	it("calls onStateChange with empty array when 'All run states' is selected", async () => {
		const user = userEvent.setup();
		const onStateChange = vi.fn();

		render(
			<StateMultiSelect
				selectedStates={["Completed", "Failed"]}
				onStateChange={onStateChange}
			/>,
		);

		await user.click(screen.getByRole("button"));
		await user.click(screen.getByRole("option", { name: "All run states" }));

		expect(onStateChange).toHaveBeenCalledWith([]);
	});

	it("calls onStateChange with all states except Scheduled when 'All except scheduled' is selected", async () => {
		const user = userEvent.setup();
		const onStateChange = vi.fn();

		render(
			<StateMultiSelect selectedStates={[]} onStateChange={onStateChange} />,
		);

		await user.click(screen.getByRole("button"));
		await user.click(
			screen.getByRole("option", { name: "All except scheduled" }),
		);

		expect(onStateChange).toHaveBeenCalledWith([
			...STATE_NAMES_WITHOUT_SCHEDULED,
		]);
	});

	it("displays 'All except scheduled' when all states except Scheduled are selected", () => {
		render(
			<StateMultiSelect
				selectedStates={[...STATE_NAMES_WITHOUT_SCHEDULED]}
				onStateChange={vi.fn()}
			/>,
		);

		expect(screen.getByText("All except scheduled")).toBeVisible();
	});

	it("can select individual states", async () => {
		const user = userEvent.setup();
		const onStateChange = vi.fn();

		render(
			<StateMultiSelect selectedStates={[]} onStateChange={onStateChange} />,
		);

		await user.click(screen.getByRole("button"));
		await user.click(screen.getByRole("option", { name: "Completed" }));

		expect(onStateChange).toHaveBeenCalledWith(["Completed"]);
	});

	it("can deselect individual states", async () => {
		const user = userEvent.setup();
		const onStateChange = vi.fn();

		render(
			<StateMultiSelect
				selectedStates={["Completed", "Failed"]}
				onStateChange={onStateChange}
			/>,
		);

		await user.click(screen.getByRole("button"));
		await user.click(screen.getByRole("option", { name: "Completed" }));

		expect(onStateChange).toHaveBeenCalledWith(["Failed"]);
	});

	it("displays selected states as badges with correct state types", () => {
		render(
			<StateMultiSelect
				selectedStates={["Completed", "Failed", "Running"]}
				onStateChange={vi.fn()}
			/>,
		);

		expect(screen.getByText("Completed")).toBeVisible();
		expect(screen.getByText("Failed")).toBeVisible();
		expect(screen.getByText("Running")).toBeVisible();
	});

	it("filters states based on search input", async () => {
		const user = userEvent.setup();

		render(<StateMultiSelect selectedStates={[]} onStateChange={vi.fn()} />);

		await user.click(screen.getByRole("button"));
		await user.type(screen.getByPlaceholderText("Search states..."), "comp");

		expect(screen.getByRole("option", { name: "Completed" })).toBeVisible();
		expect(
			screen.queryByRole("option", { name: "Failed" }),
		).not.toBeInTheDocument();
	});

	it("shows convenience options when search matches them", async () => {
		const user = userEvent.setup();

		render(<StateMultiSelect selectedStates={[]} onStateChange={vi.fn()} />);

		await user.click(screen.getByRole("button"));
		await user.type(screen.getByPlaceholderText("Search states..."), "all");

		expect(
			screen.getByRole("option", { name: "All run states" }),
		).toBeVisible();
		expect(
			screen.getByRole("option", { name: "All except scheduled" }),
		).toBeVisible();
	});

	it("maps state names to correct state types for badges", () => {
		const stateNamesToTest = [
			"Late",
			"AwaitingRetry",
			"Suspended",
			"Retrying",
			"Cached",
			"TimedOut",
		] as const;

		render(
			<StateMultiSelect
				selectedStates={[...stateNamesToTest]}
				onStateChange={vi.fn()}
			/>,
		);

		for (const stateName of stateNamesToTest) {
			expect(screen.getByText(stateName)).toBeVisible();
			const expectedType = STATE_NAME_TO_TYPE[stateName];
			expect(expectedType).toBeDefined();
		}
	});
});
