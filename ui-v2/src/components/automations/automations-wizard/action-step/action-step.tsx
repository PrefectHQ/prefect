import { Button } from "@/components/ui/button";
import { Form, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ActionTypeAdditionalFields } from "./action-type-additional-fields";
import { ActionsSchema } from "./action-type-schemas";
import { ActionTypeSelect } from "./action-type-select";

type ActionStepProps = {
	onSubmit: (schema: ActionsSchema) => void;
};

export const ActionStep = ({ onSubmit }: ActionStepProps) => {
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
				<ActionTypeSelect />
				<ActionTypeAdditionalFields actionType={watchType} />
				<FormMessage>{form.formState.errors.root?.message}</FormMessage>
				{/** nb: This button will change once we integrate it with the full wizard */}
				<Button className="mt-2" type="submit">
					Validate
				</Button>
			</form>
		</Form>
	);
};
