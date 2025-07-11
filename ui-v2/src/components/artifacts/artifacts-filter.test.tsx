import { fireEvent, render, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFakeArtifact } from "@/mocks";
import { ArtifactsFilterComponent } from "./artifacts-filter";

describe("Artifacts Filter", () => {
	const defaultCount = 2;
	const defaultArtifacts = Array.from(
		{ length: defaultCount },
		createFakeArtifact,
	);
	const defaultFilters = [
		{ id: "type", label: "Type", value: "all" },
		{ id: "name", label: "Name", value: "" },
	];

	beforeEach(() => {
		server.use(
			http.post(buildApiUrl("/artifacts/filter"), () => {
				return HttpResponse.json(defaultArtifacts);
			}),
		);
	});

	it("renders filter components", () => {
		const onFilterChange = vi.fn();
		const { findByTestId, findByText } = render(
			<ArtifactsFilterComponent
				filters={defaultFilters}
				onFilterChange={onFilterChange}
				totalCount={defaultCount}
				setDisplayMode={vi.fn()}
				displayMode="grid"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		expect(findByText(`${defaultCount} artifacts`)).toBeTruthy();
		expect(findByTestId("search-input")).toBeTruthy();
		expect(findByText("All Types")).toBeTruthy();
	});

	it("changes artifact name filter", async () => {
		const onFilterChange = vi.fn();
		const { findByTestId } = render(
			<ArtifactsFilterComponent
				filters={defaultFilters}
				onFilterChange={onFilterChange}
				totalCount={defaultCount}
				setDisplayMode={vi.fn()}
				displayMode="grid"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		const searchInput = await findByTestId("search-input");
		fireEvent.change(searchInput, { target: { value: "test" } });

		// needed for debounce
		await waitFor(() => {
			expect(onFilterChange).toHaveBeenCalledWith([
				{ id: "type", label: "Type", value: "all" },
				{ id: "name", label: "Name", value: "test" },
			]);
		});
	});

	it("changes artifact type filter", () => {
		const onFilterChange = vi.fn();
		const screen = render(
			<ArtifactsFilterComponent
				filters={defaultFilters}
				onFilterChange={onFilterChange}
				totalCount={defaultCount}
				setDisplayMode={vi.fn()}
				displayMode="grid"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		fireEvent.click(screen.getByText("All Types"));
		fireEvent.click(screen.getByText("Markdown"));

		expect(onFilterChange).toHaveBeenCalledWith([
			{ id: "name", label: "Name", value: "" },
			{ id: "type", label: "Type", value: "markdown" },
		]);
	});

	it("changes display mode", () => {
		const setDisplayMode = vi.fn();
		const { getByTestId } = render(
			<ArtifactsFilterComponent
				filters={defaultFilters}
				onFilterChange={vi.fn()}
				totalCount={defaultCount}
				setDisplayMode={setDisplayMode}
				displayMode="grid"
			/>,
			{
				wrapper: createWrapper(),
			},
		);

		fireEvent.click(getByTestId("list-layout"));
		expect(setDisplayMode).toHaveBeenCalledWith("list");
	});
});
