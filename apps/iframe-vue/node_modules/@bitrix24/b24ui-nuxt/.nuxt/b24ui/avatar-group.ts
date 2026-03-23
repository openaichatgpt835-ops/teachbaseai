const size = [
  "3xs",
  "2xs",
  "xs",
  "sm",
  "md",
  "lg",
  "xl",
  "2xl",
  "3xl"
] as const

export default {
  "slots": {
    "root": "inline-flex justify-end",
    "base": "relative rounded-full last:me-0"
  },
  "variants": {
    "size": {
      "3xs": {
        "base": "-me-0.5"
      },
      "2xs": {
        "base": "-me-0.5"
      },
      "xs": {
        "base": "-me-0.5"
      },
      "sm": {
        "base": "-me-1.5"
      },
      "md": {
        "base": "-me-1.5"
      },
      "lg": {
        "base": "-me-1.5"
      },
      "xl": {
        "base": "-me-2"
      },
      "2xl": {
        "base": "-me-2"
      },
      "3xl": {
        "base": "-me-2"
      }
    }
  },
  "defaultVariants": {
    "size": "md" as typeof size[number]
  }
}