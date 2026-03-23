const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-primary-warning",
  "air-secondary",
  "air-secondary-alert",
  "air-secondary-accent",
  "air-secondary-accent-1",
  "air-secondary-accent-2",
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
  "md"
] as const

export default {
  "slots": {
    "root": "relative overflow-hidden w-full flex text-(--b24ui-color) bg-(--b24ui-background) border-(--b24ui-border-color) border-(length:--b24ui-border-width) rounded-(--ui-border-radius-md)",
    "wrapper": "min-w-0 flex-1 flex flex-col font-[family-name:var(--ui-font-family-primary)]",
    "title": "font-bold",
    "description": "",
    "icon": "shrink-0 size-6",
    "avatar": "shrink-0",
    "avatarSize": "",
    "actions": "flex flex-wrap gap-1.5 shrink-0",
    "close": "p-0"
  },
  "variants": {
    "color": {
      "air-primary": {
        "root": "style-filled"
      },
      "air-primary-success": {
        "root": "style-filled-success"
      },
      "air-primary-alert": {
        "root": "style-filled-alert"
      },
      "air-primary-copilot": {
        "root": "style-filled-copilot"
      },
      "air-primary-warning": {
        "root": "style-filled-warning"
      },
      "air-secondary": {
        "root": "style-tinted"
      },
      "air-secondary-alert": {
        "root": "style-tinted-alert"
      },
      "air-secondary-accent": {
        "root": "style-outline"
      },
      "air-secondary-accent-1": {
        "root": "style-outline-accent-1"
      },
      "air-secondary-accent-2": {
        "root": "style-outline-accent-2"
      },
      "air-tertiary": {
        "root": "style-outline-no-accent"
      },
      "default": {
        "root": "style-old-default"
      },
      "danger": {
        "root": "style-old-danger"
      },
      "success": {
        "root": "style-old-success"
      },
      "warning": {
        "root": "style-old-warning"
      },
      "primary": {
        "root": "style-old-primary"
      },
      "secondary": {
        "root": "style-old-secondary"
      },
      "collab": {
        "root": "style-old-collab"
      },
      "ai": {
        "root": "style-old-ai"
      }
    },
    "size": {
      "sm": {
        "root": "py-xs ps-sm pe-xs gap-2",
        "title": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-lg)",
        "description": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-lg)",
        "avatarSize": "md"
      },
      "md": {
        "root": "py-md ps-md pe-xs gap-2.5",
        "title": "text-(length:--ui-font-size-md)/(--ui-font-line-height-reset)",
        "description": "text-(length:--ui-font-size-md)/(--ui-font-line-height-3xs)",
        "avatarSize": "xl"
      }
    },
    "orientation": {
      "horizontal": {
        "root": "items-center",
        "actions": "items-center"
      },
      "vertical": {
        "root": "items-start",
        "actions": "items-start mt-2"
      }
    },
    "title": {
      "true": {
        "description": "mt-1"
      }
    },
    "inverted": {
      "true": "",
      "false": ""
    }
  },
  "compoundVariants": [
    {
      "inverted": true,
      "color": "air-primary" as typeof color[number],
      "class": {
        "root": "style-filled-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-success" as typeof color[number],
      "class": {
        "root": "style-filled-success-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-alert" as typeof color[number],
      "class": {
        "root": "style-filled-alert-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-copilot" as typeof color[number],
      "class": {
        "root": "style-filled-copilot-inverted"
      }
    },
    {
      "inverted": true,
      "color": "air-primary-warning" as typeof color[number],
      "class": {
        "root": "style-filled-warning-inverted"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-secondary-accent" as typeof color[number],
    "size": "md" as typeof size[number],
    "inverted": false
  }
}