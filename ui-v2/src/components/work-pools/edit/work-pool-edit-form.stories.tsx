import type { Meta, StoryObj } from "@storybook/react";
import { HttpResponse, http } from "msw";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { WorkPoolEditForm } from "./work-pool-edit-form";

const meta: Meta<typeof WorkPoolEditForm> = {
	title: "Components/WorkPools/WorkPoolEditForm",
	component: WorkPoolEditForm,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	parameters: {
		layout: "padded",
	},
};

export default meta;
type Story = StoryObj<typeof WorkPoolEditForm>;

export const Default: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "my-work-pool",
			description: "A work pool for running flow runs",
			concurrency_limit: 10,
			type: "process",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const WithNullDescription: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "no-description-pool",
			description: null,
			concurrency_limit: 5,
			type: "docker",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const WithNullConcurrencyLimit: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "unlimited-pool",
			description: "A pool with unlimited concurrency",
			concurrency_limit: null,
			type: "kubernetes",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const WithLongDescription: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "detailed-pool",
			description:
				"This is a very detailed description of the work pool that explains its purpose, configuration, and usage guidelines. It spans multiple lines to demonstrate how the textarea handles longer content. The pool is configured for high-throughput batch processing workloads.",
			concurrency_limit: 100,
			type: "process",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const SuccessResponse: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "success-pool",
			description: "Test successful update",
			concurrency_limit: 10,
			type: "process",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const ErrorResponse: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "error-pool",
			description: "Test error handling",
			concurrency_limit: 10,
			type: "process",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return HttpResponse.json(
						{ detail: "Work pool not found" },
						{ status: 404 },
					);
				}),
			],
		},
	},
};

export const KubernetesWorkPool: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "production-k8s-pool",
			description: "Kubernetes work pool for production deployments",
			concurrency_limit: 50,
			type: "kubernetes",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const DockerWorkPool: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "docker-dev-pool",
			description: "Docker work pool for development",
			concurrency_limit: 20,
			type: "docker",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const WithBaseJobTemplate: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "process-pool-with-template",
			description: "Process work pool with base job template",
			concurrency_limit: 10,
			type: "process",
			base_job_template: {
				job_configuration: {
					image: "python:3.9",
					env: { NODE_ENV: "production" },
					command: ["python", "main.py"],
				},
				variables: {
					type: "object",
					properties: {
						image: {
							type: "string",
							default: "python:3.9",
							title: "Docker Image",
							description: "The Docker image to use",
						},
						env: {
							type: "object",
							default: {},
							title: "Environment Variables",
						},
					},
				},
			},
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};

export const PrefectAgentWorkPool: Story = {
	args: {
		workPool: createFakeWorkPool({
			name: "prefect-agent-pool",
			description:
				"Prefect Agent work pool - Base Job Template section should be hidden",
			concurrency_limit: 10,
			type: "prefect-agent",
		}),
	},
	parameters: {
		msw: {
			handlers: [
				http.patch("http://localhost:4200/api/work_pools/:name", () => {
					return new HttpResponse(null, { status: 204 });
				}),
			],
		},
	},
};
