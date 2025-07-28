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
import { createFakeBlockDocument } from "@/mocks";
import {
	BlockDocumentActionMenu,
	type BlockDocumentActionMenuProps,
} from "./block-document-action-menu";

describe("BlockDocumentActionMenu", () => {
	// Wraps component in test with a Tanstack router provider
	const BlockDocumentActionMenuRouter = (
		props: BlockDocumentActionMenuProps,
	) => {
		const rootRoute = createRootRoute({
			component: () => <BlockDocumentActionMenu {...props} />,
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

	it("copies the block document name", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockBlockDocument = createFakeBlockDocument({
			name: "my-block-document",
		});
		await waitFor(() =>
			render(
				<>
					<Toaster />
					<BlockDocumentActionMenuRouter
						blockDocument={mockBlockDocument}
						onDelete={vi.fn()}
					/>
				</>,
			),
		);
		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);
		await user.click(screen.getByRole("menuitem", { name: "Copy Name" }));

		// ------------ Assert
		await waitFor(() => {
			expect(screen.getByText("Copied to clipboard!")).toBeVisible();
		});
	});

	it("calls delete option ", async () => {
		// ------------ Setup
		const user = userEvent.setup();
		const mockOnDeleteFn = vi.fn();

		await waitFor(() =>
			render(
				<BlockDocumentActionMenuRouter
					blockDocument={createFakeBlockDocument()}
					onDelete={mockOnDeleteFn}
				/>,
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
			render(
				<BlockDocumentActionMenuRouter
					blockDocument={createFakeBlockDocument()}
					onDelete={vi.fn()}
				/>,
			),
		);

		// ------------ Act
		await user.click(
			screen.getByRole("button", { name: /open menu/i, hidden: true }),
		);

		// ------------ Assert
		expect(screen.getByRole("menuitem", { name: /edit/i })).toBeVisible();
	});
});
