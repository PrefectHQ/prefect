import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunStateTabs } from "./flow-runs-state-tabs";

describe("FlowRunStateTabs", () => {
	it("renders all state tabs with correct labels", () => {
		const flowRuns = [createFakeFlowRun()];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /Failed/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /Running/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /Completed/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /Scheduled/i })).toBeInTheDocument();
		expect(screen.getByRole("tab", { name: /Cancelled/i })).toBeInTheDocument();
	});

	it("displays correct count for ALL state", () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
		];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		const allTab = screen.getByRole("tab", { name: /All/i });
		expect(allTab).toHaveTextContent("3");
	});

	it("displays correct counts for each state type", () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "SCHEDULED" }),
			createFakeFlowRun({ state_type: "CANCELLED" }),
		];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("6");
		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"2",
		);
		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("1");
		expect(screen.getByRole("tab", { name: /Running/i })).toHaveTextContent(
			"1",
		);
		expect(screen.getByRole("tab", { name: /Scheduled/i })).toHaveTextContent(
			"1",
		);
		expect(screen.getByRole("tab", { name: /Cancelled/i })).toHaveTextContent(
			"1",
		);
	});

	it("displays 0 count for states with no flow runs", () => {
		const flowRuns = [createFakeFlowRun({ state_type: "COMPLETED" })];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("0");
		expect(screen.getByRole("tab", { name: /Running/i })).toHaveTextContent(
			"0",
		);
		expect(screen.getByRole("tab", { name: /Scheduled/i })).toHaveTextContent(
			"0",
		);
		expect(screen.getByRole("tab", { name: /Cancelled/i })).toHaveTextContent(
			"0",
		);
	});

	it("handles empty flowRuns array", () => {
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={[]}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("0");
		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("0");
		expect(screen.getByRole("tab", { name: /Running/i })).toHaveTextContent(
			"0",
		);
		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"0",
		);
		expect(screen.getByRole("tab", { name: /Scheduled/i })).toHaveTextContent(
			"0",
		);
		expect(screen.getByRole("tab", { name: /Cancelled/i })).toHaveTextContent(
			"0",
		);
	});

	it("calls onStateChange when clicking a tab", async () => {
		const user = userEvent.setup();
		const flowRuns = [createFakeFlowRun({ state_type: "COMPLETED" })];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		const failedTab = screen.getByRole("tab", { name: /Failed/i });
		await user.click(failedTab);

		expect(onStateChange).toHaveBeenCalledWith("FAILED");
	});

	it("calls onStateChange with correct state type for each tab", async () => {
		const user = userEvent.setup();
		const flowRuns = [createFakeFlowRun()];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="FAILED"
				onStateChange={onStateChange}
			/>,
		);

		await user.click(screen.getByRole("tab", { name: /Running/i }));
		expect(onStateChange).toHaveBeenLastCalledWith("RUNNING");

		await user.click(screen.getByRole("tab", { name: /Completed/i }));
		expect(onStateChange).toHaveBeenLastCalledWith("COMPLETED");

		await user.click(screen.getByRole("tab", { name: /Scheduled/i }));
		expect(onStateChange).toHaveBeenLastCalledWith("SCHEDULED");

		await user.click(screen.getByRole("tab", { name: /Cancelled/i }));
		expect(onStateChange).toHaveBeenLastCalledWith("CANCELLED");

		await user.click(screen.getByRole("tab", { name: /All/i }));
		expect(onStateChange).toHaveBeenLastCalledWith("ALL");
	});

	it("marks the selected tab as active", () => {
		const flowRuns = [createFakeFlowRun({ state_type: "FAILED" })];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="FAILED"
				onStateChange={onStateChange}
			/>,
		);

		const failedTab = screen.getByRole("tab", { name: /Failed/i });
		expect(failedTab).toHaveAttribute("data-state", "active");
	});

	it("marks ALL tab as active when selectedState is ALL", () => {
		const flowRuns = [createFakeFlowRun()];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		const allTab = screen.getByRole("tab", { name: /All/i });
		expect(allTab).toHaveAttribute("data-state", "active");
	});

	it("updates counts when flowRuns prop changes", () => {
		const flowRuns = [createFakeFlowRun({ state_type: "COMPLETED" })];
		const onStateChange = vi.fn();

		const { rerender } = render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"1",
		);

		const newFlowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
		];

		rerender(
			<FlowRunStateTabs
				flowRuns={newFlowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("3");
		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"2",
		);
		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("1");
	});

	it("handles flow runs with null state_type", () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: null }),
		];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("2");
		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"1",
		);
	});

	it("renders pill indicators for each state tab", () => {
		const flowRuns = [createFakeFlowRun()];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		// Each state tab should be accessible with aria-label
		expect(screen.getByRole("tab", { name: /all runs/i })).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /failed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /running runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /completed runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /scheduled runs/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("tab", { name: /cancelled runs/i }),
		).toBeInTheDocument();
	});

	it("handles multiple flow runs with the same state type", () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
		];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("5");
		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("5");
		expect(screen.getByRole("tab", { name: /Running/i })).toHaveTextContent(
			"0",
		);
	});

	it("handles all possible state types", () => {
		const flowRuns = [
			createFakeFlowRun({ state_type: "COMPLETED" }),
			createFakeFlowRun({ state_type: "FAILED" }),
			createFakeFlowRun({ state_type: "RUNNING" }),
			createFakeFlowRun({ state_type: "SCHEDULED" }),
			createFakeFlowRun({ state_type: "CANCELLED" }),
			createFakeFlowRun({ state_type: "PENDING" }),
			createFakeFlowRun({ state_type: "CRASHED" }),
			createFakeFlowRun({ state_type: "PAUSED" }),
			createFakeFlowRun({ state_type: "CANCELLING" }),
		];
		const onStateChange = vi.fn();

		render(
			<FlowRunStateTabs
				flowRuns={flowRuns}
				selectedState="ALL"
				onStateChange={onStateChange}
			/>,
		);

		// Should show all 9 flow runs in the ALL tab
		expect(screen.getByRole("tab", { name: /All/i })).toHaveTextContent("9");
		// The 5 visible tabs should show their respective counts
		expect(screen.getByRole("tab", { name: /Completed/i })).toHaveTextContent(
			"1",
		);
		expect(screen.getByRole("tab", { name: /Failed/i })).toHaveTextContent("1");
		expect(screen.getByRole("tab", { name: /Running/i })).toHaveTextContent(
			"1",
		);
		expect(screen.getByRole("tab", { name: /Scheduled/i })).toHaveTextContent(
			"1",
		);
		expect(screen.getByRole("tab", { name: /Cancelled/i })).toHaveTextContent(
			"1",
		);
	});
});
