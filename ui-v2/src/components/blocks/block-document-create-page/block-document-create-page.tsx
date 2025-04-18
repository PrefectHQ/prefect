import {
	useCreateBlockDocument,
	useUpdateBlockDocument,
} from "@/api/block-documents";
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
import { Link, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { BlockDocumentCreatePageHeader } from "./block-document-create-page-header";

type BlockDocumentCreatePageProps = {
	blockSchema: BlockSchema;
	blockType: BlockType;
};

export const BlockDocumentCreatePage = ({
	blockSchema,
	blockType,
}: BlockDocumentCreatePageProps) => {
	const navigate = useNavigate();
	const { values, setValues, errors, validateForm } = useSchemaForm();
	const { createBlockDocument, isPending } = useCreateBlockDocument();

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		try {
			await validateForm({ schema: values });
			createBlockDocument(
				{
					block_schema_id: blockSchema.id,
					block_type_id: blockType.id,
					is_anonymous: false,
				},
				{
					onSuccess: (res) => {
						toast.success("Block updated successfully");
						void navigate({
							to: "/blocks/block/$id",
							params: { id: res.id },
						});
					},
					onError: (err) => {
						const message = "Unknown error while updating validating schema.";
						toast.error(message);
						console.error(message, err);
					},
				},
			);
		} catch (err) {
			const message = "Unknown error while updating validating schema.";
			toast.error(message);
			console.error(message, err);
		}
	};

	return (
		<div className="flex flex-col gap-6">
			<BlockDocumentCreatePageHeader blockType={blockType} />
			<Card className=" p-6 grid grid-cols-[minmax(0,_1fr)_250px] gap-4 ">
				<form
					className="flex flex-col gap-4"
					onSubmit={(e) => void handleSubmit(e)}
				>
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

				<BlockTypeDetails blockType={blockType} />
			</Card>
		</div>
	);
};
