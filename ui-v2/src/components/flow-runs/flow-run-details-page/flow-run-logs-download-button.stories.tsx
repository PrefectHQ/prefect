import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeFlowRun } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunLogsDownloadButton } from "./flow-run-logs-download-button";

const meta = {
	title: "Components/FlowRuns/FlowRunLogsDownloadButton",
	component: FlowRunLogsDownloadButton,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
} satisfies Meta<typeof FlowRunLogsDownloadButton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {
		flowRun: createFakeFlowRun({ name: "my-flow-run" }),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id/logs/download"), () => {
					return new HttpResponse(
						"timestamp,level,message\n2024-01-01,INFO,Test log",
						{
							headers: { "Content-Type": "text/csv" },
						},
					);
				}),
			],
		},
	},
};

export const WithLongName: Story = {
	args: {
		flowRun: createFakeFlowRun({
			name: "my-very-long-flow-run-name-that-might-be-truncated",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/flow_runs/:id/logs/download"), () => {
					return new HttpResponse(
						"timestamp,level,message\n2024-01-01,INFO,Test log",
						{
							headers: { "Content-Type": "text/csv" },
						},
					);
				}),
			],
		},
	},
};
