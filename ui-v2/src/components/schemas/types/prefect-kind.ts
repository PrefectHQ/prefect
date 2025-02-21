import { createTuple } from "@/utils/utils";

export const { values: prefectKinds, isValue: isPrefectKind } = createTuple([
	null,
	"json",
	"jinja",
]);

export type PrefectKind = (typeof prefectKinds)[number];

export function getPrefectKindLabel(kind: PrefectKind) {
	switch (kind) {
		case null:
			return "Use Form Input";
		case "json":
			return "Use JSON Input";
		case "jinja":
			return "Use Jinja Template";
		default:
			// eslint-disable-next-line @typescript-eslint/restrict-template-expressions
			throw new Error(`Unknown prefect kind: ${kind satisfies never}`);
	}
}
