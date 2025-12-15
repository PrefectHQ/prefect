import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { reactQueryDecorator } from "@/storybook/utils";
import { TagsFilter } from "./tags-filter";

const meta: Meta<typeof TagsFilter> = {
	title: "Components/FlowRuns/TagsFilter",
	component: TagsFilter,
	decorators: [
		reactQueryDecorator,
		(Story) => (
			<div className="w-64">
				<Story />
			</div>
		),
	],
	parameters: {
		docs: {
			description: {
				component:
					"A combobox filter for selecting tags to filter flow runs by. Supports both selecting from suggestions and freeform tag entry.",
			},
		},
	},
};

export default meta;
type Story = StoryObj<typeof TagsFilter>;

const TagsFilterWithState = ({
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

export const Default: Story = {
	render: () => <TagsFilterWithState />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [
							{ id: "1", name: "Flow Run 1", tags: ["production", "critical"] },
							{ id: "2", name: "Flow Run 2", tags: ["staging", "production"] },
							{ id: "3", name: "Flow Run 3", tags: ["development", "test"] },
						],
						count: 3,
						pages: 1,
						page: 1,
						limit: 100,
					});
				}),
			],
		},
	},
};

export const WithSelectedTags: Story = {
	render: () => (
		<TagsFilterWithState
			initialSelectedTags={new Set(["production", "critical", "staging"])}
		/>
	),
	parameters: {
		msw: {
			handlers: [
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
			],
		},
	},
};

export const EmptyState: Story = {
	render: () => <TagsFilterWithState />,
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/paginate"), () => {
					return HttpResponse.json({
						results: [],
						count: 0,
						pages: 0,
						page: 1,
						limit: 100,
					});
				}),
			],
		},
	},
};
