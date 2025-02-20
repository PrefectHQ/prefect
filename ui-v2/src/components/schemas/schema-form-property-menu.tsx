import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { ReferenceObject, SchemaObject } from "openapi-typescript";
import { ReactNode, useMemo } from "react";
import {
	PrefectKind,
	getPrefectKindLabel,
	prefectKinds,
} from "./types/prefect-kind";
import { getPrefectKindFromValue } from "./types/prefect-kind-value";
import { useSchemaFormContext } from "./use-schema-form-context";
import { convertValueToPrefectKind } from "./utilities/convertValueToPrefectKind";

export type SchemaFormPropertyMenuProps = {
	value: unknown;
	onValueChange: (value: unknown) => void;
	property: SchemaObject | ReferenceObject | (SchemaObject | ReferenceObject)[];
	children?: ReactNode;
};

export const SchemaFormPropertyMenu = ({
	value,
	onValueChange,
	property,
	children,
}: SchemaFormPropertyMenuProps) => {
	const { schema, kinds } = useSchemaFormContext();

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
			(kind) => kind !== current && (kinds.includes(kind) || kind === null),
		);
	}, [value, kinds]);

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" className="h-8 w-8 p-0">
					<span className="sr-only">Open menu</span>
					<Icon id="MoreVertical" className="h-4 w-4" />
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
