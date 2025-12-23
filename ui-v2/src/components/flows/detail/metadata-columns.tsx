import type { ColumnDef } from "@tanstack/react-table";
import type { components } from "@/api/prefect";
import { FormattedDate } from "@/components/ui/formatted-date";

type Flow = components["schemas"]["Flow"];
type FlowMetadata = { attribute: string; value: string | string[] | null };

export const columns: ColumnDef<FlowMetadata>[] = [
	{
		accessorKey: "attribute",
		header: "Attribute",
		cell: ({ row }) => (
			<span className="font-medium">{row.original.attribute}</span>
		),
	},
	{
		accessorKey: "value",
		header: "Value",
		cell: ({ row }) => {
			const { attribute, value } = row.original;

			// Format date fields
			if ((attribute === "Created" || attribute === "Updated") && value) {
				return <FormattedDate date={value as string} format="absolute" />;
			}

			// Handle arrays (like Tags)
			if (Array.isArray(value)) {
				return value.join(", ");
			}

			return value;
		},
	},
];

export const getFlowMetadata = (flow: Flow): FlowMetadata[] => [
	{ attribute: "ID", value: flow.id || null },
	{ attribute: "Name", value: flow.name },
	{ attribute: "Created", value: flow.created || null },
	{ attribute: "Updated", value: flow.updated || null },
	{ attribute: "Tags", value: flow.tags || [] },
];
