import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FormProvider, useForm } from "react-hook-form";
import { InfrastructureTypeStep } from "./infrastructure-type-step";

const mockWorkersResponse = {
	prefect: {
		process: {
			type: "process",
			display_name: "Process",
			description:
				"Execute flow runs as subprocesses on your local machine or a remote server",
			logo_url:
				"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg",
			documentation_url:
				"https://docs.prefect.io/guides/deployment/push-work-pools/",
			is_beta: false,
		},
	},
	"prefect-aws": {
		ecs: {
			type: "ecs",
			display_name: "AWS ECS",
			description:
				"Execute flow runs as ECS tasks on AWS Elastic Container Service",
			logo_url:
				"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/amazonwebservices/amazonwebservices-original.svg",
			documentation_url: "https://prefecthq.github.io/prefect-aws/ecs/",
			is_beta: false,
		},
		lambda: {
			type: "lambda",
			display_name: "AWS Lambda",
			description: "Execute flow runs as AWS Lambda functions",
			logo_url:
				"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/amazonwebservices/amazonwebservices-original.svg",
			documentation_url: "https://prefecthq.github.io/prefect-aws/lambda/",
			is_beta: true,
		},
	},
	"prefect-gcp": {
		"cloud-run": {
			type: "cloud-run",
			display_name: "Google Cloud Run",
			description: "Execute flow runs as Google Cloud Run jobs",
			logo_url:
				"https://cdn.jsdelivr.net/gh/devicons/devicon/icons/googlecloud/googlecloud-original.svg",
			documentation_url: "https://prefecthq.github.io/prefect-gcp/cloud_run/",
			is_beta: false,
		},
	},
};

const meta: Meta<typeof InfrastructureTypeStep> = {
	title: "Components/WorkPools/Create/InfrastructureTypeStep",
	component: InfrastructureTypeStep,
	parameters: {
		layout: "padded",
	},
	tags: ["autodocs"],
	decorators: [
		(Story) => {
			const queryClient = new QueryClient({
				defaultOptions: {
					queries: {
						retry: false,
						staleTime: Number.POSITIVE_INFINITY,
					},
				},
			});

			// Pre-populate the query cache with mock data
			queryClient.setQueryData(
				["collections", "work-pool-types"],
				mockWorkersResponse,
			);

			const FormWrapper = () => {
				const form = useForm<{ type: string }>({
					defaultValues: {
						type: "",
					},
				});

				return (
					<FormProvider {...form}>
						<Story />
					</FormProvider>
				);
			};

			return (
				<QueryClientProvider client={queryClient}>
					<div className="max-w-2xl">
						<FormWrapper />
					</div>
				</QueryClientProvider>
			);
		},
	],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	args: {},
};

export const WithSelection: Story = {
	decorators: [
		(Story) => {
			const queryClient = new QueryClient({
				defaultOptions: {
					queries: {
						retry: false,
						staleTime: Number.POSITIVE_INFINITY,
					},
				},
			});

			// Pre-populate the query cache with mock data
			queryClient.setQueryData(
				["collections", "work-pool-types"],
				mockWorkersResponse,
			);

			const FormWrapper = () => {
				const form = useForm<{ type: string }>({
					defaultValues: {
						type: "process",
					},
				});

				return (
					<FormProvider {...form}>
						<Story />
					</FormProvider>
				);
			};

			return (
				<QueryClientProvider client={queryClient}>
					<div className="max-w-2xl">
						<FormWrapper />
					</div>
				</QueryClientProvider>
			);
		},
	],
	args: {},
};

export const MinimalOptions: Story = {
	decorators: [
		(Story) => {
			const queryClient = new QueryClient({
				defaultOptions: {
					queries: {
						retry: false,
						staleTime: Number.POSITIVE_INFINITY,
					},
				},
			});

			// Mock with fewer options
			const minimalResponse = {
				prefect: {
					process: mockWorkersResponse.prefect.process,
				},
			};

			queryClient.setQueryData(
				["collections", "work-pool-types"],
				minimalResponse,
			);

			const FormWrapper = () => {
				const form = useForm<{ type: string }>({
					defaultValues: {
						type: "",
					},
				});

				return (
					<FormProvider {...form}>
						<Story />
					</FormProvider>
				);
			};

			return (
				<QueryClientProvider client={queryClient}>
					<div className="max-w-2xl">
						<FormWrapper />
					</div>
				</QueryClientProvider>
			);
		},
	],
	args: {},
};
