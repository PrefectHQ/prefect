import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

// Mock work pool types data for Storybook
const mockWorkPoolTypes = {
	"prefect-agent": {
		"prefect-agent": {
			type: "prefect-agent",
			display_name: "Prefect Agent",
			description: "Execute flow runs with a Prefect agent.",
			logo_url:
				"https://images.ctfassets.net/gm98wzqotmnx/08yCE6xpJMX9Kjn1CcGfNy/faa476bbba80b18b16a2c2d0dc66a5be/prefect-mark-solid-black.svg",
			documentation_url:
				"https://docs.prefect.io/latest/concepts/work-pools/#prefect-agent-work-pool",
			is_beta: false,
		},
	},
	kubernetes: {
		"kubernetes-job": {
			type: "kubernetes-job",
			display_name: "Kubernetes Job",
			description: "Execute flow runs as Kubernetes Jobs.",
			logo_url:
				"https://images.ctfassets.net/gm98wzqotmnx/1jbV4lceHOjGgunX15lUwT/a1cea49ca56d0b142a1d30a5b8296ff0/kubernetes-logo.svg",
			documentation_url:
				"https://docs.prefect.io/latest/concepts/work-pools/#kubernetes-job-work-pool",
			is_beta: false,
		},
	},
	docker: {
		"docker-container": {
			type: "docker-container",
			display_name: "Docker Container",
			description: "Execute flow runs in Docker containers.",
			logo_url:
				"https://images.ctfassets.net/gm98wzqotmnx/2IfXXfMq66mrzJBDFFCHTp/6d8f7cdca7b4f6d7ce95128b540f3cc2/docker-logo.svg",
			documentation_url:
				"https://docs.prefect.io/latest/concepts/work-pools/#docker-container-work-pool",
			is_beta: false,
		},
	},
};

const meta = {
	title: "Components/WorkPools/WorkPoolCreateWizard",
	component: WorkPoolCreateWizard,
	parameters: {
		layout: "padded",
		msw: {
			handlers: [
				// Mock the collections API endpoint
				http.get(
					buildApiUrl("/collections/views/aggregate-worker-metadata"),
					() => {
						return HttpResponse.json(mockWorkPoolTypes);
					},
				),
				// Mock work pool creation
				http.post(buildApiUrl("/work_pools/"), () => {
					return HttpResponse.json(
						{
							id: "mock-work-pool-id",
							name: "test-work-pool",
							type: "prefect-agent",
						},
						{ status: 201 },
					);
				}),
			],
		},
	},
	decorators: [
		reactQueryDecorator,
		routerDecorator,
		toastDecorator,
		(Story) => (
			<div className="max-w-4xl mx-auto">
				<Story />
			</div>
		),
	],
} satisfies Meta<typeof WorkPoolCreateWizard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	parameters: {
		docs: {
			description: {
				story:
					"The work pool creation wizard with three steps: Infrastructure Type, Work Pool Information, and Infrastructure Configuration.",
			},
		},
	},
};

export const WithInteractions: Story = {
	...Default,
	parameters: {
		...Default.parameters,
		docs: {
			description: {
				story:
					"Work pool creation wizard demonstrating the complete flow from infrastructure selection to work pool creation.",
			},
		},
	},
};
