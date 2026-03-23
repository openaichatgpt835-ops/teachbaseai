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
  "card",
  "table"
] as const

const orientation = [
  "horizontal",
  "vertical"
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
    "root": "relative",
    "fieldset": "flex",
    "legend": "mb-1.5 block text-(--b24ui-typography-label-color)",
    "item": "flex items-start",
    "base": "cursor-pointer rounded-(--ui-border-radius-pill) ring ring-inset ring-(--ui-color-base-5) outline-(--ui-color-background-transparent) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--b24ui-background)",
    "indicator": "flex items-center justify-center size-full rounded-(--ui-border-radius-pill) after:bg-(--b24ui-color) after:rounded-(--ui-border-radius-pill) bg-(--b24ui-background)" as typeof indicator[number],
    "container": "flex items-center",
    "wrapper": "font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-regular) w-full",
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
      "list": {},
      "card": {
        "item": "cursor-pointer items-start border border-(--ui-color-design-outline-na-stroke) bg-(--ui-color-design-outline-na-bg) has-data-[state=checked]:border-(--b24ui-border-color)"
      },
      "table": {
        "item": "cursor-pointer border border-(--ui-color-design-outline-na-stroke) bg-(--ui-color-design-outline-na-bg) has-data-[state=checked]:bg-(--b24ui-background)/24 has-data-[state=checked]:border-(--b24ui-border-color) has-data-[state=checked]:text-(--b24ui-color) has-data-[state=checked]:z-[1]"
      }
    },
    "orientation": {
      "horizontal": {
        "fieldset": "flex-row",
        "root": "me-2"
      },
      "vertical": {
        "fieldset": "flex-col"
      }
    },
    "indicator": {
      "start": {
        "item": "flex-row",
        "base": "me-2"
      },
      "end": {
        "item": "flex-row-reverse",
        "base": "ms-2"
      },
      "hidden": {
        "base": "sr-only",
        "wrapper": "text-center"
      }
    },
    "size": {
      "xs": {
        "fieldset": "gap-x-[12px] gap-y-[4px]",
        "legend": "text-(length:--ui-font-size-xs)",
        "base": "size-[12px]",
        "item": "text-(length:--ui-font-size-xs)",
        "label": "leading-[11px]",
        "container": "h-[12px]",
        "indicator": "after:size-[4px]" as typeof indicator[number]
      },
      "sm": {
        "fieldset": "gap-x-[14px] gap-y-[6px]",
        "legend": "text-(length:--ui-font-size-xs)",
        "base": "size-[14px]",
        "item": "text-(length:--ui-font-size-sm)",
        "label": "leading-[14px]",
        "container": "h-[14px]",
        "indicator": "after:size-[6px]" as typeof indicator[number]
      },
      "md": {
        "fieldset": "gap-x-[16px] gap-y-[8px]",
        "legend": "text-(length:--ui-font-size-sm)",
        "base": "size-[16px]",
        "item": "text-(length:--ui-font-size-lg)",
        "label": "leading-[15px]",
        "container": "h-[16px]",
        "indicator": "after:size-[6px]" as typeof indicator[number]
      },
      "lg": {
        "fieldset": "gap-x-[16px] gap-y-[8px]",
        "legend": "text-(length:--ui-font-size-sm)",
        "base": "size-[20px]",
        "item": "text-(length:--ui-font-size-xl)",
        "label": "leading-[18px]",
        "container": "h-[20px]",
        "indicator": "after:size-[8px]" as typeof indicator[number]
      }
    },
    "disabled": {
      "true": {
        "base": "cursor-not-allowed opacity-30",
        "label": "cursor-not-allowed opacity-30"
      }
    },
    "required": {
      "true": {
        "label": "after:content-['*'] after:ms-0.5 after:text-(--ui-color-accent-main-alert)"
      }
    }
  },
  "compoundVariants": [
    {
      "size": "xs" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "item": "px-[13px] py-[7px] rounded-(--ui-border-radius-xs)"
      }
    },
    {
      "size": "sm" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "item": "px-[13px] py-[9px] rounded-(--ui-border-radius-sm)"
      }
    },
    {
      "size": "md" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "item": "px-[17px] py-[10px] rounded-(--ui-border-radius-md)"
      }
    },
    {
      "size": "lg" as typeof size[number],
      "variant": "card" as typeof variant[number],
      "class": {
        "item": "px-[23px] py-[12px] rounded-(--ui-border-radius-md)"
      }
    },
    {
      "size": "xs" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "class": {
        "item": "px-[13px] py-[7px]"
      }
    },
    {
      "size": "sm" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "class": {
        "item": "px-[13px] py-[9px]"
      }
    },
    {
      "size": "md" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "class": {
        "item": "px-[17px] py-[10px]"
      }
    },
    {
      "size": "lg" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "class": {
        "item": "px-[23px] py-[12px]"
      }
    },
    {
      "size": "xs" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "orientation": "horizontal" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-s-(--ui-border-radius-xs) last-of-type:rounded-e-(--ui-border-radius-xs)",
        "fieldset": "gap-0 -space-x-px"
      }
    },
    {
      "size": "xs" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "orientation": "vertical" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-t-(--ui-border-radius-xs) last-of-type:rounded-b-(--ui-border-radius-xs)",
        "fieldset": "gap-0 -space-y-px"
      }
    },
    {
      "size": "sm" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "orientation": "horizontal" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-s-(--ui-border-radius-sm) last-of-type:rounded-e-(--ui-border-radius-sm)",
        "fieldset": "gap-0 -space-x-px"
      }
    },
    {
      "size": "sm" as typeof size[number],
      "variant": "table" as typeof variant[number],
      "orientation": "vertical" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-t-(--ui-border-radius-sm) last-of-type:rounded-b-(--ui-border-radius-sm)",
        "fieldset": "gap-0 -space-y-px"
      }
    },
    {
      "size": [
        "lg" as typeof size[number],
        "md" as typeof size[number]
      ],
      "variant": "table" as typeof variant[number],
      "orientation": "horizontal" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-s-(--ui-border-radius-md) last-of-type:rounded-e-(--ui-border-radius-md)",
        "fieldset": "gap-0 -space-x-px"
      }
    },
    {
      "size": [
        "lg" as typeof size[number],
        "md" as typeof size[number]
      ],
      "variant": "table" as typeof variant[number],
      "orientation": "vertical" as typeof orientation[number],
      "class": {
        "item": "first-of-type:rounded-t-(--ui-border-radius-md) last-of-type:rounded-b-(--ui-border-radius-md)",
        "fieldset": "gap-0 -space-y-px"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number],
    "size": "md" as typeof size[number],
    "variant": "list" as typeof variant[number],
    "orientation": "vertical" as typeof orientation[number],
    "indicator": "start" as typeof indicator[number]
  }
}