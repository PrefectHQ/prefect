import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TagsFilter } from "./tags-filter";

beforeAll(() => {
	Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
		value: vi.fn(),
		configurable: true,
		writable: true,
	});
});

function renderWithQueryClient(ui: React.ReactElement) {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(
		<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
	);
}

describe("TagsFilter", () => {
	const TestTagsFilter = ({
		initialSelectedTags = new Set<string>(),
	}: {
		initialSelectedTags?: Set<string>;
	}) => {
		const [selectedTags, setSelectedTags] =
			useState<Set<string>>(initialSelectedTags);
		return (
			<TagsFilter selectedTags={selectedTags} onSelectTags={setSelectedTags} />
		);
	};

	it("renders with 'All tags' when no tags are selected", () => {
		renderWithQueryClient(<TestTagsFilter />);

		expect(
			screen.getByRole("button", { name: /filter by tag/i }),
		).toBeVisible();
		expect(screen.getByText("All tags")).toBeVisible();
	});

	it("opens dropdown and shows 'All tags' option", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});

		expect(screen.getByRole("option", { name: /all tags/i })).toBeVisible();
	});

	it("shows search input in dropdown", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});
	});

	it("has 'All tags' checkbox checked by default", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(screen.getByRole("option", { name: /all tags/i })).toBeVisible();
		});

		const allTagsOption = screen.getByRole("option", { name: /all tags/i });
		const allTagsCheckbox = allTagsOption.querySelector('[role="checkbox"]');
		expect(allTagsCheckbox).toHaveAttribute("data-state", "checked");
	});

	it("allows selecting a tag from suggestions", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [
						{ id: "1", name: "Flow Run 1", tags: ["production", "critical"] },
						{ id: "2", name: "Flow Run 2", tags: ["staging", "production"] },
					],
					count: 2,
					pages: 1,
					page: 1,
					limit: 100,
				});
			}),
		);

		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(screen.getByRole("option", { name: "production" })).toBeVisible();
		});

		await user.click(screen.getByRole("option", { name: "production" }));

		const productionOption = screen.getByRole("option", {
			name: "production",
		});
		const checkbox = productionOption.querySelector('[role="checkbox"]');
		expect(checkbox).toHaveAttribute("data-state", "checked");
	});

	it("allows adding freeform tag via Enter key", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});

		const input = screen.getByPlaceholderText("Search or enter new tag");
		await user.type(input, "my-new-tag");

		await waitFor(() => {
			expect(screen.getByText(/Add "my-new-tag"/)).toBeVisible();
		});

		await user.keyboard("{Enter}");

		await waitFor(() => {
			const selectedOption = screen.getByRole("option", {
				name: "my-new-tag",
			});
			const checkbox = selectedOption.querySelector('[role="checkbox"]');
			expect(checkbox).toHaveAttribute("data-state", "checked");
		});
	});

	it("allows adding freeform tag via comma trigger", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});

		const input = screen.getByPlaceholderText("Search or enter new tag");
		await user.type(input, "comma-tag,");

		await waitFor(() => {
			const selectedOption = screen.getByRole("option", {
				name: "comma-tag",
			});
			const checkbox = selectedOption.querySelector('[role="checkbox"]');
			expect(checkbox).toHaveAttribute("data-state", "checked");
		});
	});

	it("clears all tags when 'All tags' is selected", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(
			<TestTagsFilter initialSelectedTags={new Set(["tag1", "tag2"])} />,
		);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(screen.getByRole("option", { name: /all tags/i })).toBeVisible();
		});

		await user.click(screen.getByRole("option", { name: /all tags/i }));

		const allTagsOption = screen.getByRole("option", { name: /all tags/i });
		const allTagsCheckbox = allTagsOption.querySelector('[role="checkbox"]');
		expect(allTagsCheckbox).toHaveAttribute("data-state", "checked");
	});

	it("displays truncated tags with '+ N' pattern for more than 2 selected tags", () => {
		renderWithQueryClient(
			<TestTagsFilter
				initialSelectedTags={new Set(["tag1", "tag2", "tag3", "tag4"])}
			/>,
		);

		expect(screen.getByText("4 tags")).toBeVisible();
	});

	it("handles special characters in tag names", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});

		const input = screen.getByPlaceholderText("Search or enter new tag");
		await user.type(input, "env:prod space-tag");

		await waitFor(() => {
			expect(screen.getByText(/Add "env:prod space-tag"/)).toBeVisible();
		});

		await user.keyboard("{Enter}");

		await waitFor(() => {
			const selectedOption = screen.getByRole("option", {
				name: "env:prod space-tag",
			});
			const checkbox = selectedOption.querySelector('[role="checkbox"]');
			expect(checkbox).toHaveAttribute("data-state", "checked");
		});
	});

	it("prevents case-insensitive duplicate tags", async () => {
		const user = userEvent.setup();
		renderWithQueryClient(
			<TestTagsFilter initialSelectedTags={new Set(["Production"])} />,
		);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(
				screen.getByPlaceholderText("Search or enter new tag"),
			).toBeVisible();
		});

		const input = screen.getByPlaceholderText("Search or enter new tag");
		await user.type(input, "production");

		await waitFor(() => {
			expect(screen.queryByText(/Add "production"/)).not.toBeInTheDocument();
		});
	});

	it("toggles tag selection off when clicking a selected tag", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [{ id: "1", name: "Flow Run 1", tags: ["test-tag"] }],
					count: 1,
					pages: 1,
					page: 1,
					limit: 100,
				});
			}),
		);

		const user = userEvent.setup();
		renderWithQueryClient(
			<TestTagsFilter initialSelectedTags={new Set(["test-tag"])} />,
		);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(screen.getByRole("option", { name: "test-tag" })).toBeVisible();
		});

		const selectedOption = screen.getByRole("option", { name: "test-tag" });
		const checkbox = selectedOption.querySelector('[role="checkbox"]');
		expect(checkbox).toHaveAttribute("data-state", "checked");

		await user.click(selectedOption);

		await waitFor(() => {
			const allTagsOption = screen.getByRole("option", { name: /all tags/i });
			const allTagsCheckbox = allTagsOption.querySelector('[role="checkbox"]');
			expect(allTagsCheckbox).toHaveAttribute("data-state", "checked");
		});
	});

	it("shows loading skeleton while fetching suggestions", async () => {
		server.use(
			http.post(buildApiUrl("/flow_runs/paginate"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json({
					results: [],
					count: 0,
					pages: 0,
					page: 1,
					limit: 100,
				});
			}),
		);

		const user = userEvent.setup();
		renderWithQueryClient(<TestTagsFilter />);

		await user.click(screen.getByRole("button", { name: /filter by tag/i }));

		await waitFor(() => {
			expect(screen.getByRole("listbox")).toBeVisible();
		});
	});
});
