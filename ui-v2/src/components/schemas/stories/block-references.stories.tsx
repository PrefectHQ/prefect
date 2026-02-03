import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import type { components } from "@/api/prefect";
import { Button } from "@/components/ui/button";
import { LazyJsonInput as JsonInput } from "@/components/ui/json-input-lazy";
import type { SchemaFormValues } from "../types/values";
import { resolveBlockReferences } from "../utilities/resolveBlockReferences";
import { toBlockReferenceRequest } from "../utilities/toBlockReferenceRequest";

type BlockDocumentReferences =
	components["schemas"]["BlockDocument"]["block_document_references"];

/**
 * Demo component to visualize block reference resolution.
 * Shows the transformation between API format and UI format.
 */
function BlockReferenceDemo({
	apiValues,
	blockDocumentReferences,
}: {
	apiValues: SchemaFormValues;
	blockDocumentReferences: BlockDocumentReferences;
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
				<h2 className="text-3xl font-semibold tracking-tight">
					Block Reference Resolution Demo
				</h2>
				<p className="text-sm text-muted-foreground">
					This demonstrates how block document references are transformed
					between API format and UI format.
				</p>

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

				<h3 className="text-2xl font-semibold tracking-tight">
					Current Values ({currentFormat.toUpperCase()})
				</h3>
				<JsonInput value={JSON.stringify(displayValues, null, 2)} />
			</div>

			<div className="flex flex-col gap-4">
				<h2 className="text-3xl font-semibold tracking-tight">
					Transformation Details
				</h2>

				<h3 className="text-2xl font-semibold tracking-tight">
					1. API Response (Input)
				</h3>
				<p className="text-sm text-muted-foreground">
					Block references come from the API in this format with $ref containing
					block_document_id
				</p>
				<JsonInput value={JSON.stringify(apiValues, null, 2)} />

				<h3 className="text-2xl font-semibold tracking-tight">
					2. Block Document References
				</h3>
				<p className="text-sm text-muted-foreground">
					The API also provides metadata about each referenced block
				</p>
				<JsonInput value={JSON.stringify(blockDocumentReferences, null, 2)} />

				<h3 className="text-2xl font-semibold tracking-tight">
					3. Resolved UI Values
				</h3>
				<p className="text-sm text-muted-foreground">
					After resolveBlockReferences(), values are in UI format with
					blockTypeSlug and blockDocumentId
				</p>
				<JsonInput value={JSON.stringify(uiValues, null, 2)} />

				<h3 className="text-2xl font-semibold tracking-tight">
					4. Back to API Format
				</h3>
				<p className="text-sm text-muted-foreground">
					toBlockReferenceRequest() converts UI format back to API format for
					submission
				</p>
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
