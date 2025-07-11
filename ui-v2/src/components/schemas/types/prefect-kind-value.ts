import { isDefined, isRecord, isString } from "../utilities/guards";
import { isPrefectKind, type PrefectKind } from "./prefect-kind";

type BasePrefectKindValue<
	TKind extends PrefectKind = PrefectKind,
	TRest extends Record<string, unknown> = Record<string, unknown>,
> = {
	__prefect_kind: TKind;
} & TRest;

export type PrefectKindValue = PrefectKindValueJinja | PrefectKindValueJson;

export function getPrefectKindFromValue(value: unknown): PrefectKind | null {
	if (isPrefectKindValue(value)) {
		return value.__prefect_kind;
	}

	return null;
}

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

export type PrefectKindValueJson = BasePrefectKindValue<
	"json",
	{
		value?: string;
	}
>;

export function isPrefectKindValueJson(
	value: unknown,
): value is PrefectKindValueJson {
	return (
		isPrefectKindValue(value, "json") &&
		(isString(value.value) || !isDefined(value.value))
	);
}

export type PrefectKindValueJinja = BasePrefectKindValue<
	"jinja",
	{
		template?: string;
	}
>;

export function isPrefectKindValueJinja(
	value: unknown,
): value is PrefectKindValueJinja {
	return isPrefectKindValue(value, "jinja") && isString(value.template);
}
