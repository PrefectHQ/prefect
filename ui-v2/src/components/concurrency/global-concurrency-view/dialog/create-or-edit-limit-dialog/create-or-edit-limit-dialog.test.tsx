import { CreateOrEditLimitDialog } from "./create-or-edit-limit-dialog";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeAll, describe, expect, it, vi } from "vitest";

const MOCK_DATA = {
	id: "0",
	created: "2021-01-01T00:00:00Z",
	updated: "2021-01-01T00:00:00Z",
	active: false,
	name: "global concurrency limit 0",
	limit: 0,
	active_slots: 0,
	slot_decay_per_second: 0,
};

describe("CreateOrEditLimitDialog", () => {
	beforeAll(() => {
		class ResizeObserverMock {
			observe() {}
			unobserve() {}
			disconnect() {}
		}

		global.ResizeObserver = ResizeObserverMock;
	});

	it("able to create a new limit", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(
			<CreateOrEditLimitDialog
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
			<CreateOrEditLimitDialog
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
});
