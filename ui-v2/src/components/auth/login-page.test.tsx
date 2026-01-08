import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./login-page";

const mockLogin = vi.fn();
const mockNavigate = vi.fn();

vi.mock("@/auth", () => ({
	useAuth: () => ({
		login: mockLogin,
	}),
}));

vi.mock("@tanstack/react-router", () => ({
	useNavigate: () => mockNavigate,
}));

describe("LoginPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders the login form with Prefect logo", () => {
		render(<LoginPage />, { wrapper: createWrapper() });

		expect(screen.getByLabelText(/prefect logo/i)).toBeVisible();
		expect(screen.getByPlaceholderText("admin:pass")).toBeVisible();
		expect(screen.getByRole("button", { name: /login/i })).toBeVisible();
	});

	it("allows entering a password", async () => {
		const user = userEvent.setup();
		render(<LoginPage />, { wrapper: createWrapper() });

		const passwordInput = screen.getByPlaceholderText("admin:pass");
		await user.type(passwordInput, "test-password");

		expect(passwordInput).toHaveValue("test-password");
	});

	it("calls login and navigates on successful submission", async () => {
		const user = userEvent.setup();
		mockLogin.mockResolvedValueOnce({ success: true });

		render(<LoginPage />, { wrapper: createWrapper() });

		await user.type(screen.getByPlaceholderText("admin:pass"), "test-password");
		await user.click(screen.getByRole("button", { name: /login/i }));

		await waitFor(() => {
			expect(mockLogin).toHaveBeenCalledWith("test-password");
		});

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({ to: "/dashboard" });
		});
	});

	it("navigates to custom redirectTo on successful login", async () => {
		const user = userEvent.setup();
		mockLogin.mockResolvedValueOnce({ success: true });

		render(<LoginPage redirectTo="/flows" />, { wrapper: createWrapper() });

		await user.type(screen.getByPlaceholderText("admin:pass"), "test-password");
		await user.click(screen.getByRole("button", { name: /login/i }));

		await waitFor(() => {
			expect(mockNavigate).toHaveBeenCalledWith({ to: "/flows" });
		});
	});

	it("displays error message on failed login", async () => {
		const user = userEvent.setup();
		mockLogin.mockResolvedValueOnce({
			success: false,
			error: "Invalid credentials",
		});

		render(<LoginPage />, { wrapper: createWrapper() });

		await user.type(
			screen.getByPlaceholderText("admin:pass"),
			"wrong-password",
		);
		await user.click(screen.getByRole("button", { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByText("Invalid credentials")).toBeVisible();
		});
	});

	it("displays default error message when no error provided", async () => {
		const user = userEvent.setup();
		mockLogin.mockResolvedValueOnce({ success: false });

		render(<LoginPage />, { wrapper: createWrapper() });

		await user.type(
			screen.getByPlaceholderText("admin:pass"),
			"wrong-password",
		);
		await user.click(screen.getByRole("button", { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByText("Authentication failed")).toBeVisible();
		});
	});

	it("disables form while submitting", async () => {
		const user = userEvent.setup();
		let resolveLogin: (value: { success: boolean }) => void;
		mockLogin.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveLogin = resolve;
			}),
		);

		render(<LoginPage />, { wrapper: createWrapper() });

		await user.type(screen.getByPlaceholderText("admin:pass"), "test-password");
		await user.click(screen.getByRole("button", { name: /login/i }));

		await waitFor(() => {
			expect(screen.getByPlaceholderText("admin:pass")).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /logging in/i }),
			).toBeDisabled();
		});

		resolveLogin?.({ success: true });
	});

	it("does not submit with empty password", async () => {
		const user = userEvent.setup();
		render(<LoginPage />, { wrapper: createWrapper() });

		await user.click(screen.getByRole("button", { name: /login/i }));

		expect(mockLogin).not.toHaveBeenCalled();
	});

	it("does not submit with whitespace-only password", async () => {
		const user = userEvent.setup();
		render(<LoginPage />, { wrapper: createWrapper() });

		await user.type(screen.getByPlaceholderText("admin:pass"), "   ");
		await user.click(screen.getByRole("button", { name: /login/i }));

		expect(mockLogin).not.toHaveBeenCalled();
	});
});
