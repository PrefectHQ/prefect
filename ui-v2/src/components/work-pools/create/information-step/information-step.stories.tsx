import { zodResolver } from "@hookform/resolvers/zod";
import type { Meta, StoryObj } from "@storybook/react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Form } from "@/components/ui/form";
import { WorkPoolInformationStep } from "./information-step";
import {
	type WorkPoolInformationFormValues,
	workPoolInformationSchema,
} from "./schema";

const meta: Meta<typeof WorkPoolInformationStep> = {
	title: "Components/WorkPools/Create/InformationStep",
	component: WorkPoolInformationStep,
	parameters: {
		layout: "centered",
	},
	tags: ["autodocs"],
};

export default meta;
type Story = StoryObj<typeof meta>;

const StoryWrapper = ({
	defaultValues = {},
	onSubmit = () => {},
}: {
	defaultValues?: Partial<WorkPoolInformationFormValues>;
	onSubmit?: (data: WorkPoolInformationFormValues) => void;
}) => {
	const form = useForm<WorkPoolInformationFormValues>({
		resolver: zodResolver(workPoolInformationSchema),
		defaultValues: {
			name: "",
			description: null,
			concurrencyLimit: null,
			...defaultValues,
		},
	});

	return (
		<Card className="w-[500px] p-6">
			<Form {...form}>
				<form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
					<div className="space-y-2">
						<h2 className="text-lg font-semibold">Work Pool Information</h2>
						<p className="text-sm text-muted-foreground">
							Provide basic information about your work pool.
						</p>
					</div>
					<WorkPoolInformationStep />
					<div className="flex justify-end space-x-2">
						<Button variant="outline" type="button">
							Cancel
						</Button>
						<Button type="submit">Continue</Button>
					</div>
				</form>
			</Form>
		</Card>
	);
};

export const Default: Story = {
	render: () => <StoryWrapper />,
};

export const WithValidationErrors: Story = {
	render: () => {
		const form = useForm<WorkPoolInformationFormValues>({
			resolver: zodResolver(workPoolInformationSchema),
			defaultValues: {
				name: "",
				description: null,
				concurrencyLimit: null,
			},
		});

		// Trigger validation errors
		form.setError("name", {
			type: "manual",
			message: "Name is required",
		});

		return (
			<Card className="w-[500px] p-6">
				<Form {...form}>
					<form className="space-y-6">
						<div className="space-y-2">
							<h2 className="text-lg font-semibold">Work Pool Information</h2>
							<p className="text-sm text-muted-foreground">
								Provide basic information about your work pool.
							</p>
						</div>
						<WorkPoolInformationStep />
						<div className="flex justify-end space-x-2">
							<Button variant="outline" type="button">
								Cancel
							</Button>
							<Button type="submit">Continue</Button>
						</div>
					</form>
				</Form>
			</Card>
		);
	},
};

export const WithPrefectNameError: Story = {
	render: () => {
		const form = useForm<WorkPoolInformationFormValues>({
			resolver: zodResolver(workPoolInformationSchema),
			defaultValues: {
				name: "prefect-test-pool",
				description: null,
				concurrencyLimit: null,
			},
		});

		// Trigger prefect validation error
		form.setError("name", {
			type: "manual",
			message:
				"Work pools starting with 'prefect' are reserved for internal use.",
		});

		return (
			<Card className="w-[500px] p-6">
				<Form {...form}>
					<form className="space-y-6">
						<div className="space-y-2">
							<h2 className="text-lg font-semibold">Work Pool Information</h2>
							<p className="text-sm text-muted-foreground">
								Provide basic information about your work pool.
							</p>
						</div>
						<WorkPoolInformationStep />
						<div className="flex justify-end space-x-2">
							<Button variant="outline" type="button">
								Cancel
							</Button>
							<Button type="submit">Continue</Button>
						</div>
					</form>
				</Form>
			</Card>
		);
	},
};

export const WithPrefilledValues: Story = {
	render: () => (
		<StoryWrapper
			defaultValues={{
				name: "my-production-pool",
				description:
					"A work pool for production deployments with high reliability requirements.",
				concurrencyLimit: 10,
			}}
		/>
	),
};

export const WithLongDescription: Story = {
	render: () => (
		<StoryWrapper
			defaultValues={{
				name: "development-pool",
				description:
					"This is a development work pool used for testing and development purposes. It has relaxed concurrency limits and is configured to handle experimental workloads. This pool is not suitable for production use and should only be used during the development phase of projects.",
				concurrencyLimit: 5,
			}}
		/>
	),
};

export const WithHighConcurrency: Story = {
	render: () => (
		<StoryWrapper
			defaultValues={{
				name: "high-throughput-pool",
				description: "High-throughput work pool for batch processing",
				concurrencyLimit: 100,
			}}
		/>
	),
};
