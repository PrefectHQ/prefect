import "./mocks";
import { render, screen } from "@testing-library/react";
import { VariablesPage } from "@/components/variables/page";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { server } from "../mocks/node";
import { HttpResponse } from "msw";
import { http } from "msw";

describe("Variables page", () => {
	it("should render with empty state", () => {
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);
		expect(screen.getByText("Variables")).toBeVisible();
		expect(screen.getByText("Add a variable to get started")).toBeVisible();
		expect(screen.getByRole("button", { name: "Add Variable" })).toBeVisible();
	});

	it("should allow opening and closing the add variable dialog", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);

		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		expect(screen.queryByRole("dialog")).toBeVisible();
		// Get the footer close button for the dialog
		const closeButtons = screen.getByRole("button", {
			name: "Close",
			expanded: true,
		});
		await user.click(closeButtons);
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
	});

	it("should clear inputs when dialog is closed", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);

		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		await user.type(screen.getByLabelText("Name"), "my-variable");
		await userEvent.type(screen.getByTestId("mock-codemirror"), "123");
		await user.click(
			screen.getByRole("button", { name: "Close", expanded: true }),
		);
		await user.click(screen.getByRole("button", { name: "Add Variable" }));

		expect(screen.getByLabelText("Name")).toHaveValue("");
		expect(screen.getByTestId("mock-codemirror")).toHaveValue("");
	});

	it("should allow adding a variable", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
				<Toaster />
			</QueryClientProvider>,
		);

		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		expect(screen.getByText("New Variable")).toBeVisible();
		await user.type(screen.getByLabelText("Name"), "my-variable");
		await userEvent.type(screen.getByTestId("mock-codemirror"), "123");
		await userEvent.type(screen.getByLabelText("Tags"), "tag1");
		await user.click(screen.getByRole("button", { name: "Create" }));

		expect(screen.getByText("Variable created")).toBeVisible();
	});

	it("should show validation errors", async () => {
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);

		// Name validation error
		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		await user.click(screen.getByRole("button", { name: "Create" }));
		expect(
			screen.getByText("Name must be at least 2 characters"),
		).toBeVisible();

		// Value validation error
		await user.type(screen.getByLabelText("Name"), "my-variable");
		await userEvent.type(
			screen.getByTestId("mock-codemirror"),
			"{{Invalid JSON",
		);
		await user.click(screen.getByRole("button", { name: "Create" }));
		expect(screen.getByText("Value must be valid JSON")).toBeVisible();
	});

	it("should show error when API call fails with detail", async () => {
		server.use(
			http.post("http://localhost:4200/api/variables/", () => {
				return HttpResponse.json(
					{ detail: "Failed to create variable" },
					{ status: 500 },
				);
			}),
		);
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);

		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		await user.type(screen.getByLabelText("Name"), "my-variable");
		await userEvent.type(screen.getByTestId("mock-codemirror"), "123");
		await user.click(screen.getByRole("button", { name: "Create" }));
		expect(screen.getByText("Failed to create variable")).toBeVisible();
	});

	it("should show error when API call fails without detail", async () => {
		server.use(
			http.post("http://localhost:4200/api/variables/", () => {
				return HttpResponse.json(
					{ error: "Internal server error" },
					{ status: 500 },
				);
			}),
		);
		const user = userEvent.setup();
		const queryClient = new QueryClient();
		render(
			<QueryClientProvider client={queryClient}>
				<VariablesPage />
			</QueryClientProvider>,
		);

		await user.click(screen.getByRole("button", { name: "Add Variable" }));
		await user.type(screen.getByLabelText("Name"), "my-variable");
		await userEvent.type(screen.getByTestId("mock-codemirror"), "123");
		await user.click(screen.getByRole("button", { name: "Create" }));

		expect(
			screen.getByText("Unknown error", {
				exact: false,
			}),
		).toBeVisible();
	});
});
