import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createContext, type ReactNode, useContext } from "react";
import { describe, expect, it, vi } from "vitest";
import { BLOCK_TYPES } from "@/mocks";
import { BlocksCatalogPage } from "./blocks-catalog-page";

const TestChildrenContext = createContext<ReactNode>(null);

function RenderTestChildren() {
	const children = useContext(TestChildrenContext);
	return (
		<>
			{children}
			<Outlet />
		</>
	);
}

const renderWithProviders = async (ui: ReactNode) => {
	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				retry: false,
			},
		},
	});

	const rootRoute = createRootRoute({
		component: RenderTestChildren,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	const result = render(
		<QueryClientProvider client={queryClient}>
			<TestChildrenContext.Provider value={ui}>
				<RouterProvider router={router} />
			</TestChildrenContext.Provider>
		</QueryClientProvider>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

describe("BlocksCatalogPage", () => {
	it("renders block type cards when block types are provided", async () => {
		await renderWithProviders(
			<BlocksCatalogPage
				blockTypes={BLOCK_TYPES}
				search=""
				onSearch={vi.fn()}
				onClearFilters={vi.fn()}
			/>,
		);

		expect(screen.getByText("Catalog")).toBeVisible();
		expect(screen.getByPlaceholderText("Search blocks")).toBeVisible();
		expect(
			screen.getByText(`${BLOCK_TYPES.length.toLocaleString()} Blocks`),
		).toBeVisible();
	});

	it("renders empty state when search yields no results", async () => {
		await renderWithProviders(
			<BlocksCatalogPage
				blockTypes={[]}
				search="nonexistent"
				onSearch={vi.fn()}
				onClearFilters={vi.fn()}
			/>,
		);

		expect(screen.getByText("No block types match your search")).toBeVisible();
		expect(screen.getByText("Try adjusting your search terms.")).toBeVisible();
		expect(screen.getByRole("button", { name: "Clear filters" })).toBeVisible();
	});

	it("calls onClearFilters when clear filters button is clicked", async () => {
		const user = userEvent.setup();
		const onClearFilters = vi.fn();

		await renderWithProviders(
			<BlocksCatalogPage
				blockTypes={[]}
				search="nonexistent"
				onSearch={vi.fn()}
				onClearFilters={onClearFilters}
			/>,
		);

		await user.click(screen.getByRole("button", { name: "Clear filters" }));
		expect(onClearFilters).toHaveBeenCalledOnce();
	});

	it("does not render empty state when block types exist", async () => {
		await renderWithProviders(
			<BlocksCatalogPage
				blockTypes={BLOCK_TYPES}
				search=""
				onSearch={vi.fn()}
				onClearFilters={vi.fn()}
			/>,
		);

		expect(
			screen.queryByText("No block types match your search"),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "Clear filters" }),
		).not.toBeInTheDocument();
	});

	it("does not render filtered empty state when no search is active", async () => {
		await renderWithProviders(
			<BlocksCatalogPage
				blockTypes={[]}
				search=""
				onSearch={vi.fn()}
				onClearFilters={vi.fn()}
			/>,
		);

		expect(
			screen.queryByText("No block types match your search"),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "Clear filters" }),
		).not.toBeInTheDocument();
	});
});
