# Adding Icons

Import new icon from https://lucide.dev/icons/ in `./constants` and add entry alphabetically in `ICONS`

Use the named import that **excludes** `Icon` suffix. eg: `BanIcon` VS `Ban`

```ts
/** @/components/ui/icons/constants.ts */
import {
	AlignVerticalJustifyStart,
	Ban,
	Check, // <---- New Icon to add
	ChevronDown,
} from "lucide-react";

export const ICONS = {
	AlignVerticalJustifyStart,
	Ban,
	Check, // <---- New Icon to add
	ChevronDown,
} as const;
```