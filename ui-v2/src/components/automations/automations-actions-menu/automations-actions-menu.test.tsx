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
import { AutomationsActionsMenu } from "./automations-actions-menu";

describe("AutomationsActionsMenu", () => {
	const AutomationsActionsMenuRouter = ({
		id,
		onDelete,
	}: {
		id: string;
		onDelete: () => void;
	}) => {
		const rootRoute = createRootRoute({
			component: () => <AutomationsActionsMenu id={id} onDelete={onDelete} />,
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

	it("opens dropdown menu when trigger is clicked", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(<AutomationsActionsMenuRouter id="test-id" onDelete={vi.fn()} />),
		);

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		expect(screen.getByRole("menuitem", { name: /copy id/i })).toBeVisible();
	});

	it("copies the id and shows toast notification", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(
				<>
					<Toaster />
					<AutomationsActionsMenuRouter id="my-id" onDelete={vi.fn()} />
				</>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /copy id/i }));

		await waitFor(() => {
			expect(screen.getByText("ID copied")).toBeVisible();
		});
	});

	it("renders edit link with correct automation edit href", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(
				<AutomationsActionsMenuRouter
					id="test-automation-id"
					onDelete={vi.fn()}
				/>,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		const editLink = screen.getByRole("menuitem", { name: /edit/i });
		expect(editLink).toBeVisible();
		expect(editLink).toHaveAttribute(
			"href",
			expect.stringContaining(
				"/automations/automation/test-automation-id/edit",
			),
		);
	});

	it("calls delete callback when delete is clicked", async () => {
		const user = userEvent.setup();
		const mockOnDelete = vi.fn();

		await waitFor(() =>
			render(
				<AutomationsActionsMenuRouter id="test-id" onDelete={mockOnDelete} />,
			),
		);

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));

		expect(mockOnDelete).toHaveBeenCalledOnce();
	});

	it("documentation link points to external docs", async () => {
		const user = userEvent.setup();

		await waitFor(() =>
			render(<AutomationsActionsMenuRouter id="test-id" onDelete={vi.fn()} />),
		);

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		const docsLink = screen.getByRole("menuitem", { name: /documentation/i });
		expect(docsLink).toBeVisible();
		expect(docsLink).toHaveAttribute(
			"href",
			expect.stringContaining("docs.prefect.io"),
		);
	});
});
