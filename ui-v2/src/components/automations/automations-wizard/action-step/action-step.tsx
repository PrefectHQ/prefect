import { Button } from "@/components/ui/button";
import { Form, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useEffect } from "react";
import { ActionTypeAdditionalFields } from "./action-type-additional-fields";
import { ActionsSchema, UNASSIGNED } from "./action-type-schemas";
import { ActionTypeSelect } from "./action-type-select";

type ActionStepProps = {
	onSubmit: (schema: ActionsSchema) => void;
};

export const ActionStep = ({ onSubmit }: ActionStepProps) => {
	const form = useForm<z.infer<typeof ActionsSchema>>({
		resolver: zodResolver(ActionsSchema),
	});
	const type = form.watch("type");
	// reset form values based on selected action type
	useEffect(() => {
		switch (type) {
			case "change-flow-run-state":
				form.reset({ type });
				break;
			case "run-deployment":
				form.reset({ type, deployment_id: UNASSIGNED });
				break;
			case "pause-deployment":
			case "resume-deployment":
				form.reset({
					type,
					deployment_id: UNASSIGNED,
				});
				break;
			case "pause-work-queue":
			case "resume-work-queue":
				form.reset({
					type,
					work_queue_id: UNASSIGNED,
				});
				break;
			case "pause-work-pool":
			case "resume-work-pool":
				form.reset({
					type,
					work_pool_id: UNASSIGNED,
				});
				break;
			case "pause-automation":
			case "resume-automation":
				form.reset({
					type,
					automation_id: UNASSIGNED,
				});
				break;
			case "send-notification":
				form.reset({ type });
				break;
			case "cancel-flow-run":
			case "suspend-flow-run":
			case "resume-flow-run":
			default:
				form.reset({ type });
				break;
		}
	}, [form, type]);

	return (
		<Form {...form}>
			<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
				<div className="flex flex-col gap-4">
					<ActionTypeSelect />
					<ActionTypeAdditionalFields actionType={type} />
					<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				</div>
				{/** nb: This button will change once we integrate it with the full wizard */}
				<Button className="mt-2" type="submit">
					Validate
				</Button>
			</form>
		</Form>
	);
};
