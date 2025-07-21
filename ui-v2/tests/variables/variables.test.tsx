import { Toaster } from "@/components/ui/sonner";
import { VariablesDataTable } from "@/components/variables/data-table";
import "@/mocks/mock-json-input";
import { RouterProvider } from "@tanstack/react-router";
import {
	getByLabelText,
	getByTestId,
	getByText,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import {
	afterEach,
	beforeAll,
	beforeEach,
	describe,
	expect,
	it,
	vi,
} from "vitest";
import { router } from "@/router";

const renderVariablesPage = async () => {
	const user = userEvent.setup();
	// Render with router provider
	const result = await waitFor(() =>
		render(<RouterProvider router={router} />, {
			wrapper: createWrapper(),
		}),
	);
	await user.click(screen.getByRole("link", { name: "Variables" }));
	return result;
};

describe("Variables page", () => {
	it("should render with empty state", async () => {
		await renderVariablesPage();
		expect(screen.getByText("Add a variable to get started")).toBeVisible();
		expect(screen.getByRole("button", { name: "Add Variable" })).toBeVisible();
	});

	describe("Add variable dialog", () => {
		it("should allow opening and closing the add variable dialog", async () => {
			const user = userEvent.setup();
			await renderVariablesPage();

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
			await renderVariablesPage();

			await user.click(screen.getByRole("button", { name: "Add Variable" }));
			await user.type(screen.getByLabelText("Name"), "my-variable");
			await userEvent.type(screen.getByTestId("mock-json-input"), "123");
			await user.click(
				screen.getByRole("button", { name: "Close", expanded: true }),
			);
			await user.click(screen.getByRole("button", { name: "Add Variable" }));

			expect(screen.getByLabelText("Name")).toHaveValue("");
			expect(screen.getByTestId("mock-json-input")).toHaveValue("");
		});

		it("should allow adding a variable", async () => {
			const user = userEvent.setup();
			await renderVariablesPage();

			await user.click(screen.getByRole("button", { name: "Add Variable" }));
			expect(screen.getByRole("dialog")).toBeVisible();
			await user.type(screen.getByLabelText("Name"), "my-variable");
			await userEvent.type(screen.getByTestId("mock-json-input"), "123");
			await userEvent.type(screen.getByLabelText("Tags"), "tag1");
			await user.click(screen.getByRole("button", { name: "Create" }));
			await waitFor(() => {
				expect(screen.getByText("Variable created")).toBeVisible();
				expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
			});
		});

		it("should show validation errors", async () => {
			const user = userEvent.setup();
			await renderVariablesPage();

			// Name validation error
			await user.click(screen.getByRole("button", { name: "Add Variable" }));
			await user.click(screen.getByRole("button", { name: "Create" }));
			expect(
				screen.getByText("Name must be at least 2 characters"),
			).toBeVisible();

			// Value validation error
			await user.type(screen.getByLabelText("Name"), "my-variable");
			await userEvent.type(
				screen.getByTestId("mock-json-input"),
				"{{Invalid JSON",
			);
			await user.click(screen.getByRole("button", { name: "Create" }));
			expect(screen.getByText("Value must be valid JSON")).toBeVisible();
		});

		it("should show error when API call fails with detail", async () => {
			server.use(
				http.post(buildApiUrl("/variables/"), () => {
					return HttpResponse.json(
						{ detail: "Failed to create variable" },
						{ status: 500 },
					);
				}),
			);
			const user = userEvent.setup();
			await renderVariablesPage();

			await user.click(screen.getByRole("button", { name: "Add Variable" }));
			await user.type(screen.getByLabelText("Name"), "my-variable");
			await userEvent.type(screen.getByTestId("mock-json-input"), "123");
			await user.click(screen.getByRole("button", { name: "Create" }));
			expect(screen.getByText("Failed to create variable")).toBeVisible();
		});

		it("should show error when API call fails without detail", async () => {
			server.use(
				http.post(buildApiUrl("/variables/"), () => {
					return HttpResponse.json(
						{ error: "Internal server error" },
						{ status: 500 },
					);
				}),
			);
			const user = userEvent.setup();
			await renderVariablesPage();

			await user.click(screen.getByRole("button", { name: "Add Variable" }));
			await user.type(screen.getByLabelText("Name"), "my-variable");
			await userEvent.type(screen.getByTestId("mock-json-input"), "123");
			await user.click(screen.getByRole("button", { name: "Create" }));

			expect(
				screen.getByText("Unknown error", {
					exact: false,
				}),
			).toBeVisible();
		});
	});

	describe("Edit variable dialog", () => {
		it("should allow editing a variable", async () => {
			const user = userEvent.setup();

			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			server.use(
				http.post(buildApiUrl("/variables/filter"), () => {
					return HttpResponse.json(variables);
				}),
				http.post(buildApiUrl("/variables/count"), () => {
					return HttpResponse.json(1);
				}),
			);

			await renderVariablesPage();

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Edit"));
			expect(screen.getByText("Edit Variable")).toBeVisible();

			const dialog = screen.getByRole("dialog");
			expect(getByLabelText(dialog, "Name")).toHaveValue("my-variable");
			expect(getByTestId(dialog, "mock-json-input")).toHaveValue("123");
			expect(getByText(dialog, "tag1")).toBeVisible();

			await user.type(getByLabelText(dialog, "Name"), "new_name");
			await user.click(screen.getByRole("button", { name: "Save" }));
			await waitFor(() => {
				expect(screen.getByText("Variable updated")).toBeVisible();
			});
		});

		it("should show an error when API call fails with detail", async () => {
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			server.use(
				http.patch(buildApiUrl("/variables/:id"), () => {
					return HttpResponse.json(
						{ detail: "Failed to update variable. Here's some detail..." },
						{ status: 500 },
					);
				}),
				http.post(buildApiUrl("/variables/filter"), () => {
					return HttpResponse.json(variables);
				}),
				http.post(buildApiUrl("/variables/count"), () => {
					return HttpResponse.json(1);
				}),
			);
			const user = userEvent.setup();

			await renderVariablesPage();

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Edit"));
			expect(screen.getByText("Edit Variable")).toBeVisible();

			const dialog = screen.getByRole("dialog");
			expect(getByLabelText(dialog, "Name")).toHaveValue("my-variable");

			await user.type(getByLabelText(dialog, "Name"), "new_name");
			await user.click(screen.getByRole("button", { name: "Save" }));
			expect(
				screen.getByText("Failed to update variable. Here's some detail..."),
			).toBeVisible();
		});
	});

	it("should show an error when API call fails without detail", async () => {
		const variables = [
			{
				id: "1",
				name: "my-variable",
				value: 123,
				created: "2021-01-01T00:00:00Z",
				updated: "2021-01-01T00:00:00Z",
				tags: ["tag1"],
			},
		];
		server.use(
			http.patch(buildApiUrl("/variables/:id"), () => {
				return HttpResponse.json(
					{ error: "Internal server error" },
					{ status: 500 },
				);
			}),
			http.post(buildApiUrl("/variables/filter"), () => {
				return HttpResponse.json(variables);
			}),
			http.post(buildApiUrl("/variables/count"), () => {
				return HttpResponse.json(1);
			}),
		);
		const user = userEvent.setup();

		await renderVariablesPage();

		await user.click(screen.getByRole("button", { expanded: false }));
		await user.click(screen.getByText("Edit"));

		const dialog = screen.getByRole("dialog");
		expect(getByLabelText(dialog, "Name")).toHaveValue("my-variable");

		await user.type(getByLabelText(dialog, "Name"), "new_name");
		await user.click(screen.getByRole("button", { name: "Save" }));
		expect(screen.getByText("Unknown error", { exact: false })).toBeVisible();
	});

	describe("Variables table", () => {
		beforeAll(() => {
			mockPointerEvents();
		});
		const originalToLocaleString = Date.prototype.toLocaleString; // eslint-disable-line @typescript-eslint/unbound-method
		beforeEach(() => {
			// Mock toLocaleString to simulate specific timezone
			Date.prototype.toLocaleString = function (
				locale?: string | string[],
				options?: Intl.DateTimeFormatOptions,
			) {
				return originalToLocaleString.call(this, locale, {
					...options,
					timeZone: "UTC",
				});
			};
		});
		afterEach(() => {
			Date.prototype.toLocaleString = originalToLocaleString;
		});

		it("should render provided variables", () => {
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
				{
					id: "2",
					name: "my-variable-2",
					value: "foo",
					created: "2022-02-02T00:00:00Z",
					updated: "2022-02-02T00:00:00Z",
					tags: ["tag2"],
				},
			];
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={2}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);
			expect(screen.getByText("2 Variables")).toBeVisible();
			// Table headers
			expect(screen.getByText("Name")).toBeVisible();
			expect(screen.getByText("Value")).toBeVisible();
			expect(screen.getByText("Updated")).toBeVisible();

			// Variable 1
			expect(screen.getByText("my-variable")).toBeVisible();
			expect(screen.getByText("tag1")).toBeVisible();
			expect(screen.getByText("123")).toBeVisible();
			expect(screen.getByText("1/1/2021 12:00:00 AM")).toBeVisible();

			// Variable 2
			expect(screen.getByText("my-variable-2")).toBeVisible();
			expect(screen.getByText("tag2")).toBeVisible();
			expect(screen.getByText('"foo"')).toBeVisible();
			expect(screen.getByText("2/2/2022 12:00:00 AM")).toBeVisible();
		});

		it("should render pagination controls", async () => {
			const variables = Array.from({ length: 20 }, (_, i) => ({
				id: `${i + 1}`,
				name: `variable-${i + 1}`,
				value: i % 2 === 0 ? i * 100 : `value-${i + 1}`,
				created: `2023-${(i % 12) + 1}-01T00:00:00Z`,
				updated: `2023-${(i % 12) + 1}-01T00:00:00Z`,
				tags: [`tag-${i + 1}`],
			}));
			const onPaginationChange = vi.fn();
			const user = userEvent.setup();
			const { rerender } = render(
				<VariablesDataTable
					variables={variables.slice(0, 10)}
					currentVariableCount={20}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={onPaginationChange}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);
			expect(screen.getByText("20 Variables")).toBeVisible();

			expect(screen.getByText("Page 1 of 2")).toBeVisible();
			expect(screen.getByLabelText("Go to first page")).toBeDisabled();
			expect(screen.getByLabelText("Go to previous page")).toBeDisabled();
			expect(screen.getByLabelText("Go to next page")).toBeEnabled();
			expect(screen.getByLabelText("Go to last page")).toBeEnabled();

			await user.click(screen.getByLabelText("Go to next page"));
			expect(onPaginationChange).toHaveBeenCalled();

			await user.click(screen.getByLabelText("Go to last page"));
			expect(onPaginationChange).toHaveBeenCalled();

			rerender(
				<VariablesDataTable
					variables={variables.slice(10, 20)}
					currentVariableCount={20}
					pagination={{ pageIndex: 1, pageSize: 10 }}
					onPaginationChange={onPaginationChange}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
			);

			expect(screen.getByText("Page 2 of 2")).toBeVisible();
			expect(screen.getByLabelText("Go to first page")).toBeEnabled();
			expect(screen.getByLabelText("Go to previous page")).toBeEnabled();
			expect(screen.getByLabelText("Go to next page")).toBeDisabled();
			expect(screen.getByLabelText("Go to last page")).toBeDisabled();

			await user.click(screen.getByLabelText("Go to first page"));
			expect(onPaginationChange).toHaveBeenCalled();

			await user.click(screen.getByLabelText("Go to previous page"));
			expect(onPaginationChange).toHaveBeenCalled();
		});

		it("should allow variable ID to be copied to clipboard", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Copy ID"));
			expect(await navigator.clipboard.readText()).toBe("1");
		});

		it("should allow variable name to be copied to clipboard", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Copy Name"));
			expect(await navigator.clipboard.readText()).toBe("my-variable");
		});

		it("should allow variable value to be copied to clipboard", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Copy Value"));
			expect(await navigator.clipboard.readText()).toBe("123");
		});

		it("should allow a variable to be deleted", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			render(
				<>
					<Toaster />
					<VariablesDataTable
						variables={variables}
						currentVariableCount={1}
						pagination={{ pageIndex: 0, pageSize: 10 }}
						onPaginationChange={vi.fn()}
						columnFilters={[]}
						onColumnFiltersChange={vi.fn()}
						sorting="CREATED_DESC"
						onSortingChange={vi.fn()}
						onVariableEdit={vi.fn()}
					/>
				</>,
				{ wrapper: createWrapper() },
			);

			await user.click(screen.getByRole("button", { expanded: false }));
			await user.click(screen.getByText("Delete"));
			await waitFor(() => {
				expect(screen.getByText("Variable deleted")).toBeVisible();
			});
		});

		it("should handle filtering by name", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			const onColumnFiltersChange = vi.fn();
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[{ id: "name", value: "start value" }]}
					onColumnFiltersChange={onColumnFiltersChange}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			// Clear any initial calls from mounting
			onColumnFiltersChange.mockClear();

			const nameSearchInput = screen.getByPlaceholderText("Search variables");
			expect(nameSearchInput).toHaveValue("start value");

			await user.clear(nameSearchInput);
			await user.type(nameSearchInput, "my-variable");

			expect(onColumnFiltersChange).toHaveBeenCalledWith([
				{ id: "name", value: "my-variable" },
			]);
		});

		it("should handle filtering by tags", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];

			const onColumnFiltersChange = vi.fn();
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[{ id: "tags", value: ["tag2"] }]}
					onColumnFiltersChange={onColumnFiltersChange}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			// Clear any initial calls from mounting
			onColumnFiltersChange.mockClear();

			const tagsSearchInput = screen.getByPlaceholderText("Filter by tags");
			expect(await screen.findByText("tag2")).toBeVisible();

			await user.type(tagsSearchInput, "tag1");
			await user.keyboard("{enter}");

			expect(onColumnFiltersChange).toHaveBeenCalledWith([
				{ id: "tags", value: ["tag2", "tag1"] },
			]);
		});

		it("should handle sorting", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];

			const onSortingChange = vi.fn();
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={vi.fn()}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={onSortingChange}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			const select = screen.getByLabelText("Variable sort order");
			expect(screen.getByText("Created")).toBeVisible();

			await user.click(select);
			await user.click(screen.getByText("A to Z"));
			expect(onSortingChange).toHaveBeenCalledWith("NAME_ASC");

			await user.click(select);
			await user.click(screen.getByText("Z to A"));
			expect(onSortingChange).toHaveBeenCalledWith("NAME_DESC");
		});

		it("should emit when updating items per page", async () => {
			const user = userEvent.setup();
			const variables = [
				{
					id: "1",
					name: "my-variable",
					value: 123,
					created: "2021-01-01T00:00:00Z",
					updated: "2021-01-01T00:00:00Z",
					tags: ["tag1"],
				},
			];
			const onPaginationChange = vi.fn();
			render(
				<VariablesDataTable
					variables={variables}
					currentVariableCount={1}
					pagination={{ pageIndex: 0, pageSize: 10 }}
					onPaginationChange={onPaginationChange}
					columnFilters={[]}
					onColumnFiltersChange={vi.fn()}
					sorting="CREATED_DESC"
					onSortingChange={vi.fn()}
					onVariableEdit={vi.fn()}
				/>,
				{ wrapper: createWrapper() },
			);

			const select = screen.getByLabelText("Items per page");
			expect(screen.getByText("10")).toBeVisible();

			await user.click(select);
			await user.click(screen.getByText("25"));

			expect(onPaginationChange).toHaveBeenCalledWith({
				pageIndex: 0,
				pageSize: 25,
			});
		});
	});
});
