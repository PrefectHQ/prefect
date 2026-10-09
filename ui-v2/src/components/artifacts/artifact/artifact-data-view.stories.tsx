import type { Meta, StoryObj } from "@storybook/react";
import { createFakeArtifact } from "@/mocks";
import { ArtifactDataView } from "./artifact-data-view";

const meta: Meta<typeof ArtifactDataView> = {
	title: "Components/Artifacts/ArtifactDataView",
	component: ArtifactDataView,
};

export default meta;
type Story = StoryObj<typeof ArtifactDataView>;

const tableRows = [
	{ metric: "latency", value: 120, unit: "ms" },
	{ metric: "throughput", value: 1500, unit: "req/s" },
	{ metric: "error_rate", value: 0.02, unit: "%" },
];

export const Markdown: Story = {
	args: {
		artifact: createFakeArtifact({
			type: "markdown",
			data: "# Daily report\n\nProcessed **1,204** records with an accuracy of `94.2%`.",
		}),
	},
};

export const Table: Story = {
	args: {
		artifact: createFakeArtifact({
			type: "table",
			data: JSON.stringify(tableRows),
		}),
	},
};

export const TableWithArrayData: Story = {
	args: {
		artifact: createFakeArtifact({ type: "table", data: tableRows }),
	},
};

export const MalformedTable: Story = {
	args: {
		artifact: createFakeArtifact({ type: "table", data: "not valid json" }),
	},
};

export const Progress: Story = {
	args: {
		artifact: createFakeArtifact({ type: "progress", data: 64 }),
	},
};

export const Image: Story = {
	args: {
		artifact: createFakeArtifact({
			type: "image",
			data: "https://picsum.photos/600/300",
		}),
	},
};

export const UnknownType: Story = {
	args: {
		artifact: createFakeArtifact({
			type: "result",
			data: { value: 42, status: "success" },
		}),
	},
};

export const WithCustomFallback: Story = {
	args: {
		artifact: createFakeArtifact({
			type: "result",
			data: { value: 42, status: "success" },
		}),
		fallback: (
			<pre className="bg-muted p-3 rounded-md text-sm">Custom fallback</pre>
		),
	},
};
