import { isDefined, isRecord, isString } from "../utilities/guards";
import { PrefectKind, isPrefectKind } from "./prefect-kind";

type BasePrefectKindValue<
	TKind extends PrefectKind = PrefectKind,
	TRest extends Record<string, unknown> = Record<string, unknown>,
> = {
	__prefect_kind: TKind;
} & TRest;

export type PrefectKindValue =
	| PrefectKindNull
	| PrefectKindJinja
	| PrefectKindJson;

export function isPrefectKindValue<T extends PrefectKind = PrefectKind>(
	value: unknown,
	kind?: T,
): value is PrefectKindValue & { __prefect_kind: T } {
	const isKindObject = isRecord(value) && isPrefectKind(value.__prefect_kind);

	if (!isKindObject) {
		return false;
	}

	if (isPrefectKind(kind)) {
		return value.__prefect_kind === kind;
	}

	return true;
}

export type PrefectKindNull = BasePrefectKindValue<
	"none",
	{
		value: unknown;
	}
>;

export function isPrefectKindNull(value: unknown): value is PrefectKindNull {
	return isPrefectKindValue(value, "none") && "value" in value;
}

export type PrefectKindJson = BasePrefectKindValue<
	"json",
	{
		value?: string;
	}
>;

export function isPrefectKindJson(value: unknown): value is PrefectKindJson {
	return (
		isPrefectKindValue(value, "json") &&
		(isString(value.value) || !isDefined(value.value))
	);
}

export type PrefectKindJinja = BasePrefectKindValue<
	"jinja",
	{
		template?: string;
	}
>;

export function isPrefectKindJinja(value: unknown): value is PrefectKindJinja {
	return isPrefectKindValue(value, "jinja") && isString(value.template);
}
