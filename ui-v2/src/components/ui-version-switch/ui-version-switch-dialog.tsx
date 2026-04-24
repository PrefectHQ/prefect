import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
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
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import {
	UI_SWITCH_REASON_OPTIONS,
	type UiSwitchReason,
} from "@/utils/ui-version";

const formSchema = z.object({
	reason: z.enum(
		UI_SWITCH_REASON_OPTIONS.map((option) => option.value) as [
			UiSwitchReason,
			...UiSwitchReason[],
		],
		{
			required_error: "Select a reason before switching back.",
		},
	),
	notes: z.string().max(2000).default(""),
	openGithubIssue: z.boolean().default(false),
});

export type UiVersionSwitchDialogValues = z.infer<typeof formSchema>;
type UiVersionSwitchDialogFormValues = z.input<typeof formSchema>;

const defaultValues = {
	notes: "",
	openGithubIssue: false,
} satisfies Partial<UiVersionSwitchDialogFormValues>;

type UiVersionSwitchDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSkipFeedback: () => void;
	onSubmitFeedback: (values: UiVersionSwitchDialogValues) => void;
};

export const UiVersionSwitchDialog = ({
	open,
	onOpenChange,
	onSkipFeedback,
	onSubmitFeedback,
}: UiVersionSwitchDialogProps) => {
	const form = useForm<
		UiVersionSwitchDialogFormValues,
		undefined,
		UiVersionSwitchDialogValues
	>({
		resolver: zodResolver(formSchema),
		defaultValues,
	});

	useEffect(() => {
		if (open) {
			form.reset(defaultValues);
		}
	}, [form, open]);

	const handleSubmit = form.handleSubmit((values) => {
		onOpenChange(false);
		onSubmitFeedback(values);
	});

	const handleSkipFeedback = () => {
		onOpenChange(false);
		onSkipFeedback();
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[85vh] overflow-y-auto overflow-x-hidden sm:max-w-xl">
				<DialogHeader>
					<DialogTitle>Switch back to the current UI</DialogTitle>
					<DialogDescription>
						Tell us what brought you back so we can prioritize the new
						experience.
					</DialogDescription>
				</DialogHeader>
				<Form {...form}>
					<form className="min-w-0 space-y-6" onSubmit={handleSubmit}>
						<FormField
							control={form.control}
							name="reason"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Why are you switching back?</FormLabel>
									<FormControl>
										<RadioGroup
											value={field.value}
											onValueChange={field.onChange}
											className="min-w-0 gap-3"
										>
											{UI_SWITCH_REASON_OPTIONS.map((option) => (
												<label
													key={option.value}
													htmlFor={`switch-reason-${option.value}`}
													className="flex w-full min-w-0 cursor-pointer items-start gap-3 rounded-lg border border-border p-3"
												>
													<RadioGroupItem
														id={`switch-reason-${option.value}`}
														value={option.value}
														className="mt-0.5 shrink-0"
													/>
													<div className="min-w-0 space-y-1">
														<div className="text-sm font-medium">
															{option.label}
														</div>
														<div className="break-words text-sm text-muted-foreground">
															{option.description}
														</div>
													</div>
												</label>
											))}
										</RadioGroup>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="notes"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Additional notes</FormLabel>
									<FormControl>
										<Textarea
											{...field}
											placeholder="Optional details that would help us understand the issue."
										/>
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="openGithubIssue"
							render={({ field }) => (
								<FormItem className="flex min-w-0 flex-row items-start gap-3 space-y-0 rounded-lg border border-border p-3">
									<FormControl>
										<Checkbox
											checked={field.value}
											onCheckedChange={(checked) =>
												field.onChange(Boolean(checked))
											}
											className="shrink-0"
										/>
									</FormControl>
									<div className="min-w-0 space-y-1">
										<FormLabel>Also open GitHub issue</FormLabel>
										<div className="break-words text-sm text-muted-foreground">
											Open a prefilled issue in a new tab with the structured
											feedback and your notes.
										</div>
									</div>
								</FormItem>
							)}
						/>
						<DialogFooter>
							<Button
								type="button"
								variant="ghost"
								onClick={handleSkipFeedback}
							>
								Skip feedback and switch
							</Button>
							<Button
								type="button"
								variant="outline"
								onClick={() => onOpenChange(false)}
							>
								Cancel
							</Button>
							<Button type="submit">Submit feedback and switch</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
