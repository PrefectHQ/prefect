import { Link } from "@tanstack/react-router";
import type { Deployment } from "@/api/deployments";
import type { PrefectSchemaObject } from "@/components/schemas";
import { SchemaForm } from "@/components/schemas";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
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
import { Switch } from "@/components/ui/switch";
import { TagsInput } from "@/components/ui/tags-input";
import { Textarea } from "@/components/ui/textarea";
import { Typography } from "@/components/ui/typography";
import { WorkQueueSelect } from "@/components/work-pools/work-queue-select";
import { FlowRunNameInput } from "./flow-run-name-input";
import { FlowRunStartInput } from "./flow-run-start-input";
import { useCreateFlowRunForm } from "./use-create-flow-run-form";

type CreateFlowRunFormProps = {
	deployment: Deployment;
	overrideParameters: Record<string, unknown> | undefined;
};

export const CreateFlowRunForm = ({
	deployment,
	overrideParameters,
}: CreateFlowRunFormProps) => {
	const {
		form,
		onCreate,
		parameterFormErrors,
		setParametersFormValues,
		parametersFormValues,
	} = useCreateFlowRunForm(deployment, overrideParameters);
	const parametersOpenAPISchema = form.getValues("parameter_openapi_schema");

	const { id, work_pool_name } = deployment;

	return (
		<Form {...form}>
			<form
				onSubmit={(e) => void form.handleSubmit(onCreate)(e)}
				className="space-y-4"
			>
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>

				<FormField
					control={form.control}
					name="name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Run Name</FormLabel>
							<FormControl>
								<FlowRunNameInput {...field} onClickGenerate={field.onChange} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>

				{parametersOpenAPISchema && (
					<div className="pt-4 border-t">
						<Typography variant="h3" className="mb-4">
							Parameters
						</Typography>

						<SchemaForm
							schema={parametersOpenAPISchema as unknown as PrefectSchemaObject}
							errors={parameterFormErrors}
							values={parametersFormValues}
							onValuesChange={setParametersFormValues}
							kinds={["json"]}
						/>

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
				)}

				<div className="pt-4 border-t">
					<FormField
						control={form.control}
						name="state.state_details.scheduled_time"
						render={({ field }) => (
							<FormItem>
								<FormLabel>
									<Typography variant="bodyLarge" className="mb-4">
										Start
									</Typography>
								</FormLabel>
								<FormControl>
									<FlowRunStartInput
										value={field.value}
										onValueChange={field.onChange}
									/>
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>
				</div>

				<Accordion type="single" collapsible>
					<AccordionItem value="item-1">
						<AccordionTrigger>
							<Typography variant="bodyLarge">Additional Options</Typography>
						</AccordionTrigger>
						<AccordionContent className="flex flex-col gap-4">
							<FormField
								control={form.control}
								name="state.message"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Message (Optional)</FormLabel>
										<FormControl>
											<Textarea
												placeholder="Created from the Prefect UI"
												className="resize-none"
												{...field}
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
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

							{work_pool_name && (
								<FormField
									control={form.control}
									name="work_queue_name"
									render={({ field }) => (
										<FormItem>
											<FormLabel>
												Work Queue for {work_pool_name} (Optional)
											</FormLabel>
											<FormControl>
												<WorkQueueSelect
													workPoolName={work_pool_name}
													selected={field.value}
													onSelect={field.onChange}
												/>
											</FormControl>
											<FormMessage />
										</FormItem>
									)}
								/>
							)}

							<div className="flex gap-4">
								<div className="w-full">
									<FormField
										control={form.control}
										name="empirical_policy.retries"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Retries (Optional)</FormLabel>
												<FormControl>
													<Input type="number" {...field} />
												</FormControl>
												<FormMessage />
											</FormItem>
										)}
									/>
								</div>
								<div className="w-full">
									<FormField
										control={form.control}
										name="empirical_policy.retry_delay"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Retries (Optional)</FormLabel>
												<div className="flex items-center">
													<FormControl>
														<Input
															className="border-r-0 rounded-r-none"
															type="number"
															{...field}
														/>
													</FormControl>
													<Typography className="border rounded-sm rounded-l-none p-1.25">
														Seconds
													</Typography>
												</div>
												<FormMessage />
											</FormItem>
										)}
									/>
								</div>
							</div>

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
						</AccordionContent>
					</AccordionItem>
				</Accordion>

				<div className="flex gap-3 justify-end">
					<Link to="/deployments/deployment/$id" params={{ id }}>
						<Button variant="secondary">Cancel</Button>
					</Link>
					<Button type="submit">Submit</Button>
				</div>
			</form>
		</Form>
	);
};
