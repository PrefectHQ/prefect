import { Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/utils";

type CodeBannerProps = {
	command: string;
	title: string;
	subtitle: string;
	className?: string;
};

export const CodeBanner = ({
	command,
	title,
	subtitle,
	className,
}: CodeBannerProps) => {
	const [copying, setCopying] = useState(false);

	const handleCopy = async () => {
		if (copying) return;

		setCopying(true);
		try {
			await navigator.clipboard.writeText(command);
			toast.success("Command copied to clipboard");
		} catch {
			toast.error("Failed to copy command");
		} finally {
			setCopying(false);
		}
	};

	return (
		<div className={cn("space-y-4", className)}>
			{/* Title and subtitle above terminal */}
			<div className="text-center">
				<h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
				<p className="text-gray-600 text-sm">{subtitle}</p>
			</div>

			{/* Terminal window */}
			<div className="bg-gray-100 border border-gray-300 rounded-lg shadow-sm overflow-hidden">
				{/* macOS-style window header */}
				<div className="bg-gray-200 border-b border-gray-300 px-3 py-2 flex items-center space-x-2">
					<div className="flex space-x-1">
						<div className="w-3 h-3 bg-red-500 rounded-full" />
						<div className="w-3 h-3 bg-yellow-500 rounded-full" />
						<div className="w-3 h-3 bg-green-500 rounded-full" />
					</div>
					<Button
						variant="ghost"
						size="sm"
						// eslint-disable-next-line @typescript-eslint/no-misused-promises
						onClick={handleCopy}
						disabled={copying}
						className="ml-auto text-gray-600 hover:text-gray-800 hover:bg-gray-300 h-6 w-6 p-0"
					>
						<Copy className="h-4 w-4" />
					</Button>
				</div>

				{/* Terminal content */}
				<div className="bg-gray-800 px-4 py-2">
					<p className="py-1">
						<code className="font-mono text-sm text-gray-300 select-all">
							{command}
						</code>
						<span className="ml-1 -mb-1 inline-block w-[7px] h-[18px] bg-gray-400 terminal-cursor" />
					</p>
				</div>
			</div>
		</div>
	);
};
