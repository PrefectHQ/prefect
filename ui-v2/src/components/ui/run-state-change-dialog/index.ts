import { RunStateChangeDialog } from "./run-state-change-dialog";

export type RunStateFormValues = {
	state: string;
	message?: string | null;
	force?: boolean;
};

export { RunStateChangeDialog };
