import clsx from "clsx";
import { CronExpressionParser } from "cron-parser";
import cronstrue from "cronstrue";
import { useState } from "react";
import { Input, type InputProps } from "@/components/ui/input";
import { Typography } from "@/components/ui/typography";

const verifyCronValue = (cronValue: string) => {
	let description = "";
	let isCronValid = false;
	try {
		CronExpressionParser.parse(cronValue);
		description = cronstrue.toString(cronValue);
		isCronValid = true;
	} catch {
		isCronValid = false;
		description = "Invalid expression";
	}
	return {
		description,
		isCronValid,
	};
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
			<Typography
				variant="bodySmall"
				className={clsx(isCronValid ? "text-muted-foreground" : "text-red-500")}
			>
				{description}
			</Typography>
		</div>
	);
};
