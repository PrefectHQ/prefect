import { Button } from "@/components/ui/button";
import { Form, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ActionsSchema } from "@/components/automations/automations-wizard/action-type-schemas";
import { AutomationsWizardActionTypeAdditionalFields } from "@/components/automations/automations-wizard/automations-wizard-action-type-additional-fields";
import { AutomationsWizardActionTypeSelect } from "@/components/automations/automations-wizard/automations-wizard-action-type-select";

type AutomationWizardActionStepProps = {
	onSubmit: (schema: ActionsSchema) => void;
};

export const AutomationsWizardActionStep = ({
	onSubmit,
}: AutomationWizardActionStepProps) => {
	const form = useForm<z.infer<typeof ActionsSchema>>({
		resolver: zodResolver(ActionsSchema),
	});

	// Reset form when changing action type
	const watchType = form.watch("type");
	useEffect(() => {
		const currentActionType = form.getValues("type");
		form.reset();
		form.setValue("type", currentActionType);
	}, [form, watchType]);

	return (
		<Form {...form}>
			<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
				<AutomationsWizardActionTypeSelect />
				<AutomationsWizardActionTypeAdditionalFields />
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				{/** nb: This button will change once we integrate it with the full wizard */}
				<Button className="mt-2" type="submit">
					Validate
				</Button>
			</form>
		</Form>
	);
};
