import { zodResolver } from "@hookform/resolvers/zod";
import { useSuspenseQuery } from "@tanstack/react-query";
import { Suspense } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateBlockDocument } from "@/api/block-documents";
import { buildListFilterBlockSchemasQuery } from "@/api/block-schemas";
import { buildGetBlockTypeQuery } from "@/api/block-types";
import {
	LazySchemaForm,
	type PrefectSchemaObject,
	useSchemaForm,
} from "@/components/schemas";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
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
import { Input } from "@/components/ui/input";

type BlockDocumentCreateDialogProps = {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	blockTypeSlug: string;
	onCreated: (blockDocumentId: string) => void;
};

const BLOCK_NAME_REGEX = /^[a-zA-Z0-9-]+$/;

const BlockNameFormSchema = z.object({
	blockName: z.string().regex(BLOCK_NAME_REGEX, {
		message: "Name must only contain lowercase letters, numbers, and dashes",
	}),
});

type BlockNameFormSchema = z.infer<typeof BlockNameFormSchema>;

const DEFAULT_VALUES: BlockNameFormSchema = {
	blockName: "",
};

export const BlockDocumentCreateDialog = ({
	open,
	onOpenChange,
	blockTypeSlug,
	onCreated,
}: BlockDocumentCreateDialogProps) => {
	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
				<Suspense
					fallback={
						<div className="flex flex-col gap-4">
							<div className="h-6 w-48 animate-pulse bg-muted rounded" />
							<div className="h-10 animate-pulse bg-muted rounded" />
							<div className="h-32 animate-pulse bg-muted rounded" />
						</div>
					}
				>
					<BlockDocumentCreateDialogContent
						blockTypeSlug={blockTypeSlug}
						onCreated={onCreated}
						onOpenChange={onOpenChange}
					/>
				</Suspense>
			</DialogContent>
		</Dialog>
	);
};

type BlockDocumentCreateDialogContentProps = {
	blockTypeSlug: string;
	onCreated: (blockDocumentId: string) => void;
	onOpenChange: (open: boolean) => void;
};

const BlockDocumentCreateDialogContent = ({
	blockTypeSlug,
	onCreated,
	onOpenChange,
}: BlockDocumentCreateDialogContentProps) => {
	const { values, setValues, errors, validateForm } = useSchemaForm();
	const { createBlockDocument, isPending } = useCreateBlockDocument();

	const { data: blockType } = useSuspenseQuery(
		buildGetBlockTypeQuery(blockTypeSlug),
	);

	const { data: blockSchemas } = useSuspenseQuery(
		buildListFilterBlockSchemasQuery({
			block_schemas: {
				block_type_id: { any_: [blockType.id] },
				operator: "and_",
			},
			offset: 0,
		}),
	);

	const blockSchema = blockSchemas[0];

	const form = useForm({
		resolver: zodResolver(BlockNameFormSchema),
		defaultValues: DEFAULT_VALUES,
	});

	const onSave = async (zodFormValues: BlockNameFormSchema) => {
		if (!blockSchema) {
			toast.error("Block schema not found");
			return;
		}

		try {
			await validateForm({ schema: values });
			if (errors.length > 0) {
				return;
			}
			createBlockDocument(
				{
					block_schema_id: blockSchema.id,
					block_type_id: blockType.id,
					is_anonymous: false,
					data: values,
					name: zodFormValues.blockName,
				},
				{
					onSuccess: (res) => {
						toast.success("Block created successfully");
						onCreated(res.id);
					},
					onError: (err) => {
						const message = "Unknown error while creating block.";
						toast.error(message);
						console.error(message, err);
					},
				},
			);
		} catch (err) {
			const message = "Unknown error while validating block data.";
			toast.error(message);
			console.error(message, err);
		}
	};

	if (!blockSchema) {
		return (
			<div className="text-center py-4 text-muted-foreground">
				No schema found for this block type.
			</div>
		);
	}

	return (
		<>
			<DialogHeader>
				<DialogTitle>Create {blockType.name}</DialogTitle>
			</DialogHeader>
			<Form {...form}>
				<form
					className="flex flex-col gap-4"
					onSubmit={(e) => void form.handleSubmit(onSave)(e)}
				>
					<FormField
						control={form.control}
						name="blockName"
						render={({ field }) => (
							<FormItem>
								<FormLabel>Name</FormLabel>
								<FormControl>
									<Input {...field} value={field.value} />
								</FormControl>
								<FormMessage />
							</FormItem>
						)}
					/>

					<LazySchemaForm
						values={values}
						onValuesChange={setValues}
						errors={errors}
						kinds={["json"]}
						schema={blockSchema.fields as unknown as PrefectSchemaObject}
					/>

					<DialogFooter>
						<Button
							type="button"
							variant="secondary"
							onClick={() => onOpenChange(false)}
						>
							Cancel
						</Button>
						<Button loading={isPending} type="submit">
							Create
						</Button>
					</DialogFooter>
				</form>
			</Form>
		</>
	);
};
