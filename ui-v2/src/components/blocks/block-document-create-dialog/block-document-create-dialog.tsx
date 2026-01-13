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
import { Skeleton } from "@/components/ui/skeleton";

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
				<DialogHeader>
					<DialogTitle>Create New Block</DialogTitle>
				</DialogHeader>
				<Suspense fallback={<BlockDocumentCreateDialogSkeleton />}>
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

const BlockDocumentCreateDialogSkeleton = () => {
	return (
		<div className="flex flex-col gap-4">
			<Skeleton className="h-10 w-full" />
			<Skeleton className="h-32 w-full" />
			<Skeleton className="h-10 w-24 ml-auto" />
		</div>
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
	const { data: blockType } = useSuspenseQuery(
		buildGetBlockTypeQuery(blockTypeSlug),
	);

	const { data: blockSchemas } = useSuspenseQuery(
		buildListFilterBlockSchemasQuery({
			block_schemas: {
				block_type_id: { any_: [blockType.id] },
			},
			limit: 1,
		}),
	);

	const blockSchema = blockSchemas[0];

	if (!blockSchema) {
		return (
			<div className="text-muted-foreground">
				No schema found for this block type.
			</div>
		);
	}

	return (
		<BlockDocumentCreateForm
			blockTypeId={blockType.id}
			blockSchemaId={blockSchema.id}
			blockSchemaFields={blockSchema.fields as unknown as PrefectSchemaObject}
			onCreated={onCreated}
			onOpenChange={onOpenChange}
		/>
	);
};

type BlockDocumentCreateFormProps = {
	blockTypeId: string;
	blockSchemaId: string;
	blockSchemaFields: PrefectSchemaObject;
	onCreated: (blockDocumentId: string) => void;
	onOpenChange: (open: boolean) => void;
};

const BlockDocumentCreateForm = ({
	blockTypeId,
	blockSchemaId,
	blockSchemaFields,
	onCreated,
	onOpenChange,
}: BlockDocumentCreateFormProps) => {
	const { values, setValues, errors, validateForm } = useSchemaForm();
	const { createBlockDocument, isPending } = useCreateBlockDocument();

	const form = useForm({
		resolver: zodResolver(BlockNameFormSchema),
		defaultValues: DEFAULT_VALUES,
	});

	const onSave = async (zodFormValues: BlockNameFormSchema) => {
		try {
			await validateForm({ schema: values });
			if (errors.length > 0) {
				return;
			}
			createBlockDocument(
				{
					block_schema_id: blockSchemaId,
					block_type_id: blockTypeId,
					is_anonymous: false,
					data: values,
					name: zodFormValues.blockName,
				},
				{
					onSuccess: (res) => {
						toast.success("Block created successfully");
						onCreated(res.id);
						onOpenChange(false);
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

	return (
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
					schema={blockSchemaFields}
				/>

				<DialogFooter>
					<Button
						variant="secondary"
						type="button"
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
	);
};
