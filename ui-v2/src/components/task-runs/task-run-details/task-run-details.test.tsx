import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunDetails } from "./task-run-details";

describe("TaskRunDetails", () => {
	it("should display flow run link", () => {
		const taskRun = createFakeTaskRun({
			name: "test-task-name",
			flow_run_name: "test-flow-name",
		});
		const screen = render(<TaskRunDetails taskRun={taskRun} />);

		expect(screen.getByText("test-flow-name")).toBeInTheDocument();
	});

	it("should display task run ID", () => {
		const taskRun = createFakeTaskRun({ id: "test-task-id" });
		const screen = render(<TaskRunDetails taskRun={taskRun} />);

		expect(screen.getByText("test-task-id")).toBeInTheDocument();
	});

	it("should display start time", () => {
		const startTime = new Date().toISOString();
		const taskRun = createFakeTaskRun({
			start_time: startTime,
		});
		const screen = render(<TaskRunDetails taskRun={taskRun} />);

		expect(screen.getByText("Start Time").nextSibling).toBeInTheDocument();
	});

	it("should display task tags", () => {
		const taskRun = createFakeTaskRun({
			tags: ["tag1", "tag2", "tag3"],
		});
		const screen = render(<TaskRunDetails taskRun={taskRun} />);

		expect(screen.getByText("tag1")).toBeInTheDocument();
		expect(screen.getByText("tag2")).toBeInTheDocument();
		expect(screen.getByText("tag3")).toBeInTheDocument();
	});

	it("should display empty state when no taskRun is provided", () => {
		const screen = render(<TaskRunDetails taskRun={null} />);

		expect(
			screen.getByText("No task run details available"),
		).toBeInTheDocument();
	});

	it("should display task configuration section", () => {
		const taskRun = createFakeTaskRun();
		const screen = render(<TaskRunDetails taskRun={taskRun} />);

		expect(screen.getByText("Task configuration")).toBeInTheDocument();
		expect(screen.getByText("Version")).toBeInTheDocument();
		expect(screen.getByText("Retries")).toBeInTheDocument();
		expect(screen.getByText("Retry Delay")).toBeInTheDocument();
	});
});
