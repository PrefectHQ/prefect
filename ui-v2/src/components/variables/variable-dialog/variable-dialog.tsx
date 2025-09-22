import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { JsonInput } from "@/components/ui/json-input";
import { TagsInput } from "@/components/ui/tags-input";
import { useCreateVariable, useUpdateVariable } from "@/hooks/variables";

export type JSONValue =
	| string
	| number
	| boolean
	| Record<string, never>
	| unknown[]
	| null;

const formSchema = z.object({
	name: z.string().min(2, { message: "Name must be at least 2 characters" }),
	value: z.string(),
	tags: z.string().array().optional(),
});

export type VariableDialogProps = {
	onOpenChange: (open: boolean) => void;
	open: boolean;
	variableToEdit?: components["schemas"]["Variable"];
};

const VARIABLE_FORM_DEFAULT_VALUES = {
	name: "",
	value: "",
	tags: [],
};

export const VariableDialog = ({
	onOpenChange,
	open,
	variableToEdit,
}: VariableDialogProps) => {
	const form = useForm({
		resolver: zodResolver(formSchema),
		defaultValues: VARIABLE_FORM_DEFAULT_VALUES,
	});
	const initialValues = useMemo(() => {
		if (!variableToEdit) return undefined;
		return {
			name: variableToEdit.name,
			value: JSON.stringify(variableToEdit.value, null, 2),
			tags: variableToEdit.tags,
		};
	}, [variableToEdit]);

	useEffect(() => {
		// Ensure we start with the initial values when the dialog opens
		if (open) {
			form.reset(initialValues ?? VARIABLE_FORM_DEFAULT_VALUES);
		}
	}, [initialValues, form, open]);

	const { createVariable, isPending: isCreating } = useCreateVariable();

	const { updateVariable, isPending: isUpdating } = useUpdateVariable();

	const onSubmit = (values: z.infer<typeof formSchema>) => {
		try {
			const value = JSON.parse(values.value) as JSONValue;
			if (variableToEdit?.id) {
				updateVariable(
					{
						id: variableToEdit.id,
						name: values.name,
						value,
						tags: values.tags,
					},
					{
						onSuccess: () => {
							toast.success("Variable updated");
							onOpenChange(false);
						},
						onError: (error) => {
							const message =
								error.message || "Unknown error while updating variable.";
							form.setError("root", {
								message,
							});
						},
					},
				);
			} else {
				createVariable(
					{
						name: values.name,
						value,
						tags: values.tags,
					},
					{
						onSuccess: () => {
							toast.success("Variable created");
							onOpenChange(false);
						},
						onError: (error) => {
							const message =
								error.message || "Unknown error while creating variable.";
							form.setError("root", {
								message,
							});
						},
					},
				);
			}
		} catch {
			form.setError("value", { message: "Value must be valid JSON" });
		}
	};
	const dialogTitle = variableToEdit ? "Edit Variable" : "New Variable";
	const dialogDescription = variableToEdit
		? "Edit the variable by changing the name, value, or tags."
		: "Add a new variable by providing a name, value, and optional tags. Values can be any valid JSON value.";

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{dialogTitle}</DialogTitle>
				</DialogHeader>
				<DialogDescription>{dialogDescription}</DialogDescription>
				<Form {...form}>
					<form
						onSubmit={(e) => void form.handleSubmit(onSubmit)(e)}
						className="space-y-4"
					>
						<FormMessage>{form.formState.errors.root?.message}</FormMessage>
						<FormField
							control={form.control}
							name="name"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Name</FormLabel>
									<FormControl>
										<Input autoComplete="off" {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="value"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Value</FormLabel>
									<FormControl>
										<JsonInput {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<FormField
							control={form.control}
							name="tags"
							render={({ field }) => (
								<FormItem>
									<FormLabel>Tags</FormLabel>
									<FormControl>
										<TagsInput {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>
						<DialogFooter>
							<DialogTrigger asChild>
								<Button variant="outline">Close</Button>
							</DialogTrigger>
							<Button type="submit" loading={isCreating || isUpdating}>
								{variableToEdit ? "Save" : "Create"}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
