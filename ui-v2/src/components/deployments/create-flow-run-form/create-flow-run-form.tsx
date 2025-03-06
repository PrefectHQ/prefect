import { Deployment } from "@/api/deployments";
import { SchemaForm } from "@/components/schemas";
import type { PrefectSchemaObject } from "@/components/schemas";
import { Button } from "@/components/ui/button";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { Typography } from "@/components/ui/typography";
import { Link } from "@tanstack/react-router";
import { FlowRunNameInput } from "./flow-run-name-input";
import { FlowRunStartInput } from "./flow-run-start-input";
import { useCreateFlowRunForm } from "./use-create-flow-run-form";

type CreateFlowRunFormProps = {
	deployment: Deployment;
};

export const CreateFlowRunForm = ({ deployment }: CreateFlowRunFormProps) => {
	const {
		form,
		onCreate,
		parameterFormErrors,
		setParametersFormValues,
		parametersFormValues,
	} = useCreateFlowRunForm(deployment);
	const parametersOpenAPISchema = form.getValues("parameter_openapi_schema");

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
					<FormField
						control={form.control}
						name="state.state_details.scheduled_time"
						render={({ field }) => (
							<FormItem>
								<FormLabel>
									<Typography variant="h3" className="mb-4">
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

				<div className="flex gap-3 justify-end">
					<Link to="/deployments/deployment/$id" params={{ id: deployment.id }}>
						<Button variant="secondary">Cancel</Button>
					</Link>
					<Button type="submit">Submit</Button>
				</div>
			</form>
		</Form>
	);
};
