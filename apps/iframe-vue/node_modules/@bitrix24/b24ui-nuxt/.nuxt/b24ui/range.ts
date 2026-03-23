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

const size = [
  "xs",
  "sm",
  "md",
  "lg"
] as const

const orientation = [
  "horizontal",
  "vertical"
] as const

export default {
  "slots": {
    "root": "relative flex items-center select-none touch-none",
    "track": "relative rounded-(--ui-border-radius-pill) bg-(--ui-color-base-5) grow overflow-hidden",
    "range": "absolute rounded-(--ui-border-radius-pill) bg-(--b24ui-background)",
    "thumb": "rounded-(--ui-border-radius-pill) bg-(--ui-color-base-white-fixed) ring-2 outline-transparent focus-visible:outline-2 focus-visible:outline-offset-2 ring-(--b24ui-background) focus-visible:outline-(--b24ui-background-hover)"
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
    "size": {
      "xs": {
        "thumb": "size-[12px]"
      },
      "sm": {
        "thumb": "size-[14px]"
      },
      "md": {
        "thumb": "size-[16px]"
      },
      "lg": {
        "thumb": "size-[20px]"
      }
    },
    "orientation": {
      "horizontal": {
        "root": "w-full",
        "range": "h-full"
      },
      "vertical": {
        "root": "flex-col h-full",
        "range": "w-full"
      }
    },
    "disabled": {
      "true": {
        "root": "opacity-30 cursor-not-allowed"
      }
    }
  },
  "compoundVariants": [
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": {
        "track": "h-[6px]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": {
        "track": "h-[7px]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": {
        "track": "h-[8px]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": {
        "track": "h-[9px]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xl" as typeof size[number],
      "class": {
        "track": "h-[10px]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": {
        "track": "w-[6px]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": {
        "track": "w-[7px]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": {
        "track": "w-[8px]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": {
        "track": "w-[9px]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xl" as typeof size[number],
      "class": {
        "track": "w-[10px]"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number],
    "size": "md" as typeof size[number]
  }
}