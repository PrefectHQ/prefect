import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { Component, type ReactNode } from "react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FlowStats } from "./flow-stats";

class StoryErrorBoundary extends Component<
	{ children: ReactNode },
	{ hasError: boolean; error: Error | null }
> {
	constructor(props: { children: ReactNode }) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error) {
		return { hasError: true, error };
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="rounded-lg border border-red-200 bg-red-50 p-4">
					<h3 className="text-sm font-medium text-red-800">
						Error loading flow stats
					</h3>
					<p className="mt-1 text-sm text-red-600">
						{this.state.error?.message || "An unexpected error occurred"}
					</p>
				</div>
			);
		}
		return this.props.children;
	}
}

const meta = {
	title: "Components/Flows/FlowStats",
	component: FlowStats,
	decorators: [routerDecorator, reactQueryDecorator],
	args: {
		flowId: "test-flow-id",
	},
} satisfies Meta<typeof FlowStats>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(42);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(150);
				}),
			],
		},
	},
};

export const WithVariedCounts: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(25);
				}),
				http.post(buildApiUrl("/task_runs/count"), async ({ request }) => {
					const body = (await request.json()) as {
						task_runs?: { state?: { type?: { any_?: string[] } } };
					};
					const stateTypes = body?.task_runs?.state?.type?.any_ ?? [];

					if (stateTypes.includes("COMPLETED") && stateTypes.length === 1) {
						return HttpResponse.json(120);
					}
					if (stateTypes.includes("FAILED")) {
						return HttpResponse.json(15);
					}
					return HttpResponse.json(150);
				}),
			],
		},
	},
};

export const Empty: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(0);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(0);
				}),
			],
		},
	},
};

export const WithError: Story = {
	render: (args) => (
		<StoryErrorBoundary>
			<FlowStats {...args} />
		</StoryErrorBoundary>
	),
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/flow_runs/count"), () => {
					return HttpResponse.json(
						{ detail: "Internal server error" },
						{ status: 500 },
					);
				}),
				http.post(buildApiUrl("/task_runs/count"), () => {
					return HttpResponse.json(
						{ detail: "Internal server error" },
						{ status: 500 },
					);
				}),
			],
		},
	},
};
