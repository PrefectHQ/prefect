import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import { GlobalConcurrencyLimitSelect } from "@/components/global-concurrency-limit/global-concurrency-limit-select";
import type { PrefectSchemaObject } from "@/components/schemas";
import { SchemaForm } from "@/components/schemas";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { JsonInput } from "@/components/ui/json-input";
import { MarkdownInput } from "@/components/ui/markdown-input";
import { Switch } from "@/components/ui/switch";
import { TagsInput } from "@/components/ui/tags-input";
import { Typography } from "@/components/ui/typography";
import { WorkPoolSelect } from "@/components/work-pools/work-pool-select";
import { WorkQueueSelect } from "@/components/work-pools/work-queue-select";
import { LimitCollissionStrategySelect } from "./limit-collision-strategy-select";
import { useDeploymentForm } from "./use-deployment-form";

type DeploymentFormProps = {
	deployment: Deployment;
	mode: "edit" | "duplicate";
};

export const DeploymentForm = ({ deployment, mode }: DeploymentFormProps) => {
	const {
		form,
		onSave,
		parameterFormErrors,
		setParametersFormValues,
		parametersFormValues,
	} = useDeploymentForm(deployment, { mode });
	const watchPoolName = form.watch("work_pool_name");
	const parametersOpenAPISchema = form.getValues("parameter_openapi_schema");

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => void form.handleSubmit(onSave)(e)}
				className="space-y-4"
			>
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>

				<Typography variant="h3">General</Typography>

				<FormField
					control={form.control}
					name="name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Name</FormLabel>
							<FormControl>
								<Input
									{...field}
									value={field.value}
									disabled={mode === "edit"}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				<FormField
					control={form.control}
					name="description"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Description (Optional)</FormLabel>
							<FormControl>
								<MarkdownInput
									aria-label="deployment description input"
									value={field.value ?? ""}
									onChange={field.onChange}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				<FormField
					control={form.control}
					name="work_pool_name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Work Pool (Optional)</FormLabel>
							<FormControl>
								<WorkPoolSelect
									presetOptions={[{ label: "None", value: "" }]}
									onSelect={field.onChange}
									selected={field.value}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				{watchPoolName && (
					<FormField
						control={form.control}
						name="work_queue_name"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Work Queue (Optional)</FormLabel>
								<FormControl>
									<WorkQueueSelect
										workPoolName={watchPoolName}
										presetOptions={[{ label: "None", value: "" }]}
										onSelect={field.onChange}
										selected={field.value}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				)}

				<FormField
					control={form.control}
					name="tags"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Tags (Optional)</FormLabel>
							<FormControl>
								<TagsInput {...field} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				<FormField
					control={form.control}
					name="concurrency_options.collision_strategy"
					render={({ field }) => (
						<FormItem>
							<FormLabel>
								<div className="col gap-1 mb-0.5">
									<Typography variant="bodySmall">
										Concurrency Limit Collision Strategy (Optional)
									</Typography>
									<Typography
										variant="bodySmall"
										className="text-muted-foreground"
									>
										Configure behavior for runs once the concurrency limit is
										reached.
									</Typography>
								</div>
							</FormLabel>
							<FormControl>
								<LimitCollissionStrategySelect
									value={field.value}
									onValueChange={field.onChange}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				<FormField
					control={form.control}
					name="global_concurrency_limit_id"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Global concurrency limit</FormLabel>
							<FormControl>
								<GlobalConcurrencyLimitSelect
									presetOptions={[{ label: "None", value: null }]}
									onSelect={field.onChange}
									selected={field.value}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				<div className="pt-4 border-t">
					<Typography variant="h3" className="mb-4">
						Parameters
					</Typography>
					{parametersOpenAPISchema && (
						<SchemaForm
							schema={parametersOpenAPISchema as unknown as PrefectSchemaObject}
							errors={parameterFormErrors}
							values={parametersFormValues}
							onValuesChange={setParametersFormValues}
							kinds={["json"]}
						/>
					)}
					<FormField
						control={form.control}
						name="enforce_parameter_schema"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Enforce Parameter Schema</FormLabel>
								<FormControl>
									<Switch
										className="block"
										checked={field.value}
										onCheckedChange={field.onChange}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				</div>

				<div className="pt-4 border-t">
					<Typography variant="h3" className="mb-4">
						Job Variables
					</Typography>
					<FormField
						control={form.control}
						name="job_variables"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Job Variables (Optional)</FormLabel>
								<FormControl>
									<JsonInput {...field} />
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				</div>

				<div className="flex gap-3 justify-end">
					<Link to="/deployments/deployment/$id" params={{ id: deployment.id }}>
						<Button variant="secondary">Cancel</Button>
					</Link>
					<Button type="submit">Save</Button>
				</div>
			</form>
		</Form>
	);
};
