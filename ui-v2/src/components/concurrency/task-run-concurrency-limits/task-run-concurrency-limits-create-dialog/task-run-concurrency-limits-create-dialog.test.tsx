import { createFakeTaskRunConcurrencyLimit } from "@/mocks";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { TaskRunConcurrencyLimitsCreateDialog } from "./task-run-concurrency-limits-create-dialog";

const MOCK_DATA = createFakeTaskRunConcurrencyLimit();

describe("TaskRunConcurrencyLimitsCreateDialog", () => {
	beforeAll(() => {
		class ResizeObserverMock {
			observe() {}
			unobserve() {}
			disconnect() {}
		}
		global.ResizeObserver = ResizeObserverMock;
	});
	it("calls onSubmit upon entering form data", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		const mockOnSubmitFn = vi.fn();
		render(
			<TaskRunConcurrencyLimitsCreateDialog
				onOpenChange={vi.fn()}
				onSubmit={mockOnSubmitFn}
			/>,
			{ wrapper: createWrapper() },
		);

		// ------------ Act
		await user.type(screen.getByLabelText(/tag/i), MOCK_DATA.tag);
		await user.type(
			screen.getByLabelText("Concurrency Limit"),
			String(MOCK_DATA.concurrency_limit),
		);

		await user.click(screen.getByRole("button", { name: /add/i }));

		// ------------ Assert
		expect(mockOnSubmitFn).toBeCalled();
	});
});
