import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { WorkPoolCreateWizard } from "./work-pool-create-wizard";

// Example base job template for infrastructure configuration
const exampleBaseJobTemplate = {
	job_configuration: {
		image: "{{ image }}",
		command: "{{ command }}",
		env: {
			PREFECT_API_URL: "{{ prefect_api_url }}",
			PREFECT_API_KEY: "{{ prefect_api_key }}",
		},
		labels: {
			app: "prefect",
			version: "{{ flow_run_id }}",
		},
		resources: {
			requests: {
				cpu: "100m",
				memory: "128Mi",
			},
			limits: {
				cpu: "1000m",
				memory: "1Gi",
			},
		},
	},
	variables: {
		properties: {
			image: {
				title: "Image",
				description: "Docker image to use for the job",
				type: "string",
				default: "prefecthq/prefect:2-latest",
			},
			command: {
				title: "Command",
				description: "Command to run in the container",
				type: "array",
				items: { type: "string" },
				default: [],
			},
			prefect_api_url: {
				title: "Prefect API URL",
				description: "URL of the Prefect API server",
				type: "string",
				default: "http://localhost:4200/api",
			},
			prefect_api_key: {
				title: "Prefect API Key",
				description: "API key for authenticating with Prefect",
				type: "string",
				default: null,
			},
		},
		required: ["image"],
	},
};

// Mock work pool types data for Storybook
const mockWorkPoolTypes = {
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
			default_base_job_configuration: exampleBaseJobTemplate,
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
			default_base_job_configuration: exampleBaseJobTemplate,
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
							base_job_template: exampleBaseJobTemplate,
						},
						{ status: 201 },
					);
				}),
			],
		},
	},
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
} satisfies Meta<typeof WorkPoolCreateWizard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WorkPoolCreateWizardStory: Story = {
	name: "WorkPoolCreateWizard",
	parameters: {
		docs: {
			description: {
				story:
					"The work pool creation wizard with three steps: Infrastructure Type, Work Pool Information, and Infrastructure Configuration.",
			},
		},
	},
};
