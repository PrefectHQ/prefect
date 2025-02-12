import { createTuple } from "@/utils/utils";

export const { values: prefectKinds, isValue: isPrefectKind } = createTuple([
	"none",
	"json",
	"jinja",
	"workspace_variable",
]);

export type PrefectKind = (typeof prefectKinds)[number];
