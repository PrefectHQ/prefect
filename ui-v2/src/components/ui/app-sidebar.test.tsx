import { QueryClient } from "@tanstack/react-query";
import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { delay, HttpResponse, http } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthState } from "@/auth";
import { SidebarProvider } from "@/components/ui/sidebar";
import * as uiVersionSwitch from "@/components/ui-version-switch";
import { createFakeServerSettings } from "@/mocks";
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
	afterEach(() => {
		vi.restoreAllMocks();
	});

	describe("ui switching", () => {
		it("renders the switch-back action when the current UI is available", async () => {
			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Switch back to current UI")).toBeTruthy();
			});
		});

		it("hides the switch-back action when the current UI is unavailable", async () => {
			server.use(
				http.get(/\/ui-settings$/, () => {
					return HttpResponse.json({
						api_url: "http://localhost:4200/api",
						csrf_enabled: false,
						auth: null,
						flags: [],
						default_ui: "v2",
						available_uis: ["v2"],
						v1_base_url: null,
						v2_base_url: "/v2",
					});
				}),
			);

			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Dashboard")).toBeTruthy();
			});

			expect(screen.queryByText("Switch back to current UI")).toBeNull();
		});

		it("keeps analytics disabled until server settings have loaded", async () => {
			const user = userEvent.setup();
			const switchToV1UiSpy = vi
				.spyOn(uiVersionSwitch, "switchToV1Ui")
				.mockReturnValue("/");
			const baseSettings = createFakeServerSettings() as Record<string, unknown>;
			const serverSettings = {
				...baseSettings,
				server: {
					...(baseSettings.server as Record<string, unknown>),
					analytics_enabled: false,
				},
			};

			server.use(
				http.get(buildApiUrl("/admin/settings"), async () => {
					await delay(500);
					return HttpResponse.json(serverSettings);
				}),
			);

			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Switch back to current UI")).toBeTruthy();
			});

			await user.click(screen.getByText("Switch back to current UI"));
			await user.click(screen.getByText("Skip feedback and switch"));

			expect(switchToV1UiSpy).toHaveBeenCalledWith(
				expect.objectContaining({
					analyticsEnabled: false,
				}),
			);
		});
	});

	describe("promotional content", () => {
		it("renders promotional items when show_promotional_content is true", async () => {
			const mockSettings = createFakeServerSettings();
			server.use(
				http.get(buildApiUrl("/admin/settings"), () => {
					return HttpResponse.json(mockSettings);
				}),
			);

			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Ready to scale?")).toBeTruthy();
			});

			expect(screen.getByText("Join the community")).toBeTruthy();
		});

		it("hides promotional items when show_promotional_content is false", async () => {
			const mockSettings = createFakeServerSettings({
				server: {
					...(createFakeServerSettings().server as Record<string, unknown>),
					ui: {
						enabled: true,
						api_url: "http://127.0.0.1:4200/api",
						serve_base: "/",
						static_directory: null,
						show_promotional_content: false,
					},
				},
			});
			server.use(
				http.get(buildApiUrl("/admin/settings"), () => {
					return HttpResponse.json(mockSettings);
				}),
			);

			const router = createTestRouter(null);

			render(<RouterProvider router={router} />, {
				wrapper: createWrapper(),
			});

			await waitFor(() => {
				expect(screen.getByText("Dashboard")).toBeTruthy();
				expect(screen.queryByText("Ready to scale?")).toBeNull();
			});

			expect(screen.queryByText("Join the community")).toBeNull();
		});
	});

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
