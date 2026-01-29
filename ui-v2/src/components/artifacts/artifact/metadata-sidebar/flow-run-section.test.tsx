import { render, screen } from "@testing-library/react";
import humanizeDuration from "humanize-duration";
import { describe, expect, it } from "vitest";
import { createFakeFlowRun } from "@/mocks";
import { formatDate } from "@/utils/date";
import { FlowRunSection } from "./flow-run-section";

describe("FlowRunSection", () => {
	it("renders flow run section with start time", () => {
		const startTime = "2024-01-15T10:30:00.000Z";
		const flowRun = createFakeFlowRun({ start_time: startTime });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Flow Run")).toBeTruthy();
		expect(screen.getByText("Start time")).toBeTruthy();
		expect(screen.getByText(formatDate(startTime, "dateTime"))).toBeTruthy();
	});

	it("renders flow run section with duration", () => {
		const estimatedRunTime = 125;
		const flowRun = createFakeFlowRun({ estimated_run_time: estimatedRunTime });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Duration")).toBeTruthy();
		expect(
			screen.getByText(humanizeDuration(Math.ceil(estimatedRunTime) * 1000)),
		).toBeTruthy();
	});

	it("renders flow run section with created date", () => {
		const created = "2024-01-15T10:30:00.000Z";
		const flowRun = createFakeFlowRun({ created });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Created")).toBeTruthy();
		expect(screen.getByText(formatDate(created, "dateTime"))).toBeTruthy();
	});

	it("renders flow run section with last updated date", () => {
		const updated = "2024-01-15T11:30:00.000Z";
		const flowRun = createFakeFlowRun({ updated });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Last Updated")).toBeTruthy();
		expect(screen.getByText(formatDate(updated, "dateTime"))).toBeTruthy();
	});

	it("renders flow run section with tags", () => {
		const flowRun = createFakeFlowRun({ tags: ["tag1", "tag2"] });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Tags")).toBeTruthy();
		expect(screen.getByText("tag1")).toBeTruthy();
		expect(screen.getByText("tag2")).toBeTruthy();
	});

	it("renders flow run section with no tags", () => {
		const flowRun = createFakeFlowRun({ tags: [] });

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("Tags")).toBeTruthy();
		const noneElements = screen.getAllByText("None");
		expect(noneElements.length).toBeGreaterThan(0);
	});

	it("renders flow run section with state message", () => {
		const flowRun = createFakeFlowRun({
			state: {
				id: "test-state-id",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-15T10:30:00.000Z",
				message: "Test state message",
				data: null,
				state_details: {
					flow_run_id: "test-flow-run-id",
					task_run_id: null,
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
		});

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("State Message")).toBeTruthy();
		expect(screen.getByText("Test state message")).toBeTruthy();
	});

	it("renders None when state message is missing", () => {
		const flowRun = createFakeFlowRun({
			state: {
				id: "test-state-id",
				type: "COMPLETED",
				name: "Completed",
				timestamp: "2024-01-15T10:30:00.000Z",
				message: null,
				data: null,
				state_details: {
					flow_run_id: "test-flow-run-id",
					task_run_id: null,
					child_flow_run_id: null,
					scheduled_time: null,
					cache_key: null,
					cache_expiration: null,
					deferred: false,
					untrackable_result: false,
					pause_timeout: null,
					pause_reschedule: false,
					pause_key: null,
					run_input_keyset: null,
					refresh_cache: null,
					retriable: null,
					transition_id: null,
					task_parameters_id: null,
				},
			},
		});

		render(<FlowRunSection flowRun={flowRun} />);

		expect(screen.getByText("State Message")).toBeTruthy();
		const noneElements = screen.getAllByText("None");
		expect(noneElements.length).toBeGreaterThan(0);
	});
});
