import { randAnimal, randProductAdjective } from "@ngneat/falso";

export const createFakeFlowRunName = () =>
	`${randProductAdjective()}-${randAnimal({ maxCharCount: 6 })}`;
