import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { SavedFilters } from "@/components/saved-filters";

const mockSavedSearches = [
	{
		id: "saved-search-1",
		name: "My Custom Filter",
		filters: [
			{
				object: "flow_run",
				property: "state",
				type: "state",
				operation: "any",
				value: ["Completed"],
			},
		],
		created: "2024-01-01T00:00:00Z",
		updated: "2024-01-01T00:00:00Z",
	},
	{
		id: "saved-search-2",
		name: "Failed runs only",
		filters: [
			{
				object: "flow_run",
				property: "state",
				type: "state",
				operation: "any",
				value: ["Failed"],
			},
		],
		created: "2024-01-02T00:00:00Z",
		updated: "2024-01-02T00:00:00Z",
	},
];

const defaultFilter = {
	state: [],
	flow: [],
	tag: [],
	deployment: [],
	workPool: [],
	workQueue: [],
	range: { type: "span" as const, seconds: -604800 },
};

describe("SavedFilters", () => {
	beforeAll(() => {
		mockPointerEvents();
	});

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/saved_searches/filter"), () => {
				return HttpResponse.json(mockSavedSearches);
			}),
			http.post(buildApiUrl("/flow_runs/paginate"), () => {
				return HttpResponse.json({
					results: [],
					count: 0,
					page: 1,
					pages: 0,
				});
			}),
			http.post(buildApiUrl("/task_runs/paginate"), () => {
				return HttpResponse.json({
					results: [],
					count: 0,
					page: 1,
					pages: 0,
				});
			}),
		);
	});

	it("should render the saved filters dropdown", async () => {
		const onFilterChange = vi.fn();
		render(
			<SavedFilters filter={defaultFilter} onFilterChange={onFilterChange} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeVisible();
		});
	});

	it("should show saved searches in dropdown", async () => {
		const user = userEvent.setup();
		const onFilterChange = vi.fn();
		render(
			<SavedFilters filter={defaultFilter} onFilterChange={onFilterChange} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeVisible();
		});

		await user.click(screen.getByRole("combobox"));

		await waitFor(() => {
			// System saved searches
			expect(screen.getByText("Hide scheduled runs")).toBeVisible();
			// User saved searches from mock
			expect(screen.getByText("My Custom Filter")).toBeVisible();
			expect(screen.getByText("Failed runs only")).toBeVisible();
		});
	});

	it("should call onFilterChange when a saved search is selected", async () => {
		const user = userEvent.setup();
		const onFilterChange = vi.fn();
		render(
			<SavedFilters filter={defaultFilter} onFilterChange={onFilterChange} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeVisible();
		});

		await user.click(screen.getByRole("combobox"));

		await waitFor(() => {
			expect(screen.getByText("Failed runs only")).toBeVisible();
		});

		await user.click(screen.getByText("Failed runs only"));

		await waitFor(() => {
			expect(onFilterChange).toHaveBeenCalled();
		});
	});

	it("should show Custom when filter doesn't match any saved search", async () => {
		const customFilter = {
			...defaultFilter,
			state: ["Running"],
		};
		const onFilterChange = vi.fn();
		render(
			<SavedFilters filter={customFilter} onFilterChange={onFilterChange} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeVisible();
		});

		// The dropdown should show "Custom" or similar when filter doesn't match
		expect(screen.getByRole("combobox")).toHaveTextContent(/custom/i);
	});
});

describe("SavedFilters with empty saved searches", () => {
	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/saved_searches/filter"), () => {
				return HttpResponse.json([]);
			}),
		);
	});

	it("should render with no saved searches", async () => {
		const onFilterChange = vi.fn();
		render(
			<SavedFilters filter={defaultFilter} onFilterChange={onFilterChange} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(screen.getByRole("combobox")).toBeVisible();
		});
	});
});
