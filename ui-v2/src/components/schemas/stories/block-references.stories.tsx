import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { LazyJsonInput as JsonInput } from "@/components/ui/json-input-lazy";
import { Typography } from "@/components/ui/typography";
import type { SchemaFormValues } from "../types/values";
import { resolveBlockReferences } from "../utilities/resolveBlockReferences";
import { toBlockReferenceRequest } from "../utilities/toBlockReferenceRequest";

/**
 * Demo component to visualize block reference resolution.
 * Shows the transformation between API format and UI format.
 */
function BlockReferenceDemo({
	apiValues,
	blockDocumentReferences,
}: {
	apiValues: SchemaFormValues;
	blockDocumentReferences: Record<string, unknown>;
}) {
	const [currentFormat, setCurrentFormat] = useState<"api" | "ui">("api");

	// Resolve API format to UI format
	const uiValues = resolveBlockReferences(apiValues, blockDocumentReferences);

	// Convert UI format back to API format
	const backToApiValues = toBlockReferenceRequest(uiValues);

	const displayValues = currentFormat === "api" ? apiValues : uiValues;

	return (
		<div className="grid grid-cols-2 gap-4 p-4 size-full">
			<div className="flex flex-col gap-4">
				<Typography variant="h2">Block Reference Resolution Demo</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					This demonstrates how block document references are transformed
					between API format and UI format.
				</Typography>

				<div className="flex gap-2">
					<Button
						variant={currentFormat === "api" ? "default" : "outline"}
						onClick={() => setCurrentFormat("api")}
					>
						API Format (Input)
					</Button>
					<Button
						variant={currentFormat === "ui" ? "default" : "outline"}
						onClick={() => setCurrentFormat("ui")}
					>
						UI Format (Resolved)
					</Button>
				</div>

				<Typography variant="h3">
					Current Values ({currentFormat.toUpperCase()})
				</Typography>
				<JsonInput value={JSON.stringify(displayValues, null, 2)} />
			</div>

			<div className="flex flex-col gap-4">
				<Typography variant="h2">Transformation Details</Typography>

				<Typography variant="h3">1. API Response (Input)</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					Block references come from the API in this format with $ref containing
					block_document_id
				</Typography>
				<JsonInput value={JSON.stringify(apiValues, null, 2)} />

				<Typography variant="h3">2. Block Document References</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					The API also provides metadata about each referenced block
				</Typography>
				<JsonInput value={JSON.stringify(blockDocumentReferences, null, 2)} />

				<Typography variant="h3">3. Resolved UI Values</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					After resolveBlockReferences(), values are in UI format with
					blockTypeSlug and blockDocumentId
				</Typography>
				<JsonInput value={JSON.stringify(uiValues, null, 2)} />

				<Typography variant="h3">4. Back to API Format</Typography>
				<Typography variant="bodySmall" className="text-muted-foreground">
					toBlockReferenceRequest() converts UI format back to API format for
					submission
				</Typography>
				<JsonInput value={JSON.stringify(backToApiValues, null, 2)} />
			</div>
		</div>
	);
}

const meta = {
	title: "Components/SchemaForm/BlockReferences",
	component: BlockReferenceDemo,
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof BlockReferenceDemo>;

export default meta;

type Story = StoryObj<typeof meta>;

export const SimpleBlockReference: Story = {
	args: {
		apiValues: {
			credentials: { $ref: { block_document_id: "uuid-123" } },
		},
		blockDocumentReferences: {
			credentials: {
				block_document: {
					id: "uuid-123",
					name: "my-aws-creds",
					block_type: { slug: "aws-credentials" },
				},
			},
		},
	},
};
SimpleBlockReference.storyName = "Simple Block Reference";

export const MultipleBlockReferences: Story = {
	args: {
		apiValues: {
			aws_credentials: { $ref: { block_document_id: "uuid-aws" } },
			gcp_credentials: { $ref: { block_document_id: "uuid-gcp" } },
			slack_webhook: { $ref: { block_document_id: "uuid-slack" } },
		},
		blockDocumentReferences: {
			aws_credentials: {
				block_document: {
					id: "uuid-aws",
					name: "production-aws",
					block_type: { slug: "aws-credentials" },
				},
			},
			gcp_credentials: {
				block_document: {
					id: "uuid-gcp",
					name: "production-gcp",
					block_type: { slug: "gcp-credentials" },
				},
			},
			slack_webhook: {
				block_document: {
					id: "uuid-slack",
					name: "alerts-channel",
					block_type: { slug: "slack-webhook" },
				},
			},
		},
	},
};
MultipleBlockReferences.storyName = "Multiple Block References";

export const MixedValues: Story = {
	args: {
		apiValues: {
			name: "my-deployment",
			timeout: 3600,
			credentials: { $ref: { block_document_id: "uuid-123" } },
			tags: ["production", "critical"],
		},
		blockDocumentReferences: {
			credentials: {
				block_document: {
					id: "uuid-123",
					name: "my-aws-creds",
					block_type: { slug: "aws-credentials" },
				},
			},
		},
	},
};
MixedValues.storyName = "Mixed Values (Block + Primitives)";

export const NestedBlockReferences: Story = {
	args: {
		apiValues: {
			config: {
				storage: { $ref: { block_document_id: "uuid-s3" } },
				timeout: 30,
			},
		},
		blockDocumentReferences: {
			storage: {
				block_document: {
					id: "uuid-s3",
					name: "my-s3-bucket",
					block_type: { slug: "s3-bucket" },
				},
			},
		},
	},
};
NestedBlockReferences.storyName = "Nested Block References";

export const NoBlockReferences: Story = {
	args: {
		apiValues: {
			name: "simple-config",
			count: 42,
			enabled: true,
		},
		blockDocumentReferences: {},
	},
};
NoBlockReferences.storyName = "No Block References";
