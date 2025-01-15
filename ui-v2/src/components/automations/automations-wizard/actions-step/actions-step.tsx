import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/ui/icons";

import { Form, FormMessage } from "@/components/ui/form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import { ActionStep } from "./action-step";
import {
	ActionsSchema,
	type ActionsSchema as ActionsSchemaType,
} from "./action-type-schemas";

type ActionStepsProps = {
	onPrevious: () => void;
	onNext: (actionsSchema: ActionsSchemaType) => void;
};

export const ActionsStep = ({ onPrevious, onNext }: ActionStepsProps) => {
	const form = useForm<ActionsSchemaType>({
		resolver: zodResolver(ActionsSchema),
		defaultValues: {
			actions: [{ type: undefined }],
		},
	});

	const { fields, append, remove } = useFieldArray({
		control: form.control,
		name: "actions",
		shouldUnregister: true,
		rules: { minLength: 1 },
	});

	const onSubmit = (values: ActionsSchemaType) => {
		onNext(values);
	};

	return (
		<Card className="p-4 pt-8">
			<Form {...form}>
				<form onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}>
					{fields.map(({ id }, index) => (
						<ActionStep key={id} index={index} onRemove={() => remove(index)} />
					))}
					<Button
						type="button"
						variant="outline"
						onClick={() => append({ type: "cancel-flow-run" })}
					>
						<Icon id="Plus" className="mr-2 h-4 w-4" /> Add Action
					</Button>

					<FormMessage>{form.formState.errors.root?.message}</FormMessage>

					<div className="flex gap-2 justify-end">
						<Button type="button" variant="outline">
							Cancel
						</Button>
						<Button type="button" variant="outline" onClick={onPrevious}>
							Previous
						</Button>
						<Button type="submit" disabled={form.formState.disabled}>
							Next
						</Button>
					</div>
				</form>
			</Form>
		</Card>
	);
};
