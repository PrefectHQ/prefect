import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createFakeLog, createFakeTaskRun } from "@/mocks";
import { RunLogs } from ".";

describe("RunLogs", () => {
	it("should display a log level badge", () => {
		const logs = [
			createFakeLog({ level: 50 }),
			createFakeLog({ level: 40 }),
			createFakeLog({ level: 30 }),
			createFakeLog({ level: 20 }),
			createFakeLog({ level: 10 }),
			createFakeLog({ level: 0 }),
		];
		const mockBottomReached = vi.fn();
		const screen = render(
			<RunLogs
				logs={logs}
				onBottomReached={mockBottomReached}
				virtualize={false}
			/>,
		);

		expect(screen.getByText("CRITICAL")).toBeVisible();
		expect(screen.getByText("ERROR")).toBeVisible();
		expect(screen.getByText("WARNING")).toBeVisible();
		expect(screen.getByText("INFO")).toBeVisible();
		expect(screen.getByText("DEBUG")).toBeVisible();

		// Scroll to the bottom to see the last log
		fireEvent.scroll(screen.getByRole("log"), { target: { scrollTop: 500 } });
		expect(screen.getByText("CUSTOM")).toBeVisible();

		// Check that onBottomReached is called
		expect(mockBottomReached).toHaveBeenCalled();
	});

	it("should display a log message", () => {
		const log = createFakeLog({ message: "Hello, world!" });
		const screen = render(
			<RunLogs logs={[log]} onBottomReached={vi.fn()} virtualize={false} />,
		);

		expect(screen.getByText("Hello, world!")).toBeVisible();
	});

	it("should display a log day and time", () => {
		const log = createFakeLog({ timestamp: "2021-01-01T00:00:00.000Z" });
		const screen = render(
			<RunLogs logs={[log]} onBottomReached={vi.fn()} virtualize={false} />,
		);

		expect(screen.getByText("Jan 1, 2021")).toBeVisible();
		expect(screen.getByText("12:00:00 AM")).toBeVisible();
	});

	it("should display a task name and logger name", () => {
		const log = createFakeLog({
			name: "prefect.test_logger",
		});
		const taskRun = createFakeTaskRun({
			name: "test_task",
		});
		const screen = render(
			<RunLogs
				logs={[log]}
				taskRun={taskRun}
				onBottomReached={vi.fn()}
				virtualize={false}
			/>,
		);

		expect(screen.getByText("test_task")).toBeVisible();
		expect(screen.getByText("prefect.test_logger")).toBeVisible();
	});

	it("should show multiple day dividers when there are logs from different days", () => {
		const log1 = createFakeLog({ timestamp: "2021-01-01T00:00:00.000Z" });
		const log2 = createFakeLog({ timestamp: "2021-01-02T00:00:00.000Z" });
		const screen = render(
			<RunLogs
				logs={[log1, log2]}
				onBottomReached={vi.fn()}
				virtualize={false}
			/>,
		);

		expect(screen.getByText("Jan 1, 2021")).toBeVisible();
		expect(screen.getByText("Jan 2, 2021")).toBeVisible();
	});
});
