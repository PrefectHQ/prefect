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
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { useMutation } from "@tanstack/react-query";
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
import { getQueryService } from "@/api/service";
import type { components } from "@/api/prefect";
import type { JSONValue } from "@/lib/types";
import { Loader2 } from "lucide-react";
import { TagsInput } from "../ui/tags-input";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/router";

const formSchema = z.object({
	name: z.string().min(2, { message: "Name must be at least 2 characters" }),
	value: z.string(),
	tags: z
		.string()
		.min(2, { message: "Tags must be at least 2 characters" })
		.array()
		.optional(),
});

type AddVariableDialogProps = {
	onOpenChange: (open: boolean) => void;
	open: boolean;
};

export const AddVariableDialog = ({
	onOpenChange,
	open,
}: AddVariableDialogProps) => {
	const defaultValues = {
		name: "",
		value: "",
		tags: [],
	};
	const form = useForm<z.infer<typeof formSchema>>({
		resolver: zodResolver(formSchema),
		defaultValues,
	});
	const { toast } = useToast();

	const queryService = getQueryService();
	const { mutate: createVariable, isPending } = useMutation({
		mutationFn: (variable: components["schemas"]["VariableCreate"]) => {
			return queryService.POST("/variables/", {
				body: variable,
			});
		},
		onSettled: async () => {
			return await Promise.all([
				queryClient.invalidateQueries({
					predicate: (query) => query.queryKey[0] === "variables",
				}),
				queryClient.invalidateQueries({
					queryKey: ["total-variable-count"],
				}),
			]);
		},
		onSuccess: () => {
			toast({
				title: "Variable created",
			});
			onClose();
		},
		onError: (error) => {
			const message = error.message || "Unknown error while creating variable.";
			form.setError("root", {
				message,
			});
		},
	});

	const onSubmit = (values: z.infer<typeof formSchema>) => {
		try {
			const value = JSON.parse(values.value) as JSONValue;
			createVariable({
				name: values.name,
				value,
				tags: values.tags,
			});
		} catch {
			form.setError("value", { message: "Value must be valid JSON" });
		}
	};

	const onClose = () => {
		form.reset();
		onOpenChange(false);
	};

	return (
		<Dialog open={open} onOpenChange={onClose}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>New Variable</DialogTitle>
				</DialogHeader>
				<DialogDescription>
					Add a new variable by providing a name, value, and optional tags.
					Values can be any valid JSON value.
				</DialogDescription>
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
										<Input {...field} />
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
									<FormLabel id="value-label">Value</FormLabel>
									<FormControl>
										<CodeMirror
											aria-labelledby="value-label"
											extensions={[json()]}
											basicSetup={{
												foldGutter: false,
												history: false,
											}}
											theme={EditorView.theme({
												"&.cm-editor.cm-focused": {
													outline: "none",
												},
											})}
											className="rounded-md border shadow-sm overflow-hidden"
											{...field}
										/>
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
							<Button type="submit" disabled={isPending}>
								{isPending ? (
									<Loader2 className="w-4 h-4 animate-spin" />
								) : (
									"Create"
								)}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
};
