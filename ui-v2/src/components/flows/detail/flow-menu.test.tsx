import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { createFakeFlow } from "@/mocks";
import { FlowMenu, type FlowMenuProps } from "./flow-menu";

describe("FlowMenu", () => {
	const FlowMenuRouter = (props: FlowMenuProps) => {
		const rootRoute = createRootRoute({
			component: () => (
				<>
					<Toaster />
					<FlowMenu {...props} />
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

	const flow = createFakeFlow({
		id: "test-flow-id",
		name: "test-flow",
	});

	const mockOnDelete = vi.fn();

	it("renders the dropdown menu with correct options", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(<FlowMenuRouter flow={flow} onDelete={mockOnDelete} />),
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		await waitFor(() => {
			expect(screen.getByText("Actions")).toBeInTheDocument();
			expect(screen.getByText("Copy ID")).toBeInTheDocument();
			expect(screen.getByText("Delete")).toBeInTheDocument();
		});
	});

	it("copies the flow ID to clipboard when 'Copy ID' is clicked", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(<FlowMenuRouter flow={flow} onDelete={mockOnDelete} />),
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		const copyIdOption = await screen.findByText("Copy ID");
		await user.click(copyIdOption);

		await waitFor(() => {
			const toast = screen.getByText("ID copied");
			expect(toast).toBeInTheDocument();
		});
	});

	it("calls the onDelete function when 'Delete' is clicked", async () => {
		const user = userEvent.setup();
		const onDeleteMock = vi.fn();

		await waitFor(() =>
			render(<FlowMenuRouter flow={flow} onDelete={onDeleteMock} />),
		);

		const dropdownButton = screen.getByRole("button", { name: /open menu/i });
		await user.click(dropdownButton);

		const deleteOption = await screen.findByText("Delete");
		await user.click(deleteOption);

		expect(onDeleteMock).toHaveBeenCalledOnce();
	});

	it("closes the menu when an option is selected", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(<FlowMenuRouter flow={flow} onDelete={mockOnDelete} />),
		);

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
