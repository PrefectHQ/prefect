import { Link, useNavigate } from "@tanstack/react-router";
import { type FormEvent, useEffect } from "react";
import { toast } from "sonner";
import {
	type BlockDocument,
	useUpdateBlockDocument,
} from "@/api/block-documents";
import { BlockTypeDetails } from "@/components/blocks/block-type-details";
import {
	type PrefectSchemaObject,
	SchemaForm,
	useSchemaForm,
} from "@/components/schemas";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { BlockDocumentEditPageHeader } from "./block-document-edit-page-header";

type BlockDocumentEditPageProps = {
	blockDocument: BlockDocument;
};

export const BlockDocumentEditPage = ({
	blockDocument,
}: BlockDocumentEditPageProps) => {
	const navigate = useNavigate();
	const { values, setValues, errors, validateForm } = useSchemaForm();
	const { updateBlockDocument, isPending } = useUpdateBlockDocument();

	// sync up values with block document values
	useEffect(() => {
		if (blockDocument.data) {
			setValues(blockDocument.data);
		}
	}, [blockDocument.data, setValues]);

	const handleSubmit = async (event: FormEvent) => {
		event.preventDefault();
		try {
			await validateForm({ schema: values });
			updateBlockDocument(
				{
					id: blockDocument.id,
					data: values,
					merge_existing_data: false,
				},
				{
					onSuccess: () => {
						toast.success("Block updated successfully");
						void navigate({
							to: "/blocks/block/$id",
							params: { id: blockDocument.id },
						});
					},
					onError: (err) => {
						const message = "Unknown error while updating block.";
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
			<BlockDocumentEditPageHeader blockDocument={blockDocument} />
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
						schema={
							(blockDocument?.block_schema?.fields ??
								{}) as unknown as PrefectSchemaObject
						}
					/>
					<div className="flex gap-3 justify-end">
						<Button variant="secondary">
							<Link to="/blocks/block/$id" params={{ id: blockDocument.id }}>
								Cancel
							</Link>
						</Button>
						<Button loading={isPending} type="submit">
							Save
						</Button>
					</div>
				</form>

				{blockDocument.block_type && (
					<BlockTypeDetails blockType={blockDocument.block_type} />
				)}
			</Card>
		</div>
	);
};
