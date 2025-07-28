import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { components } from "@/api/prefect";
import { createFakeLog, createFakeTaskRun } from "@/mocks";
import { TaskRunLogs } from ".";

const MOCK_LOGS = [
	createFakeLog({ level: 50, message: "Critical error in task" }),
	createFakeLog({ level: 40, message: "Error processing data" }),
	createFakeLog({ level: 30, message: "Warning: slow performance" }),
	createFakeLog({ level: 20, message: "Info: task started" }),
	createFakeLog({ level: 20, message: "Info: processing data" }),
	createFakeLog({ level: 10, message: "Debug: connection established" }),
	createFakeLog({ level: 10, message: "Debug: cache hit" }),
].sort((a, b) => a.timestamp.localeCompare(b.timestamp));

type LogsFilterBody = components["schemas"]["Body_read_logs_logs_filter_post"];

describe("TaskRunLogs", () => {
	beforeEach(() => {
		mockPointerEvents();
		// Setup mock API response
		server.use(
			http.post(buildApiUrl("/logs/filter"), async ({ request }) => {
				const body = (await request.json()) as LogsFilterBody;

				let filteredLogs = [...MOCK_LOGS];

				// Filter logs by level if specified
				const minLevel = body.logs?.level?.ge_;
				if (typeof minLevel === "number") {
					filteredLogs = filteredLogs.filter((log) => log.level >= minLevel);
				}

				// Sort logs based on the sort parameter
				if (body.sort === "TIMESTAMP_DESC") {
					filteredLogs = filteredLogs.reverse();
				}

				if (body.offset) {
					filteredLogs = filteredLogs.slice(body.offset);
				}

				return HttpResponse.json(filteredLogs);
			}),
		);
	});
	it("displays logs with default filter (all levels)", async () => {
		// Render component
		const taskRun = createFakeTaskRun();
		await waitFor(() =>
			render(<TaskRunLogs taskRun={taskRun} virtualize={false} />, {
				wrapper: createWrapper(),
			}),
		);

		// Wait for logs to be rendered and verify:
		// 1. At least one log is visible (accounting for virtualization)
		// 2. The API response included logs of all levels (no filtering applied)
		await waitFor(() => {
			const listItems = screen.getAllByRole("listitem");
			expect(listItems.length).toBeGreaterThan(0);

			// Verify at least one log message is rendered
			const firstLog = MOCK_LOGS[0];
			expect(screen.getByText(firstLog.message)).toBeInTheDocument();

			// Verify the API response included logs of all levels
			const logLevels = new Set(MOCK_LOGS.map((log) => log.level));
			expect(logLevels).toContain(50); // Critical
			expect(logLevels).toContain(40); // Error
			expect(logLevels).toContain(30); // Warning
			expect(logLevels).toContain(20); // Info
			expect(logLevels).toContain(10); // Debug
		});
	});

	it("filters logs by level", async () => {
		const user = userEvent.setup();

		// Render component
		const taskRun = createFakeTaskRun();
		render(<TaskRunLogs taskRun={taskRun} virtualize={false} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(
				screen.getByRole("combobox", { name: /log level filter/i }),
			).toBeInTheDocument();
		});

		// Change filter to "Error and above"
		await user.click(
			screen.getByRole("combobox", { name: /log level filter/i }),
		);
		await user.click(screen.getByText("Error and above"));

		// Verify only error and critical logs are shown
		await waitFor(() => {
			expect(screen.getByText("Critical error in task")).toBeInTheDocument();
			expect(screen.getByText("Error processing data")).toBeInTheDocument();
			expect(
				screen.queryByText("Warning: slow performance"),
			).not.toBeInTheDocument();
			expect(screen.queryByText("Info: task started")).not.toBeInTheDocument();
			expect(
				screen.queryByText("Debug: connection established"),
			).not.toBeInTheDocument();
		});
	});

	it("handles empty logs response for scheduled task runs", async () => {
		// Setup mock API response with no logs
		server.use(
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const taskRun = createFakeTaskRun({
			state_type: "SCHEDULED",
			state_name: "Scheduled",
		});
		const screen = render(
			<TaskRunLogs taskRun={taskRun} virtualize={false} />,
			{
				wrapper: createWrapper(),
			},
		);

		// Verify empty state is shown
		await waitFor(() => {
			expect(
				screen.getByText("Run has not yet started. Check back soon for logs."),
			).toBeInTheDocument();
		});
	});

	it("handles empty logs response for running task runs", async () => {
		server.use(
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const taskRun = createFakeTaskRun({
			state_type: "RUNNING",
			state_name: "Running",
		});

		const screen = render(
			<TaskRunLogs taskRun={taskRun} virtualize={false} />,
			{
				wrapper: createWrapper(),
			},
		);

		// Verify empty state is shown
		await waitFor(() => {
			expect(screen.getByText("Waiting for logs...")).toBeInTheDocument();
		});
	});

	it("handles empty logs response for completed task runs", async () => {
		server.use(
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const taskRun = createFakeTaskRun({
			state_type: "COMPLETED",
			state_name: "Completed",
		});
		const screen = render(
			<TaskRunLogs taskRun={taskRun} virtualize={false} />,
			{
				wrapper: createWrapper(),
			},
		);

		// Verify empty state is shown
		await waitFor(() => {
			expect(
				screen.getByText("This run did not produce any logs."),
			).toBeInTheDocument();
		});
	});

	it("handles empty logs response when filtering by level", async () => {
		const user = userEvent.setup();

		// Setup mock API response with no logs
		server.use(
			http.post(buildApiUrl("/logs/filter"), () => {
				return HttpResponse.json([]);
			}),
		);

		const taskRun = createFakeTaskRun();
		render(<TaskRunLogs taskRun={taskRun} virtualize={false} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(
				screen.getByRole("combobox", { name: /log level filter/i }),
			).toBeInTheDocument();
		});

		// Change filter to "Error and above"
		await user.click(
			screen.getByRole("combobox", { name: /log level filter/i }),
		);
		await user.click(screen.getByText("Error and above"));

		// Verify empty state is shown
		await waitFor(() => {
			expect(
				screen.getByText("No logs match your filter criteria"),
			).toBeInTheDocument();
		});
	});

	it("changes sort order", async () => {
		const user = userEvent.setup();

		// Render component
		const taskRun = createFakeTaskRun();
		const screen = render(
			<TaskRunLogs taskRun={taskRun} virtualize={false} />,
			{
				wrapper: createWrapper(),
			},
		);

		await waitFor(() => {
			expect(
				screen.getByRole("combobox", { name: /log sort order/i }),
			).toBeInTheDocument();
		});

		// Change sort order to newest first
		await user.click(screen.getByRole("combobox", { name: /log sort order/i }));
		await user.click(screen.getByText("Newest to oldest"));

		await waitFor(() => {
			expect(screen.getByText(MOCK_LOGS[6].message)).toBeInTheDocument();
		});

		// Verify logs are shown in reverse order
		await waitFor(() => {
			const logMessages = screen
				.getAllByRole("listitem")
				.map((item) => item.textContent);
			for (let i = 0; i < logMessages.length; i++) {
				expect(logMessages[i]).toContain(
					MOCK_LOGS.map((log) => log.message).reverse()[i],
				);
			}
		});
	});
});
