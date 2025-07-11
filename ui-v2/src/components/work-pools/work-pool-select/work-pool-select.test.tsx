import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { WorkPool } from "@/api/work-pools";
import { createFakeWorkPool } from "@/mocks";
import { WorkPoolSelect } from "./work-pool-select";

describe("WorkPoolSelect", () => {
	beforeAll(mockPointerEvents);

	const mockListWorkPoolsAPI = (workPools: Array<WorkPool>) => {
		server.use(
			http.post(buildApiUrl("/work_pools/filter"), () => {
				return HttpResponse.json(workPools);
			}),
		);
	};

	it("able to select a workpool", async () => {
		const mockOnSelect = vi.fn();
		mockListWorkPoolsAPI([
			createFakeWorkPool({ name: "my work pool 0" }),
			createFakeWorkPool({ name: "my work pool 1" }),
		]);

		const user = userEvent.setup();

		// ------------ Setup
		render(<WorkPoolSelect selected={undefined} onSelect={mockOnSelect} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() =>
			expect(screen.getByLabelText(/select a work pool/i)).toBeVisible(),
		);

		// ------------ Act
		await user.click(screen.getByLabelText(/select a work pool/i));
		await user.click(screen.getByRole("option", { name: "my work pool 0" }));

		// ------------ Assert
		expect(mockOnSelect).toHaveBeenLastCalledWith("my work pool 0");
	});

	it("able to select a preset option", async () => {
		const mockOnSelect = vi.fn();
		mockListWorkPoolsAPI([
			createFakeWorkPool({ name: "my work pool 0" }),
			createFakeWorkPool({ name: "my work pool 1" }),
		]);

		const user = userEvent.setup();

		// ------------ Setup
		const PRESETS = [{ label: "None", value: undefined }];
		render(
			<WorkPoolSelect
				presetOptions={PRESETS}
				selected={undefined}
				onSelect={mockOnSelect}
			/>,
			{ wrapper: createWrapper() },
		);

		await waitFor(() =>
			expect(screen.getByLabelText(/select a work pool/i)).toBeVisible(),
		);

		// ------------ Act
		await user.click(screen.getByLabelText(/select a work pool/i));
		await user.click(screen.getByRole("option", { name: "None" }));

		// ------------ Assert
		expect(mockOnSelect).toHaveBeenLastCalledWith(undefined);
	});

	it("has the selected value displayed", async () => {
		mockListWorkPoolsAPI([
			createFakeWorkPool({ name: "my work pool 0" }),
			createFakeWorkPool({ name: "my work pool 1" }),
		]);

		// ------------ Setup
		const PRESETS = [{ label: "None", value: undefined }];
		render(
			<WorkPoolSelect
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
