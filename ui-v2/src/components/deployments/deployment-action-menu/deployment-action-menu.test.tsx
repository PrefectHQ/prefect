import { Toaster } from "@/components/ui/toaster";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QueryClient } from "@tanstack/react-query";
import {
	RouterProvider,
	createMemoryHistory,
	createRootRoute,
	createRouter,
} from "@tanstack/react-router";
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
		// @ts-expect-error - Type error from using a test router
		return <RouterProvider router={router} />;
	};

	it("copies the id", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />
			</>,
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: "Copy ID" }));

		// ------------ Assert
		expect(screen.getByText("ID copied")).toBeVisible();
	});

	it("calls delete option ", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnDeleteFn = vi.fn();

		render(<DeploymentActionMenuRouter id="my-id" onDelete={mockOnDeleteFn} />);

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
		render(<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />);

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
		render(<DeploymentActionMenuRouter id="my-id" onDelete={vi.fn()} />);

		// ------------ Act

		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		// ------------ Assert
		expect(screen.getByRole("menuitem", { name: /duplicate/i })).toBeVisible();
	});
});
