import { useSuspenseQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
	type Automation,
	buildGetAutomationQuery,
	useReplaceAutomation,
} from "@/api/automations";
import type { components } from "@/api/prefect";
import {
	type AutomationWizardSchema as AutomationWizardSchemaType,
	type TriggerInput,
	type TriggerTemplate,
	UNASSIGNED,
} from "./automation-schema";

type AutomationAction = Automation["actions"][number];
type AutomationTrigger = Automation["trigger"];
type AutomationUpdate = components["schemas"]["AutomationUpdate"];

/**
 * Input type for the automation wizard form (before Zod transformations).
 * This represents what the form fields accept, not the transformed output.
 */
type AutomationWizardFormInput = {
	name: string;
	description?: string;
	triggerTemplate?: TriggerTemplate;
	trigger: TriggerInput;
	actions: ActionFormInput[];
};

/**
 * Input type for actions (before Zod transformations).
 * These types don't have the `source` field - that's added by the transform.
 */
type ActionFormInput =
	| { type: "do-nothing" }
	| { type: "cancel-flow-run" | "suspend-flow-run" | "resume-flow-run" }
	| {
			type: "change-flow-run-state";
			state:
				| "COMPLETED"
				| "RUNNING"
				| "SCHEDULED"
				| "PENDING"
				| "FAILED"
				| "CANCELLED"
				| "CANCELLING"
				| "CRASHED"
				| "PAUSED";
			name?: string;
			message?: string;
	  }
	| {
			type: "run-deployment";
			deployment_id: string;
			parameters?: Record<string, unknown>;
			job_variables?: Record<string, unknown>;
	  }
	| {
			type: "pause-deployment" | "resume-deployment";
			deployment_id: string;
	  }
	| {
			type: "pause-work-queue" | "resume-work-queue";
			work_queue_id: string;
	  }
	| {
			type: "pause-work-pool" | "resume-work-pool";
			work_pool_id: string;
	  }
	| {
			type: "pause-automation" | "resume-automation";
			automation_id: string;
	  }
	| {
			type: "send-notification";
			block_document_id: string;
			body: string;
			subject: string;
	  };

type UseEditAutomationOptions = {
	automationId: string;
	onSuccess?: () => void;
	onError?: (error: Error) => void;
};

type UseEditAutomationReturn = {
	defaultValues: AutomationWizardFormInput | undefined;
	isLoading: boolean;
	updateAutomation: (values: AutomationWizardSchemaType) => void;
	isPending: boolean;
};

/**
 * Transforms an API action to form-compatible format.
 * Converts null resource IDs to UNASSIGNED constant and removes source fields.
 */
function transformActionToFormValue(action: AutomationAction): ActionFormInput {
	switch (action.type) {
		case "run-deployment": {
			return {
				type: "run-deployment",
				deployment_id: action.deployment_id ?? UNASSIGNED,
				parameters: action.parameters ?? undefined,
				job_variables: action.job_variables ?? undefined,
			};
		}
		case "pause-deployment":
		case "resume-deployment": {
			return {
				type: action.type,
				deployment_id: action.deployment_id ?? UNASSIGNED,
			};
		}
		case "pause-work-queue":
		case "resume-work-queue": {
			return {
				type: action.type,
				work_queue_id: action.work_queue_id ?? UNASSIGNED,
			};
		}
		case "pause-work-pool":
		case "resume-work-pool": {
			return {
				type: action.type,
				work_pool_id: action.work_pool_id ?? UNASSIGNED,
			};
		}
		case "pause-automation":
		case "resume-automation": {
			return {
				type: action.type,
				automation_id: action.automation_id ?? UNASSIGNED,
			};
		}
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run": {
			return {
				type: action.type,
			};
		}
		case "change-flow-run-state": {
			return {
				type: "change-flow-run-state",
				state: action.state,
				name: action.name ?? undefined,
				message: action.message ?? undefined,
			};
		}
		case "send-notification": {
			return {
				type: "send-notification",
				block_document_id: action.block_document_id,
				body: action.body,
				subject: action.subject,
			};
		}
		case "do-nothing": {
			return {
				type: "do-nothing",
			};
		}
		case "call-webhook": {
			// call-webhook is not supported in the form schema, treat as do-nothing
			return {
				type: "do-nothing",
			};
		}
		default: {
			// Fallback for any unknown action types
			return {
				type: "do-nothing",
			};
		}
	}
}

