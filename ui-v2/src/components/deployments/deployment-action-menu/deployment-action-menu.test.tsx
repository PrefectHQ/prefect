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
import {
	DeploymentActionMenu,
	type DeploymentActionMenuProps,
} from "./deployment-action-menu";

describe("DeploymentActionMenu", () => {
	// Wraps component in test with a Tanstack router provider
	const DeploymentActionMenuRouter = (props: DeploymentActionMenuProps) => {
		const rootRoute = createRootRoute({
			component: () => <DeploymentActionMenu {...props} />,
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

	it("copies the id", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		await waitFor(() =>
			render(
				<>
					<Toaster />
					<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />
				</>,
			),
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: "Copy ID" }));

		// ------------ Assert
		await waitFor(() => {
			expect(screen.getByText("ID copied")).toBeVisible();
		});
	});

	it("calls delete option ", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnDeleteFn = vi.fn();

		await waitFor(() =>
			render(
				<DeploymentActionMenuRouter id="my-id" onDelete={mockOnDeleteFn} />,
			),
		);

		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: /delete/i }));

		// ------------ Assert
		expect(mockOnDeleteFn).toHaveBeenCalledOnce();
	});

	it("edit option is visible", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		await waitFor(() =>
			render(<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />),
		);

		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		// ------------ Assert
		expect(screen.getByRole("menuitem", { name: /edit/i })).toBeVisible();
	});

	it("duplicate option is visible", async () => {
		const user = userEvent.setup();

		// ------------ Setup
		await waitFor(() =>
			render(<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />),
		);

		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		// ------------ Assert
		expect(screen.getByRole("menuitem", { name: /duplicate/i })).toBeVisible();
	});
});
