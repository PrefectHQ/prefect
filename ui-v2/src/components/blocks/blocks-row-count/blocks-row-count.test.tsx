import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { BlocksRowCount, type BlocksRowCountProps } from "./blocks-row-count";

// Wraps component in test with a Tanstack router provider
const BlocksRowCountRouter = (props: BlocksRowCountProps) => {
	const rootRoute = createRootRoute({
		component: () => <BlocksRowCount {...props} />,
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

describe("BlocksRowCount", () => {
	it("renders total count when there is no selected values", async () => {
		// ------------ Setup
		await waitFor(() =>
			render(
				<BlocksRowCountRouter
					count={101}
					setRowSelection={vi.fn()}
					rowSelection={{}}
				/>,
				{ wrapper: createWrapper() },
			),
		);
		// ------------ Assert
		expect(screen.getByText("101 Blocks")).toBeVisible();
	});

	it("able to delete selected rows", async () => {
		const user = userEvent.setup();
		const mockSetRowSelection = vi.fn();
		// ------------ Setup
		await waitFor(() =>
			render(
				<>
					<Toaster />
					<BlocksRowCountRouter
						count={1}
						setRowSelection={mockSetRowSelection}
						rowSelection={{ "1": true, "2": true }}
					/>
				</>,
				{ wrapper: createWrapper() },
			),
		);

		// ------------ Act
		expect(screen.getByText("2 selected")).toBeVisible();
		await user.click(screen.getByRole("button", { name: /Delete rows/i }));
		expect(
			screen.getByText(
				"Are you sure you want to delete these 2 selected blocks?",
			),
		).toBeVisible();
		await user.click(screen.getByRole("button", { name: /Delete/i }));

		// ------------ Assert
		await waitFor(() =>
			expect(screen.getByText(/blocks deleted/i)).toBeVisible(),
		);
		expect(mockSetRowSelection).toHaveBeenLastCalledWith({});
	});
});
