import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { SavedFilters, type SavedFiltersFilter } from "./saved-filters";
import { ONE_WEEK_FILTER } from "./saved-filters-utils";

const MOCK_SAVED_SEARCHES = [
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

const meta = {
	title: "Components/SavedFilters/SavedFilters",
	render: () => <SavedFiltersStory />,
	decorators: [routerDecorator, reactQueryDecorator, toastDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/saved_searches/filter"), () => {
					return HttpResponse.json(MOCK_SAVED_SEARCHES);
				}),
				http.put(buildApiUrl("/saved_searches/"), () => {
					return HttpResponse.json(
						{
							id: "new-saved-search-id",
							name: "New Saved Search",
							filters: [],
							created: new Date().toISOString(),
							updated: new Date().toISOString(),
						},
						{ status: 201 },
					);
				}),
				http.delete(buildApiUrl("/saved_searches/:id"), () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
} satisfies Meta<typeof SavedFilters>;

export default meta;

export const story: StoryObj = { name: "SavedFilters" };

const SavedFiltersStory = () => {
	const [filter, setFilter] = useState<SavedFiltersFilter>(ONE_WEEK_FILTER);

	return (
		<div className="p-4">
			<h2 className="text-lg font-semibold mb-4">Saved Filters Demo</h2>
			<SavedFilters filter={filter} onFilterChange={setFilter} />
			<div className="mt-4 p-4 bg-muted rounded-md">
				<h3 className="text-sm font-medium mb-2">Current Filter:</h3>
				<pre className="text-xs">{JSON.stringify(filter, null, 2)}</pre>
			</div>
		</div>
	);
};

export const WithCustomFilter: StoryObj = {
	name: "With Custom Filter",
	render: () => <SavedFiltersWithCustomFilterStory />,
};

const SavedFiltersWithCustomFilterStory = () => {
	const [filter, setFilter] = useState<SavedFiltersFilter>({
		...ONE_WEEK_FILTER,
		state: ["Running", "Pending"],
	});

	return (
		<div className="p-4">
			<h2 className="text-lg font-semibold mb-4">
				Saved Filters with Custom Filter
			</h2>
			<p className="text-sm text-muted-foreground mb-4">
				When the current filter doesn&apos;t match any saved search, it shows
				&quot;Custom&quot;
			</p>
			<SavedFilters filter={filter} onFilterChange={setFilter} />
			<div className="mt-4 p-4 bg-muted rounded-md">
				<h3 className="text-sm font-medium mb-2">Current Filter:</h3>
				<pre className="text-xs">{JSON.stringify(filter, null, 2)}</pre>
			</div>
		</div>
	);
};

export const EmptySavedSearches: StoryObj = {
	name: "Empty Saved Searches",
	render: () => <SavedFiltersEmptyStory />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/saved_searches/filter"), () => {
					return HttpResponse.json([]);
				}),
			],
		},
	},
};

const SavedFiltersEmptyStory = () => {
	const [filter, setFilter] = useState<SavedFiltersFilter>(ONE_WEEK_FILTER);

	return (
		<div className="p-4">
			<h2 className="text-lg font-semibold mb-4">
				Saved Filters (No User Saved Searches)
			</h2>
			<p className="text-sm text-muted-foreground mb-4">
				Only system saved searches are shown when there are no user saved
				searches
			</p>
			<SavedFilters filter={filter} onFilterChange={setFilter} />
		</div>
	);
};
