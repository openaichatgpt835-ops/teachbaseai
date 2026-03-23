const animation = [
  "loading",
  "carousel",
  "carousel-inverse",
  "swing",
  "elastic"
] as const

const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-primary-warning",
  "air-secondary",
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

const step = [
  "active",
  "first",
  "other",
  "last"
] as const

const orientation = [
  "horizontal",
  "vertical"
] as const

export default {
  "slots": {
    "root": "gap-2",
    "base": [
      "relative overflow-hidden",
      "rounded-(--ui-border-radius-pill)",
      "bg-(--ui-color-base-5)"
    ],
    "indicator": "rounded-(--ui-border-radius-pill) size-full transition-transform duration-200 ease-out bg-(--b24ui-background)",
    "status": "flex justify-end text-(--b24ui-typography-legend-color) transition-[width] duration-200",
    "steps": "grid items-end text-(--b24ui-typography-legend-color)",
    "step": "truncate text-end row-start-1 col-start-1 transition-opacity" as typeof step[number]
  },
  "variants": {
    "animation": {
      "loading": "",
      "carousel": "",
      "carousel-inverse": "",
      "swing": "",
      "elastic": ""
    },
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
        "status": "text-(length:--ui-font-size-xs)/(--ui-font-line-height-sm)",
        "steps": "text-(length:--ui-font-size-xs)/(--ui-font-line-height-sm)"
      },
      "sm": {
        "status": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)",
        "steps": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)"
      },
      "md": {
        "status": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)",
        "steps": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)"
      },
      "lg": {
        "status": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)",
        "steps": "text-(length:--ui-font-size-sm)/(--ui-font-line-height-sm)"
      }
    },
    "step": {
      "active": {
        "step": "opacity-100" as typeof step[number]
      },
      "first": {
        "step": "opacity-100 text-(--b24ui-typography-legend-color)" as typeof step[number]
      },
      "other": {
        "step": "opacity-0" as typeof step[number]
      },
      "last": {
        "step": ""
      }
    },
    "orientation": {
      "horizontal": {
        "root": "w-full flex flex-col",
        "base": "w-full",
        "status": "flex-row"
      },
      "vertical": {
        "root": "h-full flex flex-row-reverse",
        "base": "h-full",
        "status": "flex-col min-w-[32px]"
      }
    },
    "inverted": {
      "true": {
        "status": "self-end"
      }
    }
  },
  "compoundVariants": [
    {
      "inverted": true,
      "orientation": "horizontal" as typeof orientation[number],
      "class": {
        "step": "text-start" as typeof step[number],
        "status": "flex-row-reverse"
      }
    },
    {
      "inverted": true,
      "orientation": "vertical" as typeof orientation[number],
      "class": {
        "steps": "items-start",
        "status": "flex-col-reverse"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": "h-[2px]"
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": "h-[4px]"
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": "h-[8px]"
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": "h-[12px]"
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": "w-[2px]"
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": "w-[4px]"
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": "w-[8px]"
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": "w-[12px]"
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "animation": "carousel" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[carousel_2s_ease-in-out_infinite] data-[state=indeterminate]:rtl:animate-[carousel-rtl_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "animation": "carousel" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[carousel-vertical_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "animation": "carousel-inverse" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[carousel-inverse_2s_ease-in-out_infinite] data-[state=indeterminate]:rtl:animate-[carousel-inverse-rtl_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "animation": "carousel-inverse" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[carousel-inverse-vertical_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "animation": "swing" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[swing_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "animation": "swing" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[swing-vertical_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "animation": "elastic" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[elastic_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "animation": "elastic" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[elastic-vertical_2s_ease-in-out_infinite]"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "animation": "loading" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[progressbar-loading_2s_infinite]"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "animation": "loading" as typeof animation[number],
      "class": {
        "indicator": "data-[state=indeterminate]:animate-[progressbar-loading-vertical_2s_infinite]"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number],
    "animation": "loading" as typeof animation[number],
    "size": "md" as typeof size[number]
  }
}