import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { userEvent, waitFor, within } from "storybook/test";
import { createFakeDeployment, createFakeFlow } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { FlowRunAction } from "./flow-run-action";

const flow = createFakeFlow({ name: "my-flow" });

const deployments = Array.from({ length: 15 }, (_, i) =>
	createFakeDeployment({ flow_id: flow.id, name: `deployment-${i + 1}` }),
);

const paginateHandler = (results = deployments) =>
	http.post(buildApiUrl("/deployments/paginate"), async ({ request }) => {
		const body = (await request.json()) as {
			page: number;
			limit: number;
			deployments?: { name?: { like_?: string } };
		};
		const search = body.deployments?.name?.like_?.toLowerCase();
		const filtered = search
			? results.filter((d) => d.name.toLowerCase().includes(search))
			: results;
		const start = (body.page - 1) * body.limit;
		return HttpResponse.json({
			results: filtered.slice(start, start + body.limit),
			count: filtered.length,
			page: body.page,
			pages: Math.max(1, Math.ceil(filtered.length / body.limit)),
			limit: body.limit,
		});
	});

const countHandler = (count: number) =>
	http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
		HttpResponse.json({ [flow.id]: count }),
	);

const meta = {
	title: "Components/Flows/FlowRunAction",
	component: FlowRunAction,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	args: { flow },
} satisfies Meta<typeof FlowRunAction>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Loading: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flows/count-deployments"), () => {
					return new Promise(() => {});
				}),
			],
		},
	},
};

export const CountError: Story = {
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/ui/flows/count-deployments"), () =>
					HttpResponse.error(),
				),
			],
		},
	},
};

export const NoDeployments: Story = {
	parameters: {
		msw: { handlers: [countHandler(0)] },
	},
};

export const OneDeployment: Story = {
	parameters: {
		msw: {
			handlers: [countHandler(1), paginateHandler([deployments[0]])],
		},
	},
};

export const MultipleDeployments: Story = {
	parameters: {
		msw: { handlers: [countHandler(15), paginateHandler()] },
	},
};

export const PickerLoading: Story = {
	parameters: {
		msw: {
			handlers: [
				countHandler(2),
				http.post(buildApiUrl("/deployments/paginate"), () => {
					return new Promise(() => {});
				}),
			],
		},
	},
};

export const PickerError: Story = {
	parameters: {
		msw: {
			handlers: [
				countHandler(2),
				http.post(buildApiUrl("/deployments/paginate"), () =>
					HttpResponse.error(),
				),
			],
		},
	},
};

export const SearchNoMatches: Story = {
	...MultipleDeployments,
	play: async ({ canvasElement }) => {
		const canvas = within(canvasElement);
		const body = within(canvasElement.ownerDocument.body);
		await waitFor(async () => {
			await userEvent.click(
				await canvas.findByRole("button", { name: /run/i }),
			);
		});
		await userEvent.click(
			await body.findByRole("button", { name: "Select a deployment" }),
		);
		await userEvent.type(
			await body.findByPlaceholderText("Search deployments..."),
			"zzz",
		);
		await body.findByText("No deployments match your search");
	},
};
