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
import { AuthContext, type AuthState } from "@/auth";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "./app-sidebar";

const createTestRouter = (authState: AuthState | null) => {
	const rootRoute = createRootRoute({
		component: () => (
			<AuthContext.Provider value={authState}>
				<SidebarProvider>
					<AppSidebar />
				</SidebarProvider>
			</AuthContext.Provider>
		),
	});

	return createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({
			initialEntries: ["/"],
		}),
		context: { queryClient: new QueryClient() },
	});
};

describe("AppSidebar", () => {
	describe("logout button", () => {
		it("does not render logout button when auth context is null", async () => {
			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Dashboard")).toBeTruthy();
			});

			expect(screen.queryByText("Logout")).toBeNull();
		});

		it("does not render logout button when authRequired is false", async () => {
			const mockAuthState: AuthState = {
				isAuthenticated: true,
				isLoading: false,
				authRequired: false,
				login: vi.fn(),
				logout: vi.fn(),
			};

			const router = createTestRouter(mockAuthState);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Dashboard")).toBeTruthy();
			});

			expect(screen.queryByText("Logout")).toBeNull();
		});

		it("renders logout button when authRequired is true", async () => {
			const mockAuthState: AuthState = {
				isAuthenticated: true,
				isLoading: false,
				authRequired: true,
				login: vi.fn(),
				logout: vi.fn(),
			};

			const router = createTestRouter(mockAuthState);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Logout")).toBeTruthy();
			});
		});

		it("calls logout and navigates to /login when logout button is clicked", async () => {
			const user = userEvent.setup();
			const mockLogout = vi.fn();
			const mockAuthState: AuthState = {
				isAuthenticated: true,
				isLoading: false,
				authRequired: true,
				login: vi.fn(),
				logout: mockLogout,
			};

			const router = createTestRouter(mockAuthState);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Logout")).toBeTruthy();
			});

			const logoutButton = screen.getByText("Logout");
			await user.click(logoutButton);

			expect(mockLogout).toHaveBeenCalledTimes(1);
			expect(router.state.location.pathname).toBe("/login");
		});
	});
});
