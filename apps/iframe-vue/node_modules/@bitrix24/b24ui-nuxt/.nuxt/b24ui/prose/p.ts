const accent = [
  "default",
  "accent",
  "accent-more",
  "less",
  "less-more"
] as const

export default {
  "slots": {
    "base": "mb-2 last:mb-0 leading-relaxed text-pretty"
  },
  "variants": {
    "small": {
      "true": "text-sm",
      "false": "text-base"
    },
    "accent": {
      "default": "text-(--b24ui-typography-label-color)",
      "accent": "text-(--ui-color-accent-brand-blue)" as typeof accent[number],
      "accent-more": "text-(--ui-color-accent-soft-element-blue)",
      "less": "text-(--b24ui-typography-description-color)",
      "less-more": "text-(--ui-color-design-plain-na-content-secondary)"
    }
  },
  "defaultVariants": {
    "small": false,
    "accent": "default" as typeof accent[number]
  }
}