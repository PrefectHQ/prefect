import clsx from "clsx";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Input, type InputProps } from "@/components/ui/input";
import { createFakeFlowRunName } from "./create-fake-flow-run-name";

type FlowRunNameInputProps = InputProps & {
	onClickGenerate: (value: string) => void;
};
export const FlowRunNameInput = ({
	onClickGenerate,
	...inputProps
}: FlowRunNameInputProps) => {
	return (
		<div className="flex gap-2 items-center">
			<Input {...inputProps} className={clsx("w-full", inputProps.className)} />
			<Button
				arial-label="generate flow name"
				variant="ghost"
				size="icon"
				onClick={() => onClickGenerate(createFakeFlowRunName())}
				type="button"
			>
				<Icon id="RefreshCw" className="size-4" />
			</Button>
		</div>
	);
};
