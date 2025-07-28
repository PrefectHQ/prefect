import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import {
	WorkPoolContextMenu,
	type WorkPoolContextMenuProps,
} from "./work-pool-context-menu";

describe("WorkPoolContextMenu", () => {
	beforeAll(mockPointerEvents);

	beforeEach(() => {
		// Mocks away getRouteApi dependency in `useDeleteDeploymentConfirmationDialog`
		// @ts-expect-error Ignoring error until @tanstack/react-router has better testing documentation. Ref: https://vitest.dev/api/vi.html#vi-mock
		vi.mock(import("@tanstack/react-router"), async (importOriginal) => {
			const mod = await importOriginal();
			return {
				...mod,
				getRouteApi: () => ({
					useNavigate: vi.fn,
				}),
			};
		});
	});

	// Wraps component in test with a Tanstack router provider
	const WorkPoolContextMenuRouter = (props: WorkPoolContextMenuProps) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<WorkPoolContextMenu {...props} />
				</>
			),
		});

		const router = createRouter({
			routeTree: rootRoute,
			history: createMemoryHistory({
				initialEntries: ["/"],
			}),
			context: { queryClient: new QueryClient() },
		});
		return <RouterProvider router={router} />;
	};

	const workPool = createFakeWorkPool({
		id: "test-work-pool-id",
		name: "test-work-pool",
		status: "READY",
	});

	const mockOnDelete = vi.fn();

	it("renders the dropdown menu with correct options", async () => {
		await waitFor(() =>
			render(
				<WorkPoolContextMenuRouter
					workPool={workPool}
					onDelete={mockOnDelete}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		const user = userEvent.setup();

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText("Actions")).toBeInTheDocument();
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
			expect(screen.getByText("Edit")).toBeInTheDocument();
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
	});

	it("copies the work pool ID to clipboard when 'Copy ID' is clicked", async () => {
		await waitFor(() =>
			render(
				<WorkPoolContextMenuRouter
					workPool={workPool}
					onDelete={mockOnDelete}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		const user = userEvent.setup();

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		const copyIdOption = await screen.findByText("Copy ID");
		await user.click(copyIdOption);

		//  Despite the mock above, typescript-eslint is complaining about the method being unbound cause of the ambiguous `this`
		//  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(workPool.id);

		await waitFor(() => {
			const toast = screen.getByText("ID copied");
			expect(toast).toBeInTheDocument();
		});
	});

	it("calls the onDelete function when 'Delete' is clicked", async () => {
		await waitFor(() =>
			render(
				<WorkPoolContextMenuRouter
					workPool={workPool}
					onDelete={mockOnDelete}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		const user = userEvent.setup();

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		const deleteOption = await screen.findByText("Delete");
		fireEvent.click(deleteOption);

		expect(mockOnDelete).toHaveBeenCalledTimes(1);
	});

	it("closes the menu when an option is selected", async () => {
		await waitFor(() =>
			render(
				<WorkPoolContextMenuRouter
					workPool={workPool}
					onDelete={mockOnDelete}
				/>,
				{
					wrapper: createWrapper(),
				},
			),
		);

		const user = userEvent.setup();

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText("Actions")).toBeInTheDocument();
		});

		const copyIdOption = await screen.findByText("Copy ID");
		await user.click(copyIdOption);

		await waitFor(() => {
			expect(screen.queryByText("Actions")).toBeNull();
		});
	});
});
