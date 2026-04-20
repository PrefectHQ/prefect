import clsx from "clsx";
import { CronExpressionParser } from "cron-parser";
import cronstrue from "cronstrue";
import { useState } from "react";
import { Input, type InputProps } from "@/components/ui/input";

const verifyCronValue = (cronValue: string) => {
	try {
		CronExpressionParser.parse(cronValue);
		return {
			description: cronstrue.toString(cronValue),
			isCronValid: true,
		};
	} catch {
		return {
			description: "Invalid expression",
			isCronValid: false,
		};
	}
};

export type CronInputProps = InputProps;
export const CronInput = ({ onChange, ...props }: CronInputProps) => {
	const [description, setDescription] = useState(
		verifyCronValue(String(props.value)).description,
	);
	const [isCronValid, setIsCronValid] = useState(
		verifyCronValue(String(props.value)).isCronValid,
	);

	const handleChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
		if (onChange) {
			onChange(event);
			const { description, isCronValid } = verifyCronValue(event.target.value);
			setDescription(description);
			setIsCronValid(isCronValid);
		}
	};

	return (
		<div className="flex flex-col gap-1">
			<Input {...props} onChange={handleChange} />
			<p
				className={clsx(
					"text-sm",
					isCronValid ? "text-muted-foreground" : "text-destructive",
				)}
			>
				{description}
			</p>
		</div>
	);
};
