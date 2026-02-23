import clsx from "clsx";
import { Fragment, useMemo } from "react";
import { Card } from "@/components/ui/card";

const INTERNAL_FIELDS = new Set(["__prefect_kind"]);

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function filterInternalFields(
	obj: Record<string, unknown>,
): Record<string, unknown> {
	const filtered: Record<string, unknown> = {};
	for (const [key, val] of Object.entries(obj)) {
		if (INTERNAL_FIELDS.has(key)) {
			continue;
		}
		if (isRecord(val)) {
			filtered[key] = filterInternalFields(val);
		} else {
			filtered[key] = val;
		}
	}
	return filtered;
}

function formatLabel(key: string): string {
	return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ObjectValueCard({ value }: { value: Record<string, unknown> }) {
	const filtered = filterInternalFields(value);
	const entries = Object.entries(filtered);
	if (entries.length === 0) {
		return <span className="text-muted-foreground text-base">None</span>;
	}
	return (
		<Card className="p-3 flex flex-col gap-2">
			{entries.map(([key, val]) => (
				<div key={key} className="flex flex-col gap-1">
					<span className="text-muted-foreground text-sm">
						{formatLabel(key)}
					</span>
					{isRecord(val) ? (
						<ObjectValueCard value={val} />
					) : (
						<span className="text-base">{formatDisplayValue(val)}</span>
					)}
				</div>
			))}
		</Card>
	);
}

function formatDisplayValue(value: unknown): string {
	if (value === null || value === undefined) {
		return "None";
	}
	if (typeof value === "string") {
		return value;
	}
	if (typeof value === "boolean" || typeof value === "number") {
		return String(value);
	}
	if (Array.isArray(value)) {
		return JSON.stringify(value);
	}
	return JSON.stringify(value);
}

type FieldValue = {
	label: string;
	raw: unknown;
};

type BlockDocumentSchemaProperties = {
	data: { [key: string]: unknown };
	fields: { [key: string]: unknown };
};
export function BlockDocumentSchemaProperties({
	data,
	fields,
}: BlockDocumentSchemaProperties) {
	const fieldValues = useMemo(() => {
		let properties: { [key: string]: unknown } = {};
		if ("properties" in fields) {
			properties = fields.properties as { [key: string]: unknown };
		}

		return Object.keys(properties).map((property): FieldValue => {
			let label = property;
			const field = properties[property] as {
				[key: string]: unknown;
				title: string;
			};
			if (field.title) {
				label = field.title;
			}

			return {
				label,
				raw: data[property] ?? null,
			};
		});
	}, [data, fields]);

	return (
		<dl className="flex flex-col gap-2 p-2 text-xs">
			{fieldValues.map(({ label, raw }) => (
				<Fragment key={label}>
					<dt className="text-muted-foreground text-sm">{label}</dt>
					<dd
						className={clsx(
							"text-base",
							raw == null && "text-muted-foreground",
						)}
					>
						{isRecord(raw) ? (
							<ObjectValueCard value={raw} />
						) : (
							formatDisplayValue(raw)
						)}
					</dd>
				</Fragment>
			))}
		</dl>
	);
}
