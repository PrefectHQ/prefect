import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FlowRunStateTabs, type StateTypeCounts } from "./flow-runs-state-tabs";

const createStateCounts = (
	overrides: Partial<StateTypeCounts> = {},
): StateTypeCounts => ({
	FAILED: 0,
	CRASHED: 0,
	RUNNING: 0,
	PENDING: 0,
	CANCELLING: 0,
	COMPLETED: 0,
	SCHEDULED: 0,
	PAUSED: 0,
	CANCELLED: 0,
	...overrides,
});

describe("FlowRunStateTabs", () => {
	it("renders all state tabs with correct labels", () => {
		const stateCounts = createStateCounts();
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toBeInTheDocument();
	});

	it("displays correct counts for each state type", () => {
		// Note: The component now receives pre-computed counts per state group
		// FAILED count includes both FAILED and CRASHED (grouped together)
		const stateCounts = createStateCounts({
			FAILED: 1, // This represents the FAILED+CRASHED group count
			RUNNING: 1, // This represents the RUNNING+PENDING+CANCELLING group count
			COMPLETED: 2,
			SCHEDULED: 1, // This represents the SCHEDULED+PAUSED group count
			CANCELLED: 1,
		});
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toHaveTextContent("2");
		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("1");
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toHaveTextContent("1");
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toHaveTextContent("1");
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toHaveTextContent("1");
	});

	it("displays 0 count for states with no flow runs", () => {
		const stateCounts = createStateCounts({
			COMPLETED: 1,
		});
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toHaveTextContent("0");
	});

	it("handles all zero counts", () => {
		const stateCounts = createStateCounts();
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toHaveTextContent("0");
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toHaveTextContent("0");
	});

	it("calls onStateChange when clicking a tab", async () => {
		const user = userEvent.setup();
		const stateCounts = createStateCounts({ COMPLETED: 1 });
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		const completedTab = screen.getByRole("tab", { name: /completed runs/i });
		await user.click(completedTab);

		expect(onStateChange).toHaveBeenCalledWith(["COMPLETED"]);
	});

	it("calls onStateChange with correct state types for each tab", async () => {
		const user = userEvent.setup();
		const stateCounts = createStateCounts();
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		await user.click(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		);
		expect(onStateChange).toHaveBeenLastCalledWith([
			"RUNNING",
			"PENDING",
			"CANCELLING",
		]);

		await user.click(screen.getByRole("tab", { name: /completed runs/i }));
		expect(onStateChange).toHaveBeenLastCalledWith(["COMPLETED"]);

		await user.click(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		);
		expect(onStateChange).toHaveBeenLastCalledWith(["SCHEDULED", "PAUSED"]);

		await user.click(screen.getByRole("tab", { name: /cancelled runs/i }));
		expect(onStateChange).toHaveBeenLastCalledWith(["CANCELLED"]);
	});

	it("marks the selected tab as active", () => {
		const stateCounts = createStateCounts({ FAILED: 1 });
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		const failedTab = screen.getByRole("tab", {
			name: /failed-crashed runs/i,
		});
		expect(failedTab).toHaveAttribute("data-state", "active");
	});

	it("updates counts when stateCounts prop changes", () => {
		const stateCounts = createStateCounts({ COMPLETED: 1 });
		const onStateChange = vi.fn();

		const { rerender } = render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toHaveTextContent("1");

		const newStateCounts = createStateCounts({
			COMPLETED: 2,
			FAILED: 1,
		});

		rerender(
			<FlowRunStateTabs
				stateCounts={newStateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toHaveTextContent("2");
		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("1");
	});

	it("renders pill indicators for each state tab", () => {
		const stateCounts = createStateCounts();
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toBeInTheDocument();
	});

	it("handles high counts correctly", () => {
		const stateCounts = createStateCounts({
			FAILED: 5,
		});
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("5");
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toHaveTextContent("0");
	});

	it("handles counts for all state groups", () => {
		// Note: The component receives pre-computed counts per state group
		// The first state in each group holds the group's total count
		const stateCounts = createStateCounts({
			COMPLETED: 1,
			FAILED: 2, // FAILED+CRASHED group
			RUNNING: 3, // RUNNING+PENDING+CANCELLING group
			SCHEDULED: 2, // SCHEDULED+PAUSED group
			CANCELLED: 1,
		});
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				stateCounts={stateCounts}
				selectedStates={["FAILED", "CRASHED"]}
				onStateChange={onStateChange}
			/>,
		);

		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toHaveTextContent("1");
		expect(
			screen.getByRole("tab", { name: /failed-crashed runs/i }),
		).toHaveTextContent("2");
		expect(
			screen.getByRole("tab", { name: /running-pending-cancelling runs/i }),
		).toHaveTextContent("3");
		expect(
			screen.getByRole("tab", { name: /scheduled-paused runs/i }),
		).toHaveTextContent("2");
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toHaveTextContent("1");
	});
});
