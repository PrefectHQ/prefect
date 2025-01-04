import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { AutomationsWizardActionTypeAdditionalFields } from "@/components/automations/automations-wizard/automations-wizard-action-type-additional-fields";
import { AutomationsWizardActionTypeSelect } from "@/components/automations/automations-wizard/automations-wizard-action-type-select";
import { Button } from "@/components/ui/button";
import { Form, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ActionsSchema } from "../action-type-schemas";

const meta = {
	title: "Components/Automations/Wizard/ActionStep",
	args: { onValueChange: fn() },
	render: () => <StoryExample />,
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "ActionStep" };

function StoryExample() {
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

	const onSubmit = (values: z.infer<typeof ActionsSchema>) => {
		console.log(values);
	};

	return (
		<Form {...form}>
			<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
				<AutomationsWizardActionTypeSelect />
				<AutomationsWizardActionTypeAdditionalFields />
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				<Button className="mt-2" type="submit">
					Validate
				</Button>
			</form>
		</Form>
	);
}
