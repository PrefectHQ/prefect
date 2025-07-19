import type { components } from "@/api/prefect";

type WorkerMetadata = components["schemas"]["WorkerMetadata"];

export const createFakeWorkerMetadata = (
	overrides?: Partial<WorkerMetadata>,
): WorkerMetadata => {
	return {
		type: "process",
		display_name: "Process",
		description: "Execute flow runs as subprocesses",
		documentation_url: "https://docs.prefect.io/latest/concepts/work-pools/",
		logo_url: "https://example.com/process.png",
		install_command: "pip install prefect",
		is_beta: false,
		default_base_job_configuration: {
			job_configuration: {
				command: "{{ command }}",
				env: "{{ env }}",
				labels: "{{ labels }}",
				name: "{{ name }}",
				stream_output: "{{ stream_output }}",
				working_dir: "{{ working_dir }}",
			},
			variables: {
				type: "object",
				properties: {
					command: {
						type: "string",
						title: "Command",
						description: "The command to run for the flow run.",
						default: null,
					},
					env: {
						type: "object",
						title: "Environment Variables",
						description:
							"Environment variables to set when starting a flow run.",
						default: {},
						additionalProperties: {
							type: "string",
						},
					},
					labels: {
						type: "object",
						title: "Labels",
						description:
							"Labels applied to infrastructure created by a worker.",
						default: {},
						additionalProperties: {
							type: "string",
						},
					},
					name: {
						type: "string",
						title: "Process Name",
						description: "The name of the process.",
						default: null,
					},
					stream_output: {
						type: "boolean",
						title: "Stream Output",
						description:
							"Stream output from the process to local standard output.",
						default: true,
					},
					working_dir: {
						type: "string",
						title: "Working Directory",
						description: "The working directory for the process.",
						default: null,
					},
				},
			},
		},
		...overrides,
	};
};

export const createFakeWorkersMetadataResponse = () => {
	return {
		prefect: {
			process: createFakeWorkerMetadata({
				type: "process",
				display_name: "Process",
				description: "Execute flow runs as subprocesses",
			}),
		},
		"prefect-aws": {
			ecs: createFakeWorkerMetadata({
				type: "ecs",
				display_name: "AWS ECS",
				description: "Execute flow runs on AWS ECS",
				logo_url: "https://example.com/ecs.png",
			}),
		},
		"prefect-kubernetes": {
			kubernetes: createFakeWorkerMetadata({
				type: "kubernetes",
				display_name: "Kubernetes",
				description: "Execute flow runs in Kubernetes",
				logo_url: "https://example.com/k8s.png",
				is_beta: true,
			}),
		},
	};
};
