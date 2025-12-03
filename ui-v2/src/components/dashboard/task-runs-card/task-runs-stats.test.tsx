import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createFakeTaskRun } from "@/mocks";
import { TaskRunStats } from "./task-runs-stats";

describe("TaskRunStats", () => {
	describe("count calculations", () => {
		it("displays correct total count", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("3");
		});

		it("displays correct running count", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-running")).toHaveTextContent("2");
		});

		it("displays correct completed count", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed")).toHaveTextContent("3");
		});

		it("displays correct failed count", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-failed")).toHaveTextContent("2");
		});

		it("includes CRASHED state in failed count", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "CRASHED" }),
				createFakeTaskRun({ state_type: "CRASHED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-failed")).toHaveTextContent("3");
		});

		it("handles multiple task runs with the same state type", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("5");
			expect(screen.getByTestId("stat-running")).toHaveTextContent("5");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("0");
		});
	});

	describe("empty array handling", () => {
		it("handles empty taskRuns array", () => {
			render(<TaskRunStats taskRuns={[]} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-running")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("0");
		});

		it("displays 0.0% for percentages when array is empty", () => {
			render(<TaskRunStats taskRuns={[]} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"0.0%",
			);
			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"0.0%",
			);
		});
	});

	describe("null/undefined state_type handling", () => {
		it("handles task runs with null state_type", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: null }),
				createFakeTaskRun({ state_type: null }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("3");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("1");
		});

		it("handles task runs with undefined state_type", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: undefined }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("2");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("1");
		});

		it("does not count null state_type in any specific state category", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: null }),
				createFakeTaskRun({ state_type: null }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("2");
			expect(screen.getByTestId("stat-running")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("0");
		});
	});

	describe("percentage calculations", () => {
		it("calculates completed percentage based on finished runs", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"50.0%",
			);
		});

		it("calculates failed percentage based on finished runs", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"75.0%",
			);
		});

		it("handles division by zero when no finished runs exist", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "SCHEDULED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"0.0%",
			);
			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"0.0%",
			);
		});

		it("displays 100% completed when all finished runs are completed", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"100.0%",
			);
			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"0.0%",
			);
		});

		it("displays 100% failed when all finished runs are failed", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "CRASHED" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"0.0%",
			);
			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"100.0%",
			);
		});

		it("calculates percentages with decimal precision", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"66.7%",
			);
			expect(screen.getByTestId("stat-failed-percentage")).toHaveTextContent(
				"33.3%",
			);
		});

		it("excludes running tasks from percentage calculation denominator", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"100.0%",
			);
		});
	});

	describe("dynamic updates", () => {
		it("updates counts when props change", () => {
			const initialTaskRuns = [createFakeTaskRun({ state_type: "COMPLETED" })];

			const { rerender } = render(<TaskRunStats taskRuns={initialTaskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("1");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("1");

			const updatedTaskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			rerender(<TaskRunStats taskRuns={updatedTaskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("3");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("2");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("1");
		});

		it("updates percentages when props change", () => {
			const initialTaskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			const { rerender } = render(<TaskRunStats taskRuns={initialTaskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"50.0%",
			);

			const updatedTaskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			rerender(<TaskRunStats taskRuns={updatedTaskRuns} />);

			expect(screen.getByTestId("stat-completed-percentage")).toHaveTextContent(
				"75.0%",
			);
		});
	});

	describe("all state types", () => {
		it("handles all possible state types correctly", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
				createFakeTaskRun({ state_type: "RUNNING" }),
				createFakeTaskRun({ state_type: "SCHEDULED" }),
				createFakeTaskRun({ state_type: "CANCELLED" }),
				createFakeTaskRun({ state_type: "PENDING" }),
				createFakeTaskRun({ state_type: "CRASHED" }),
				createFakeTaskRun({ state_type: "PAUSED" }),
				createFakeTaskRun({ state_type: "CANCELLING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("9");
			expect(screen.getByTestId("stat-running")).toHaveTextContent("1");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("1");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("2");
		});

		it("does not count SCHEDULED, CANCELLED, PENDING, PAUSED, CANCELLING in specific categories", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "SCHEDULED" }),
				createFakeTaskRun({ state_type: "CANCELLED" }),
				createFakeTaskRun({ state_type: "PENDING" }),
				createFakeTaskRun({ state_type: "PAUSED" }),
				createFakeTaskRun({ state_type: "CANCELLING" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(screen.getByTestId("stat-total")).toHaveTextContent("5");
			expect(screen.getByTestId("stat-running")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-completed")).toHaveTextContent("0");
			expect(screen.getByTestId("stat-failed")).toHaveTextContent("0");
		});
	});

	describe("UI rendering", () => {
		it("renders the stats container", () => {
			render(<TaskRunStats taskRuns={[]} />);

			expect(screen.getByTestId("task-run-stats")).toBeInTheDocument();
		});

		it("renders all stat labels", () => {
			render(<TaskRunStats taskRuns={[]} />);

			expect(screen.getByText("Total")).toBeInTheDocument();
			expect(screen.getByText("Running")).toBeInTheDocument();
			expect(screen.getByText("Completed")).toBeInTheDocument();
			expect(screen.getByText("Failed")).toBeInTheDocument();
		});

		it("renders percentage indicators for completed and failed", () => {
			const taskRuns = [
				createFakeTaskRun({ state_type: "COMPLETED" }),
				createFakeTaskRun({ state_type: "FAILED" }),
			];

			render(<TaskRunStats taskRuns={taskRuns} />);

			expect(
				screen.getByTestId("stat-completed-percentage"),
			).toBeInTheDocument();
			expect(screen.getByTestId("stat-failed-percentage")).toBeInTheDocument();
		});
	});
});
