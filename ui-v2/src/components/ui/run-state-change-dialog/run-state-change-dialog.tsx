import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { RUN_STATES, type RunStates } from "@/api/flow-runs/constants";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { StateBadge } from "@/components/ui/state-badge";
import { Textarea } from "@/components/ui/textarea";

const formSchema = z.object({
	state: z.enum(
		Object.keys(RUN_STATES) as [
			components["schemas"]["StateType"],
			...components["schemas"]["StateType"][],
		],
	),
	message: z.string().optional().default(""),
});

export type RunStateFormValues = z.infer<typeof formSchema>;

type RunState = {
	type: RunStates | null | undefined;
	name: string | null | undefined;
};

export type RunStateDialogProps = {
	currentState: RunState;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	title: string;
	onSubmitChange: (values: RunStateFormValues) => Promise<void>;
};

export const RunStateChangeDialog = ({
	currentState,
	open,
	onOpenChange,
	title,
	onSubmitChange,
}: RunStateDialogProps) => {
	const [isSubmitting, setIsSubmitting] = useState(false);

	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: {
			state: undefined,
			message: "",
		},
	});

	const stateOptions = useMemo(
		() =>
			Object.entries(RUN_STATES).filter(([key]) => key !== currentState.type),
		[currentState.type],
	);

	const isSubmitDisabled = isSubmitting || !form.watch("state");

	const onSubmit = async (values: RunStateFormValues) => {
		setIsSubmitting(true);
		try {
			await onSubmitChange(values);
			onOpenChange(false);
		} catch {
			// Error is handled/displayed by the onSubmitChange promise
			// (typically via a toast in the mutation's onError callback)
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent aria-describedby={undefined}>
				<DialogHeader>
					<DialogTitle>{title}</DialogTitle>
				</DialogHeader>

				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}
						className="space-y-4"
					>
						{currentState.type && currentState.name && (
							<div className="mb-4">
								<FormLabel className="mb-2 block">Current State</FormLabel>
								<StateBadge type={currentState.type} name={currentState.name} />
							</div>
						)}

						<FormField
							control={form.control}
							name="state"
							render={({ field }) => (
								<FormItem className="w-full">
									<FormLabel>Desired State</FormLabel>
									<FormControl>
										<Select {...field} onValueChange={field.onChange}>
											<SelectTrigger
												aria-label="select state"
												className="w-full"
											>
												<SelectValue placeholder="Select state">
													{field.value && (
														<StateBadge
															type={field.value}
															name={RUN_STATES[field.value]}
														/>
													)}
												</SelectValue>
											</SelectTrigger>
											<SelectContent className="w-full min-w-[300px]">
												<SelectGroup>
													{stateOptions.map(([key, value]) => (
														<SelectItem
															key={key}
															value={key}
															className="flex items-center"
														>
															<StateBadge
																type={key as components["schemas"]["StateType"]}
																name={value}
															/>
														</SelectItem>
													))}
												</SelectGroup>
											</SelectContent>
										</Select>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<FormField
							control={form.control}
							name="message"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Reason (Optional)</FormLabel>
									<FormControl>
										<Textarea
											{...field}
											placeholder="State changed manually via UI"
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="flex flex-col gap-2 pt-4">
							<div className="flex justify-end space-x-2">
								<Button
									type="button"
									variant="outline"
									onClick={() => onOpenChange(false)}
								>
									Close
								</Button>
								<Button type="submit" disabled={isSubmitDisabled}>
									Change
								</Button>
							</div>
						</div>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
