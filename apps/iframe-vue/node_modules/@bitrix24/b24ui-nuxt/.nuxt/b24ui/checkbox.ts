const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-primary-warning",
  "default",
  "danger",
  "success",
  "warning",
  "primary",
  "secondary",
  "collab",
  "ai"
] as const

const variant = [
  "list",
  "card"
] as const

const indicator = [
  "start",
  "end",
  "hidden"
] as const

const size = [
  "xs",
  "sm",
  "md",
  "lg"
] as const

export default {
  "slots": {
    "root": "relative flex items-start",
    "base": "cursor-pointer flex items-center justify-center shrink-0 rounded-(--ui-border-radius-2xs) text-(--b24ui-typography-label-color) ring ring-inset ring-(--ui-color-base-5) focus-visible:outline-(--b24ui-border-color) outline-transparent focus-visible:outline-2 focus-visible:outline-offset-2",
    "indicator": "flex items-center justify-center size-full text-(--b24ui-color)" as typeof indicator[number],
    "container": "flex items-center",
    "icon": "shrink-0 size-full",
    "wrapper": "font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-regular)",
    "label": "cursor-pointer block text-(--b24ui-typography-label-color)",
    "description": "text-(--b24ui-typography-description-color)"
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
    "variant": {
      "list": {
        "root": ""
      },
      "card": {
        "root": "border border-(--ui-color-design-outline-na-stroke) bg-(--ui-color-design-outline-na-bg)"
      }
    },
    "indicator": {
      "start": {
        "root": "flex-row",
        "wrapper": "ms-2"
      },
      "end": {
        "root": "flex-row-reverse",
        "wrapper": "me-2"
      },
      "hidden": {
        "base": "sr-only",
        "wrapper": "text-center"
      }
    },
    "size": {
      "xs": {
        "base": "size-[12px]",
        "container": "h-[12px]",
        "wrapper": "text-(length:--ui-font-size-xs)",
        "label": "leading-[11px]"
      },
      "sm": {
        "base": "size-[14px]",
        "container": "h-[14px]",
        "wrapper": "text-(length:--ui-font-size-sm)",
        "label": "leading-[14px]"
      },
      "md": {
        "base": "size-[16px]",
        "container": "h-[16px]",
        "wrapper": "text-(length:--ui-font-size-lg)",
        "label": "leading-[15px]"
      },
      "lg": {
        "base": "size-[20px]",
        "container": "h-[20px]",
        "wrapper": "text-(length:--ui-font-size-xl)",
        "label": "leading-[18px]"
      }
    },
    "required": {
      "true": {
        "label": "after:content-['*'] after:ms-0.5 after:text-(--ui-color-accent-main-alert)"
      }
    },
    "disabled": {
      "true": {
        "base": "cursor-not-allowed opacity-30",
        "label": "cursor-not-allowed opacity-30",
        "description": "cursor-not-allowed opacity-30"
      }
    },
    "checked": {
      "true": {
        "base": "ring-1 ring-(--b24ui-background) bg-(--b24ui-background)"
      }
    }
  },
  "compoundVariants": [
    {
      "size": "xs" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "root": "px-[13px] py-[7px] rounded-(--ui-border-radius-xs)"
      }
    },
    {
      "size": "sm" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "root": "px-[13px] py-[9px] rounded-(--ui-border-radius-sm)"
      }
    },
    {
      "size": "md" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "root": "px-[17px] py-[10px] rounded-(--ui-border-radius-md)"
      }
    },
    {
      "size": "lg" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "root": "px-[23px] py-[12px] rounded-(--ui-border-radius-md)"
      }
    },
    {
      "variant": "card" as typeof variant[number],
      "checked": true,
      "class": {
        "root": "border-(--b24ui-border-color) cursor-pointer"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number],
    "size": "md" as typeof size[number],
    "variant": "list" as typeof variant[number],
    "indicator": "start" as typeof indicator[number]
  }
}