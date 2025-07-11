import type { ReferenceObject, SchemaObject } from "openapi-typescript";
import { type ReactNode, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import {
	getPrefectKindLabel,
	type PrefectKind,
	prefectKinds,
} from "./types/prefect-kind";
import { getPrefectKindFromValue } from "./types/prefect-kind-value";
import { useSchemaFormContext } from "./use-schema-form-context";
import { convertValueToPrefectKind } from "./utilities/convertValueToPrefectKind";

export type SchemaFormPropertyMenuProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	disableKinds?: boolean;
	children?: ReactNode;
};

export const SchemaFormPropertyMenu = ({
	value,
	onValueChange,
	property,
	children,
	disableKinds,
}: SchemaFormPropertyMenuProps) => {
	const { schema, kinds } = useSchemaFormContext();
	const [open, setOpen] = useState(false);

	function convertValueKind(kind: PrefectKind) {
		const newValue = convertValueToPrefectKind({
			value,
			property,
			schema,
			to: kind,
		});

		onValueChange(newValue);
	}

	const kindOptions = useMemo(() => {
		const current = getPrefectKindFromValue(value);

		return prefectKinds.filter(
			(kind) =>
				kind !== current &&
				(kinds.includes(kind) || kind === null) &&
				!disableKinds,
		);
	}, [value, kinds, disableKinds]);

	return (
		<DropdownMenu open={open} onOpenChange={setOpen}>
			<DropdownMenuTrigger asChild>
				<Button
					variant="ghost"
					data-open={open}
					className="h-8 w-8 p-0 opacity-0 transition-opacity disabled:!opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 data-[open=true]:opacity-100"
				>
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="size-4" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				{kindOptions.map((kind) => (
					<DropdownMenuItem key={kind} onClick={() => convertValueKind(kind)}>
						{getPrefectKindLabel(kind)}
					</DropdownMenuItem>
				))}

				<DropdownMenuSeparator />

				{children}
			</DropdownMenuContent>
		</DropdownMenu>
	);
};
