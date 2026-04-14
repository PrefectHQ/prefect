import { render, screen } from "@testing-library/react";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { WorkPoolQueueForm } from "./work-pool-queue-form";

vi.mock("@/api/work-pool-queues", () => ({
	useCreateWorkPoolQueueMutation: () => ({
		mutate: vi.fn(),
		isPending: false,
	}),
	useUpdateWorkPoolQueueMutation: () => ({
		mutate: vi.fn(),
		isPending: false,
	}),
}));

describe("WorkPoolQueueForm", () => {
	const defaultProps = {
		workPoolName: "test-pool",
		onSubmit: vi.fn(),
		onCancel: vi.fn(),
	};

	it("renders create form with all fields", () => {
		render(<WorkPoolQueueForm {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("Name")).toBeInTheDocument();
		expect(screen.getByLabelText("Description")).toBeInTheDocument();
		expect(screen.getByLabelText("Flow Run Concurrency")).toBeInTheDocument();
		expect(screen.getByText("Priority")).toBeInTheDocument();
	});

	it("renders Create button in create mode", () => {
		render(<WorkPoolQueueForm {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
	});

	it("renders Save button in edit mode", () => {
		const queue = createFakeWorkPoolQueue({
			name: "test-queue",
			work_pool_name: "test-pool",
		});

		render(<WorkPoolQueueForm {...defaultProps} queueToEdit={queue} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
	});

	it("renders Cancel button", () => {
		render(<WorkPoolQueueForm {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
	});

	it("calls onCancel when Cancel button is clicked", () => {
		const onCancel = vi.fn();
		render(<WorkPoolQueueForm {...defaultProps} onCancel={onCancel} />, {
			wrapper: createWrapper(),
		});

		screen.getByRole("button", { name: "Cancel" }).click();
		expect(onCancel).toHaveBeenCalled();
	});

	it("populates form with queue data in edit mode", () => {
		const queue = createFakeWorkPoolQueue({
			name: "my-queue",
			description: "My description",
			concurrency_limit: 5,
			priority: 2,
			work_pool_name: "test-pool",
		});

		render(<WorkPoolQueueForm {...defaultProps} queueToEdit={queue} />, {
			wrapper: createWrapper(),
		});

		expect(screen.getByLabelText("Name")).toHaveValue("my-queue");
		expect(screen.getByLabelText("Description")).toHaveValue("My description");
	});
});