/**
 * Transforms an API trigger to form-compatible format.
 * Handles event triggers, compound triggers, and sequence triggers.
 */
function transformTriggerToFormValue(trigger: AutomationTrigger): TriggerInput {
	switch (trigger.type) {
		case "event": {
			return {
				type: "event",
				posture: trigger.posture,
				threshold: trigger.threshold,
				within: trigger.within,
				match: trigger.match,
				match_related: Array.isArray(trigger.match_related)
					? trigger.match_related[0]
					: trigger.match_related,
				for_each: trigger.for_each,
				after: trigger.after,
				expect: trigger.expect,
			};
		}
		case "compound": {
			return {
				type: "compound",
				triggers: trigger.triggers.map(transformTriggerToFormValue),
				require: trigger.require,
				within: trigger.within ?? undefined,
			};
		}
		case "sequence": {
			return {
				type: "sequence",
				triggers: trigger.triggers.map(transformTriggerToFormValue),
				within: trigger.within ?? undefined,
			};
		}
		default: {
			// Fallback to a basic event trigger
			return {
				type: "event",
				posture: "Reactive",
				threshold: 1,
				within: 0,
			};
		}
	}
}

/**
 * Infers the trigger template from an event trigger's match conditions.
 * Returns "custom" if the template cannot be determined.
 */
function inferTriggerTemplate(trigger: AutomationTrigger): TriggerTemplate {
	if (trigger.type !== "event") {
		return "custom";
	}

	const resourceId = trigger.match?.["prefect.resource.id"];
	if (!resourceId) {
		return "custom";
	}

	const resourceIdStr = Array.isArray(resourceId) ? resourceId[0] : resourceId;

	if (resourceIdStr?.startsWith("prefect.flow-run.")) {
		return "flow-run-state";
	}
	if (resourceIdStr?.startsWith("prefect.deployment.")) {
		return "deployment-status";
	}
	if (resourceIdStr?.startsWith("prefect.work-pool.")) {
		return "work-pool-status";
	}
	if (resourceIdStr?.startsWith("prefect.work-queue.")) {
		return "work-queue-status";
	}

	return "custom";
}

/**
 * Transforms API automation data to form-compatible values.
 * Converts null resource IDs to UNASSIGNED, removes source fields from actions,
 * and handles trigger transformations.
 */
export function transformAutomationToFormValues(
	automation: Automation,
): AutomationWizardFormInput {
	return {
		name: automation.name,
		description: automation.description || undefined,
		triggerTemplate: inferTriggerTemplate(automation.trigger),
		trigger: transformTriggerToFormValue(automation.trigger),
		actions: automation.actions.map(transformActionToFormValue),
	};
}

/**
 * Transforms form values to API update format.
 * The Zod schema transformations handle most of the conversion (UNASSIGNED -> null, adding source fields).
 * This function removes form-only fields and ensures proper typing.
 */
export function transformFormValuesToApi(
	values: AutomationWizardSchemaType,
): Omit<AutomationUpdate, "enabled"> {
	return {
		name: values.name,
		description: values.description ?? "",
		trigger: values.trigger,
		actions: values.actions,
	};
}

/**
 * Hook for editing an automation.
 * Fetches automation data, transforms it for form editing, and handles update submissions.
 */
export const useEditAutomation = (
	options: UseEditAutomationOptions,
): UseEditAutomationReturn => {
	const { automationId, onSuccess, onError } = options;

	const { data: automation, isLoading } = useSuspenseQuery(
		buildGetAutomationQuery(automationId),
	);

	const defaultValues = useMemo(() => {
		if (!automation) {
			return undefined;
		}
		return transformAutomationToFormValues(automation);
	}, [automation]);

	const { replaceAutomation: replaceAutomationMutation, isPending } =
		useReplaceAutomation();

	const updateAutomation = (values: AutomationWizardSchemaType) => {
		const apiValues = transformFormValuesToApi(values);
		replaceAutomationMutation(
			{
				id: automationId,
				enabled: automation?.enabled ?? true,
				...apiValues,
			},
			{
				onSuccess: () => {
					onSuccess?.();
				},
				onError: (error) => {
					onError?.(error instanceof Error ? error : new Error(String(error)));
				},
			},
		);
	};

	return {
		defaultValues,
		isLoading,
		updateAutomation,
		isPending,
	};
};
