"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-w-fit shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl text-center leading-none font-medium transition duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 select-none",
  {
    variants: {
      variant: {
        primary: "bg-brand-500 text-white shadow-sm shadow-brand-500/20 hover:bg-brand-600 font-medium",
        secondary:
          "border border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900",
        ghost: "text-gray-600 hover:bg-gray-100",
        danger: "bg-red-500 text-white hover:bg-red-600",
      },
      size: {
        sm: "h-9 px-3.5 text-sm sm:h-10 sm:px-4",
        md: "h-11 px-4 text-sm sm:h-12 sm:px-5 sm:text-[15px]",
        lg: "h-12 px-5 text-base sm:h-14 sm:px-7 sm:text-lg",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
);
Button.displayName = "Button";
