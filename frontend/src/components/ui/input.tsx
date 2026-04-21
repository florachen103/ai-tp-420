import { forwardRef, InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "h-12 px-4 w-full rounded-lg border border-gray-200 bg-white text-base leading-relaxed",
        "focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500",
        "placeholder:text-gray-400",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "min-h-[110px] px-4 py-3 w-full rounded-lg border border-gray-200 bg-white text-base leading-relaxed",
        "focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500",
        "placeholder:text-gray-400 resize-y",
        className
      )}
      {...props}
    />
  )
);
Textarea.displayName = "Textarea";
