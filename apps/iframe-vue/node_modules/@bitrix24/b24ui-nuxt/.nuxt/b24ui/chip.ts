const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-primary-warning",
  "air-secondary",
  "air-secondary-accent",
  "air-secondary-accent-1",
  "air-tertiary",
  "default",
  "danger",
  "success",
  "warning",
  "primary",
  "secondary",
  "collab",
  "ai"
] as const

const size = [
  "sm",
  "md",
  "lg"
] as const

const position = [
  "top-right",
  "bottom-right",
  "top-left",
  "bottom-left"
] as const

export default {
  "slots": {
    "root": "relative shrink-0 isolate inline-flex items-center justify-center",
    "base": "ui-counter__scope --air font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-medium) select-none relative min-w-(--ui-counter-size) h-(--ui-counter-size) py-0 px-(--ui-counter-inline-space) inline-flex items-center justify-center bg-(--b24ui-background) rounded-(--ui-counter-current-size) ring-(length:--b24ui-border-width) ring-(--b24ui-border-color) text-center align-middle text-(length:--ui-counter-font-size) text-(--b24ui-color) leading-(--ui-counter-current-size) overflow-hidden z-1 text-nowrap",
    "trailingIcon": "size-(--ui-counter-size) text-inherit text-(length:--ui-counter-symbol-font-size) opacity-96 tracking-(--ui-letter-spacing-xl) me-(--ui-counter-symbol-compensation) empty:me-[0]"
  },
  "variants": {
    "color": {
      "air-primary": {
        "base": "style-filled"
      },
      "air-primary-success": {
        "base": "style-filled-success"
      },
      "air-primary-alert": {
        "base": "style-filled-alert"
      },
      "air-primary-copilot": {
        "base": "style-filled-copilot"
      },
      "air-primary-warning": {
        "base": "style-filled-warning"
      },
      "air-secondary": {
        "base": "style-tinted-no-accent-1"
      },
      "air-secondary-accent": {
        "base": "style-filled-no-accent"
      },
      "air-secondary-accent-1": {
        "base": "style-filled-no-accent-inverted edge-dark:text-(--ui-color-g-content-grey-2)"
      },
      "air-tertiary": {
        "base": "style-outline-no-accent"
      },
      "default": {
        "base": "style-old-default"
      },
      "danger": {
        "base": "style-old-danger"
      },
      "success": {
        "base": "style-old-success"
      },
      "warning": {
        "base": "style-old-warning"
      },
      "primary": {
        "base": "style-old-primary"
      },
      "secondary": {
        "base": "style-old-secondary"
      },
      "collab": {
        "base": "style-old-collab"
      },
      "ai": {
        "base": "style-old-ai"
      }
    },
    "size": {
      "sm": "ui-counter-sm font-(--ui-font-weight-regular)",
      "md": "ui-counter-md",
      "lg": "ui-counter-lg"
    },
    "position": {
      "top-right": "top-0 right-0",
      "bottom-right": "bottom-0 right-0",
      "top-left": "top-0 left-0",
      "bottom-left": "bottom-0 left-0"
    },
    "inverted": {
      "true": "",
      "false": ""
    },
    "inset": {
      "false": ""
    },
    "standalone": {
      "true": "",
      "false": "absolute"
    },
    "hideZero": {
      "true": {
        "base": "data-[value=0]:hidden"
      }
    },
    "oneDigit": {
      "true": {
        "base": "px-0"
      }
    }
  },
  "compoundVariants": [
    {
      "position": "top-right" as typeof position[number],
      "inset": false,
      "standalone": false,
      "class": "-translate-y-1/2 translate-x-1/2 transform"
    },
    {
      "position": "bottom-right" as typeof position[number],
      "inset": false,
      "standalone": false,
      "class": "translate-y-1/2 translate-x-1/2 transform"
    },
    {
      "position": "top-left" as typeof position[number],
      "inset": false,
      "standalone": false,
      "class": "-translate-y-1/2 -translate-x-1/2 transform"
    },
    {
      "position": "bottom-left" as typeof position[number],
      "inset": false,
      "standalone": false,
      "class": "translate-y-1/2 -translate-x-1/2 transform"
    },
    {
      "position": "top-right" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "xs" as typeof size[number],
        "sm" as typeof size[number],
        "md" as typeof size[number],
        "lg" as typeof size[number],
        "xl" as typeof size[number],
        "2xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "-translate-y-1/3 translate-x-1/3 transform"
    },
    {
      "position": "top-right" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "3xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "translate-y-0 translate-x-0 transform"
    },
    {
      "position": "bottom-right" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "xs" as typeof size[number],
        "sm" as typeof size[number],
        "md" as typeof size[number],
        "lg" as typeof size[number],
        "xl" as typeof size[number],
        "2xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "translate-y-1/3 translate-x-1/3 transform"
    },
    {
      "position": "bottom-right" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "3xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "translate-y-0 translate-x-0 transform"
    },
    {
      "position": "top-left" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "xs" as typeof size[number],
        "sm" as typeof size[number],
        "md" as typeof size[number],
        "lg" as typeof size[number],
        "xl" as typeof size[number],
        "2xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "-translate-y-1/3 -translate-x-1/3 transform"
    },
    {
      "position": "top-left" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "3xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "-translate-y-0 -translate-x-0 transform"
    },
    {
      "position": "bottom-left" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "xs" as typeof size[number],
        "sm" as typeof size[number],
        "md" as typeof size[number],
        "lg" as typeof size[number],
        "xl" as typeof size[number],
        "2xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "translate-y-1/3 -translate-x-1/3 transform"
    },
    {
      "position": "bottom-left" as typeof position[number],
      "size": [
        "2xs" as typeof size[number],
        "3xl" as typeof size[number]
      ],
      "inset": true,
      "standalone": false,
      "class": "translate-y-0 -translate-x-0 transform"
    },
    {
      "inverted": true,
      "color": "air-primary" as typeof color[number],
      "class": {
        "base": "style-filled-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-success" as typeof color[number],
      "class": {
        "base": "style-filled-success-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-alert" as typeof color[number],
      "class": {
        "base": "style-filled-alert-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-copilot" as typeof color[number],
      "class": {
        "base": "style-filled-copilot-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-warning" as typeof color[number],
      "class": {
        "base": "style-filled-warning-inverted"
      }
    }
  ],
  "defaultVariants": {
    "size": "sm" as typeof size[number],
    "color": "air-primary-alert" as typeof color[number],
    "position": "top-right" as typeof position[number],
    "inverted": false
  }
}