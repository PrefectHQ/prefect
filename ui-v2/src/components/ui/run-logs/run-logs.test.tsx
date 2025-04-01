import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunLogs } from ".";

import { createFakeLog, createFakeTaskRun } from "@/mocks";

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
		const screen = render(<RunLogs logs={logs} />);

		expect(screen.getByText("CRITICAL")).toBeVisible();
		expect(screen.getByText("ERROR")).toBeVisible();
		expect(screen.getByText("WARNING")).toBeVisible();
		expect(screen.getByText("INFO")).toBeVisible();
		expect(screen.getByText("DEBUG")).toBeVisible();
		expect(screen.getByText("CUSTOM")).toBeVisible();
	});

	it("should display a log message", () => {
		const log = createFakeLog({ message: "Hello, world!" });
		const screen = render(<RunLogs logs={[log]} />);

		expect(screen.getByText("Hello, world!")).toBeVisible();
	});

	it("should display a log day and time", () => {
		const log = createFakeLog({ timestamp: "2021-01-01T00:00:00.000Z" });
		const screen = render(<RunLogs logs={[log]} />);

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
		const screen = render(<RunLogs logs={[log]} taskRun={taskRun} />);

		expect(screen.getByText("test_task")).toBeVisible();
		expect(screen.getByText("prefect.test_logger")).toBeVisible();
	});

	it("should show multiple day dividers when there are logs from different days", () => {
		const log1 = createFakeLog({ timestamp: "2021-01-01T00:00:00.000Z" });
		const log2 = createFakeLog({ timestamp: "2021-01-02T00:00:00.000Z" });
		const screen = render(<RunLogs logs={[log1, log2]} />);

		expect(screen.getByText("Jan 1, 2021")).toBeVisible();
		expect(screen.getByText("Jan 2, 2021")).toBeVisible();
	});
});
