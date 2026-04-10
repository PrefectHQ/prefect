import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { GlobalConcurrencyLimitsCreateOrEditDialog } from "./global-concurrency-limits-create-or-edit-dialog";

const ResizeObserverMock = class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	active: false,
	name: "global concurrency limit 0",
	limit: 1,
	active_slots: 0,
	slot_decay_per_second: 0,
};

describe("GlobalConcurrencyLimitsCreateOrEditDialog", () => {
	beforeAll(() => {
		global.ResizeObserver = ResizeObserverMock;
	});

	it("able to create a new limit", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(
			<GlobalConcurrencyLimitsCreateOrEditDialog
				onOpenChange={vi.fn()}
				onSubmit={mockOnSubmitFn}
			/>,
			{ wrapper: createWrapper() },
		);
		// ------------ Act

		await user.type(screen.getByLabelText(/name/i), MOCK_DATA.name);
		await user.type(
			screen.getByLabelText("Concurrency Limit"),
			MOCK_DATA.limit.toString(),
		);
		await user.type(
			screen.getByLabelText("Slot Decay Per Second"),
			MOCK_DATA.slot_decay_per_second.toString(),
		);
		await user.click(screen.getByRole("button", { name: /save/i }));

		// ------------ Assert
		expect(mockOnSubmitFn).toHaveBeenCalledOnce();
	});

	it("able to edit a limit", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(
			<GlobalConcurrencyLimitsCreateOrEditDialog
				limitToUpdate={MOCK_DATA}
				onOpenChange={vi.fn()}
				onSubmit={mockOnSubmitFn}
			/>,
			{ wrapper: createWrapper() },
		);
		// ------------ Act

		await user.type(screen.getByLabelText(/name/i), MOCK_DATA.name);
		await user.type(
			screen.getByLabelText("Concurrency Limit"),
			MOCK_DATA.limit.toString(),
		);
		await user.type(
			screen.getByLabelText("Slot Decay Per Second"),
			MOCK_DATA.slot_decay_per_second.toString(),
		);
		await user.click(screen.getByRole("button", { name: /update/i }));

		// ------------ Assert
		expect(mockOnSubmitFn).toHaveBeenCalledOnce();
	});

	it("shows validation error when concurrency limit is 0", async () => {
		const user = userEvent.setup();

		render(
			<GlobalConcurrencyLimitsCreateOrEditDialog
				onOpenChange={vi.fn()}
				onSubmit={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const limitInput = screen.getByLabelText("Concurrency Limit");
		await user.clear(limitInput);
		await user.type(limitInput, "0");
		await user.type(screen.getByLabelText(/name/i), "test-limit");
		await user.click(screen.getByRole("button", { name: /save/i }));

		expect(
			await screen.findByText("Concurrency limit must be greater than 0"),
		).toBeVisible();
	});

	it("shows validation error when concurrency limit is negative", async () => {
		const user = userEvent.setup();

		render(
			<GlobalConcurrencyLimitsCreateOrEditDialog
				onOpenChange={vi.fn()}
				onSubmit={vi.fn()}
			/>,
			{ wrapper: createWrapper() },
		);

		const limitInput = screen.getByLabelText("Concurrency Limit");
		await user.clear(limitInput);
		await user.type(limitInput, "-5");
		await user.type(screen.getByLabelText(/name/i), "test-limit");
		await user.click(screen.getByRole("button", { name: /save/i }));

		expect(
			await screen.findByText("Concurrency limit must be greater than 0"),
		).toBeVisible();
	});
});
