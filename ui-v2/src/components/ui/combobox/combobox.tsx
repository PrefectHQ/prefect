import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import { Icon } from "@/components/ui/icons";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { createContext, use, useState } from "react";

const ComboboxContext = createContext<{
	open: boolean;
	setOpen: (open: boolean) => void;
} | null>(null);

const Combobox = ({ children }: { children: React.ReactNode }) => {
	const [open, setOpen] = useState(false);
	return (
		<ComboboxContext.Provider value={{ open, setOpen }}>
			<Popover open={open} onOpenChange={setOpen}>
				{children}
			</Popover>
		</ComboboxContext.Provider>
	);
};

const ComboboxTrigger = ({
	selected = false,
	children,
}: { selected?: boolean; withForm?: boolean; children: React.ReactNode }) => {
	const comboboxCtx = use(ComboboxContext);
	if (!comboboxCtx) {
		throw new Error("'ComboboxTrigger' must be a child of `Combobox`");
	}
	const { open } = comboboxCtx;

	return (
		<PopoverTrigger asChild className="w-full">
			<Button
				aria-expanded={open}
				variant="outline"
				role="combobox"
				className={cn(
					"w-full justify-between",
					selected && "text-muted-foreground",
				)}
			>
				{children}
				<Icon id="ChevronsUpDown" className="h-4 w-4 opacity-50" />
			</Button>
		</PopoverTrigger>
	);
};

const ComboboxContent = ({
	filter,
	children,
}: {
	filter?: (value: string, search: string, keywords?: string[]) => number;
	children: React.ReactNode;
}) => {
	return (
		<PopoverContent fullWidth>
			<Command filter={filter}>{children}</Command>
		</PopoverContent>
	);
};

const ComboboxCommandInput = ({ placeholder }: { placeholder?: string }) => {
	return <CommandInput placeholder={placeholder} className="h-9" />;
};

const ComboboxCommandList = ({ children }: { children: React.ReactNode }) => {
	return <CommandList>{children}</CommandList>;
};

const ComboboxCommandEmtpy = ({ children }: { children: React.ReactNode }) => {
	return <CommandEmpty>{children}</CommandEmpty>;
};

const ComboboxCommandGroup = ({ children }: { children: React.ReactNode }) => {
	return <CommandGroup>{children}</CommandGroup>;
};

const ComboboxCommandItem = ({
	onSelect,
	selected = false,
	value,
	children,
}: {
	onSelect: (value: string) => void;
	selected?: boolean;
	value: string;
	children: React.ReactNode;
}) => {
	const comboboxCtx = use(ComboboxContext);
	if (!comboboxCtx) {
		throw new Error("'ComboboxCommandItem' must be a child of `Combobox`");
	}
	const { setOpen } = comboboxCtx;

	return (
		<CommandItem
			value={value}
			onSelect={() => {
				setOpen(false);
				onSelect(value);
			}}
		>
			{children}
			<Icon
				id="Check"
				className={cn("ml-auto", selected ? "opacity-100" : "opacity-0")}
			/>
		</CommandItem>
	);
};

export {
	Combobox,
	ComboboxTrigger,
	ComboboxContent,
	ComboboxCommandInput,
	ComboboxCommandList,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandItem,
};
