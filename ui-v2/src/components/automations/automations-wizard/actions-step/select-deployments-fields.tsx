import { useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";
import type { DeploymentWithFlow } from "@/api/deployments";
import { useListDeploymentsWithFlows } from "@/api/deployments/use-list-deployments-with-flows";
import {
	type AutomationWizardSchema,
	UNASSIGNED,
} from "@/components/automations/automations-wizard/automation-schema";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "@/components/ui/combobox";
import {
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Icon } from "@/components/ui/icons";
import useDebounce from "@/hooks/use-debounce";
import { LoadingSelectState } from "./loading-select-state";

const INFER_OPTION = {
	value: UNASSIGNED,
	name: "Infer Deployment",
} as const;

const getButtonLabel = (
	data: Array<DeploymentWithFlow> | undefined,
	fieldValue: string | null,
) => {
	if (fieldValue === INFER_OPTION.value) {
		return INFER_OPTION.name;
	}
	const deployment = data?.find((d) => d.id === fieldValue);
	if (!deployment) {
		return undefined;
	}
	return <DeploymentLabel deploymentWithFlow={deployment} />;
};

type SelectDeploymentsFieldsProps = {
	action: "Run" | "Pause" | "Resume";
	index: number;
};

export const SelectDeploymentsFields = ({
	action,
	index,
}: SelectDeploymentsFieldsProps) => {
	const [search, setSearch] = useState("");
	const form = useFormContext<AutomationWizardSchema>();
	const actionType = form.watch(`actions.${index}.type`);
	const deploymentId = useWatch<AutomationWizardSchema>({
		name: `actions.${index}.deployment_id`,
	});

	const debouncedSearch = useDebounce(search, 500);
	const { data } = useListDeploymentsWithFlows({
		page: 1,
		sort: "NAME_ASC",
		deployments: {
			operator: "or_",
			flow_or_deployment_name: {
				like_: debouncedSearch,
			},
		},
	});

	const isInferredOptionFiltered = INFER_OPTION.name
		.toLowerCase()
		.includes(search.toLowerCase());

	const deploymentsWithFlows = data?.results;

	return (
		<div>
			<FormField
				control={form.control}
				name={`actions.${index}.deployment_id`}
				render={({ field }) => {
					const buttonLabel = getButtonLabel(deploymentsWithFlows, field.value);
					return (
						<FormItem className="flex flex-col">
							<FormLabel>Deployment To {action}</FormLabel>
							<Combobox>
								<ComboboxTrigger
									selected={Boolean(buttonLabel)}
									aria-label={`Select Deployment to ${action}`}
								>
									{buttonLabel ?? "Select deployment"}
								</ComboboxTrigger>
								<ComboboxContent>
									<ComboboxCommandInput
										value={search}
										onValueChange={setSearch}
										placeholder="Search for an deployment..."
									/>
									<ComboboxCommandEmtpy>
										No deployment found
									</ComboboxCommandEmtpy>
									<ComboboxCommandList>
										<ComboboxCommandGroup>
											{isInferredOptionFiltered && (
												<ComboboxCommandItem
													selected={field.value === INFER_OPTION.value}
													onSelect={field.onChange}
													value={INFER_OPTION.value}
												>
													{INFER_OPTION.name}
												</ComboboxCommandItem>
											)}
											{deploymentsWithFlows ? (
												deploymentsWithFlows.map((deployment) => (
													<ComboboxCommandItem
														aria-label={deployment.name}
														key={deployment.id}
														selected={field.value === deployment.id}
														onSelect={field.onChange}
														value={deployment.id}
													>
														<DeploymentLabel deploymentWithFlow={deployment} />
													</ComboboxCommandItem>
												))
											) : (
												<LoadingSelectState />
											)}
										</ComboboxCommandGroup>
									</ComboboxCommandList>
								</ComboboxContent>
							</Combobox>
							<FormMessage />
						</FormItem>
					);
				}}
			/>
			{deploymentId !== INFER_OPTION.value &&
				actionType === "run-deployment" && <div>TODO: Additional fields</div>}
		</div>
	);
};

type DeploymentLabelProps = {
	deploymentWithFlow: DeploymentWithFlow;
};
const DeploymentLabel = ({ deploymentWithFlow }: DeploymentLabelProps) => {
	if (deploymentWithFlow.flow) {
		return (
			<div className="flex items-center gap-0.5">
				<div>{deploymentWithFlow.flow.name}</div>
				<Icon className="size-4" id="ChevronRight" />
				<div>{deploymentWithFlow.name}</div>
			</div>
		);
	}

	return deploymentWithFlow.name;
};
