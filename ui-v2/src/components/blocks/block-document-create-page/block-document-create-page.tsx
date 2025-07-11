import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateBlockDocument } from "@/api/block-documents";
import type { BlockSchema } from "@/api/block-schemas";
import type { BlockType } from "@/api/block-types";
import { BlockTypeDetails } from "@/components/blocks/block-type-details";
import {
	type PrefectSchemaObject,
	SchemaForm,
	useSchemaForm,
} from "@/components/schemas";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { BlockDocumentCreatePageHeader } from "./block-document-create-page-header";

type BlockDocumentCreatePageProps = {
	blockSchema: BlockSchema;
	blockType: BlockType;
};

// Letters, numbers, and dashes only
const BLOCK_NAME_REGEX = /^[a-zA-Z0-9-]+$/;

const BlockNameFormSchema = z.object({
	blockName: z.string().regex(BLOCK_NAME_REGEX, {
		message: "Name must only contain lowercase letters, numbers, and dashes",
	}),
});

export type BlockNameFormSchema = z.infer<typeof BlockNameFormSchema>;
const DEFAULT_VALUES: BlockNameFormSchema = {
	blockName: "",
};

export const BlockDocumentCreatePage = ({
	blockSchema,
	blockType,
}: BlockDocumentCreatePageProps) => {
	const navigate = useNavigate();
	const { values, setValues, errors, validateForm } = useSchemaForm();
	const { createBlockDocument, isPending } = useCreateBlockDocument();

	const form = useForm({
		resolver: zodResolver(BlockNameFormSchema),
		defaultValues: DEFAULT_VALUES,
	});

	const onSave = async (zodFormValues: BlockNameFormSchema) => {
		try {
			await validateForm({ schema: values });
			// Early exit if there's errors from block schema validation
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
						void navigate({
							to: "/blocks/block/$id",
							params: { id: res.id },
						});
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
		<div className="flex flex-col gap-6">
			<BlockDocumentCreatePageHeader blockType={blockType} />
			<Card className=" p-6 grid grid-cols-[minmax(0,_1fr)_250px] gap-4 ">
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

						<SchemaForm
							values={values}
							onValuesChange={setValues}
							errors={errors}
							kinds={["json"]}
							schema={blockSchema.fields as unknown as PrefectSchemaObject}
						/>
						<div className="flex gap-3 justify-end">
							<Button variant="secondary">
								<Link to="/blocks/catalog">Cancel</Link>
							</Button>
							<Button loading={isPending} type="submit">
								Save
							</Button>
						</div>
					</form>
				</Form>
				<BlockTypeDetails blockType={blockType} />
			</Card>
		</div>
	);
};
