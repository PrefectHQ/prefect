import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { WorkQueue } from "@/api/work-queues";
import { createFakeWorkQueue } from "@/mocks";
import { WorkQueueSelect } from "./work-queue-select";

describe("WorkQueueSelect", () => {
	beforeAll(mockPointerEvents);

	const WORK_POOL_NAME = "my-work-pool";

	const mockListWorkPoolWorkQueuesAPI = (workQueues: Array<WorkQueue>) => {
		server.use(
			http.post(
				buildApiUrl("/work_pools/:work_pool_name/queues/filter"),
				() => {
					return HttpResponse.json(workQueues);
				},
			),
		);
	};

	it("able to select a work queue", async () => {
		const mockOnSelect = vi.fn();
		mockListWorkPoolWorkQueuesAPI([
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 0",
			}),
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 1",
			}),
		]);

		const user = userEvent.setup();

		// ------------ Setup
		render(
			<WorkQueueSelect
				workPoolName={WORK_POOL_NAME}
				selected={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a work queue/i)).toBeVisible(),
		);

		// ------------ Act
		await user.click(screen.getByLabelText(/select a work queue/i));
		await user.click(screen.getByRole("option", { name: "my work queue 0" }));

		// ------------ Assert
		expect(mockOnSelect).toHaveBeenLastCalledWith("my work queue 0");
	});

	it("able to select a preset option", async () => {
		const mockOnSelect = vi.fn();
		mockListWorkPoolWorkQueuesAPI([
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 0",
			}),
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 1",
			}),
		]);

		const user = userEvent.setup();

		// ------------ Setup
		const PRESETS = [{ label: "None", value: undefined }];
		render(
			<WorkQueueSelect
				workPoolName={WORK_POOL_NAME}
				presetOptions={PRESETS}
				selected={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a work queue/i)).toBeVisible(),
		);

		// ------------ Act
		await user.click(screen.getByLabelText(/select a work queue/i));
		await user.click(screen.getByRole("option", { name: "None" }));

		// ------------ Assert
		expect(mockOnSelect).toHaveBeenLastCalledWith(undefined);
	});

	it("has the selected value displayed", async () => {
		mockListWorkPoolWorkQueuesAPI([
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 0",
			}),
			createFakeWorkQueue({
				work_pool_name: WORK_POOL_NAME,
				name: "my work queue 1",
			}),
		]);
		// ------------ Setup
		const PRESETS = [{ label: "None", value: undefined }];
		render(
			<WorkQueueSelect
				workPoolName={WORK_POOL_NAME}
				presetOptions={PRESETS}
				selected="my work pool 0"
				onSelect={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		// ------------ Assert
		await waitFor(() =>
			expect(screen.getByText("my work pool 0")).toBeVisible(),
		);
	});
});
