import { Link } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import type { Deployment } from "@/api/deployments";
import {
	type CreateNewFlowRun,
	useDeploymentCreateFlowRun,
} from "@/api/flow-runs";
import {
	LazySchemaForm,
	type PrefectSchemaObject,
	useSchemaForm,
} from "@/components/schemas";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogClose,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export type QuickRunParametersDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	deployment: Deployment;
};

const QUICK_RUN_STATE = {
	type: "SCHEDULED",
	message: "Run from the Prefect UI",
	state_details: {
		deferred: false,
		untrackable_result: false,
		pause_reschedule: false,
	},
} as const;

export const QuickRunParametersDialog = ({
	open,
	onOpenChange,
	deployment,
}: QuickRunParametersDialogProps) => {
	const [enforceParameterSchema, setEnforceParameterSchema] = useState(
		() => deployment.enforce_parameter_schema,
	);
	const {
		values: parameters,
		setValues: setParameters,
		errors,
		validateForm,
	} = useSchemaForm(deployment.parameters ?? {});
	const { createDeploymentFlowRun, isPending } = useDeploymentCreateFlowRun();
	const parameterSchema = deployment.parameter_openapi_schema;

	const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();

		if (enforceParameterSchema && parameterSchema) {
			try {
				const validationResult = await validateForm({
					schema: parameterSchema,
				});
				if (!validationResult?.valid) {
					return;
				}
			} catch (error) {
				const message =
					error instanceof Error
						? error.message
						: "Unknown error while validating parameters.";
				toast.error(message);
				return;
			}
		}

		const payload: CreateNewFlowRun = {
			parameters,
			enforce_parameter_schema: enforceParameterSchema,
			state: QUICK_RUN_STATE,
		};

		createDeploymentFlowRun(
			{
				id: deployment.id,
				...payload,
			},
			{
				onSuccess: (res) => {
					toast.success("Flow run created", {
						action: (
							<Link to="/runs/flow-run/$id" params={{ id: res.id }}>
								<Button size="sm">View run</Button>
							</Link>
						),
						description: (
							<p>
								<span className="font-bold">{res.name}</span> scheduled to start{" "}
								<span className="font-bold">now</span>
							</p>
						),
					});
					onOpenChange(false);
				},
				onError: (error) => {
					toast.error(
						error.message || "Unknown error while creating flow run.",
					);
				},
			},
		);
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
				<DialogHeader>
					<DialogTitle>Run Deployment</DialogTitle>
				</DialogHeader>
				<form onSubmit={(event) => void onSubmit(event)} className="space-y-4">
					{parameterSchema && (
						<>
							<LazySchemaForm
								schema={parameterSchema as unknown as PrefectSchemaObject}
								errors={errors}
								values={parameters}
								onValuesChange={setParameters}
								kinds={["json"]}
							/>
							<div className="flex items-center gap-2">
								<Switch
									id="quick-run-enforce-parameter-schema"
									checked={enforceParameterSchema}
									onCheckedChange={setEnforceParameterSchema}
								/>
								<Label htmlFor="quick-run-enforce-parameter-schema">
									Validate parameters
								</Label>
							</div>
						</>
					)}
					<DialogFooter>
						<DialogClose asChild>
							<Button type="button" variant="outline">
								Cancel
							</Button>
						</DialogClose>
						<Button type="submit" loading={isPending}>
							Run
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
};
