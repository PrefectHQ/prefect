import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogDescription,
	DialogTrigger,
} from "@/components/ui/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "../ui/form";
import { Input } from "../ui/input";
import type { components } from "@/api/prefect";
import type { JSONValue } from "@/lib/types";
import { TagsInput } from "../ui/tags-input";
import { JsonInput } from "@/components/ui/json-input";
import { useEffect, useMemo } from "react";
import { useCreateVariable, useUpdateVariable } from "./hooks";

const formSchema = z.object({
	name: z.string().min(2, { message: "Name must be at least 2 characters" }),
	value: z.string(),
	tags: z
		.string()
		.min(2, { message: "Tags must be at least 2 characters" })
		.array()
		.optional(),
});

export type VariableDialogProps = {
	onOpenChange: (open: boolean) => void;
	open: boolean;
	existingVariable?: components["schemas"]["Variable"];
};

const VARIABLE_FORM_DEFAULT_VALUES = {
	name: "",
	value: "",
	tags: [],
};

export const VariableDialog = ({
	onOpenChange,
	open,
	existingVariable,
}: VariableDialogProps) => {
	const form = useForm<z.infer<typeof formSchema>>({
		resolver: zodResolver(formSchema),
		defaultValues: VARIABLE_FORM_DEFAULT_VALUES,
	});
	const initialValues = useMemo(() => {
		if (!existingVariable) return undefined;
		return {
			name: existingVariable.name,
			value: JSON.stringify(existingVariable.value),
			tags: existingVariable.tags,
		};
	}, [existingVariable]);

	useEffect(() => {
		// Ensure we start with the initial values when the dialog opens
		if (open) {
			form.reset(initialValues ?? VARIABLE_FORM_DEFAULT_VALUES);
		}
	}, [initialValues, form, open]);

	const { mutate: createVariable, isPending: isCreating } = useCreateVariable({
		onSuccess: () => {
			onOpenChange(false);
		},
		onError: (error) => {
			const message = error.message || "Unknown error while creating variable.";
			form.setError("root", {
				message,
			});
		},
	});

	const { mutate: updateVariable, isPending: isUpdating } = useUpdateVariable({
		onSuccess: () => {
			onOpenChange(false);
		},
		onError: (error) => {
			const message = error.message || "Unknown error while updating variable.";
			form.setError("root", {
				message,
			});
		},
	});

	const onSubmit = (values: z.infer<typeof formSchema>) => {
		try {
			const value = JSON.parse(values.value) as JSONValue;
			if (existingVariable?.id) {
				updateVariable({
					id: existingVariable.id,
					name: values.name,
					value,
					tags: values.tags,
				});
			} else {
				createVariable({
					name: values.name,
					value,
					tags: values.tags,
				});
			}
		} catch {
			form.setError("value", { message: "Value must be valid JSON" });
		}
	};
	const dialogTitle = existingVariable ? "Edit Variable" : "New Variable";
	const dialogDescription = existingVariable
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
								{existingVariable ? "Save" : "Create"}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
