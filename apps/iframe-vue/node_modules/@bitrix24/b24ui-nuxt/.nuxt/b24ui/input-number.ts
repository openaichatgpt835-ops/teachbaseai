const size = [
  "xss",
  "xs",
  "sm",
  "md",
  "lg",
  "xl"
] as const

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

const orientation = [
  "horizontal",
  "vertical"
] as const

export default {
  "slots": {
    "root": "isolate relative inline-flex items-center",
    "base": "w-full py-0 border-0 focus:outline-none disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-30 disabled:resize-none appearance-none transition duration-300 ease-linear ring ring-inset ring-(--ui-color-design-outline-stroke) text-(--ui-color-base-1) style-blurred-bg-input placeholder:text-(--ui-color-design-plain-na-content-secondary) hover:text-(--ui-color-base-1) focus:text-(--ui-color-base-1) active:text-(--ui-color-base-1) font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-regular) align-middle text-ellipsis whitespace-nowrap focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-(--b24ui-border-color)",
    "increment": "absolute flex items-center",
    "decrement": "absolute flex items-center",
    "tag": "pointer-events-none select-none absolute z-10 -top-[7px] right-[14px] flex flex-col justify-center items-center"
  },
  "variants": {
    "buttonGroup": {
      "horizontal": {
        "root": "group leading-none has-focus-visible:z-[1]",
        "base": "focus-visible:outline-none ring ring-inset ring-1 focus-visible:ring-2 group-not-only:group-first:rounded-e-3xl group-not-only:group-last:rounded-s-none group-not-last:group-not-first:rounded-none group-not-only:group-first:rounded-e-none group-not-only:group-last:rounded-s-none group-not-last:group-not-first:rounded-none group-not-only:group-first:border-e-0 group-not-only:group-not-first:border-s-0"
      },
      "vertical": {
        "root": "group has-focus-visible:z-[1]",
        "base": "focus-visible:outline-none ring ring-inset ring-1 focus-visible:ring-2 group-not-only:group-first:rounded-b-none group-not-only:group-last:rounded-t-none group-not-last:group-not-first:rounded-none"
      }
    },
    "noSplit": {
      "false": "group-not-only:not-first:after:content-[''] group-not-only:not-first:after:absolute group-not-only:not-first:after:top-[7px] group-not-only:not-first:after:bottom-[6px] group-not-only:not-first:after:left-0 group-not-only:not-first:after:w-px group-not-only:not-first:after:bg-current/30"
    },
    "size": {
      "xss": "px-2 h-[20px] gap-1 text-(length:--ui-font-size-4xs)/[normal]",
      "xs": "px-2 h-[24px] gap-1 text-(length:--ui-font-size-xs)/[normal]",
      "sm": "px-2.5 h-[28px] gap-1.5 text-(length:--ui-font-size-sm)/[normal]",
      "md": "px-2.5 h-[34px] gap-1.5 text-(length:--ui-font-size-lg)/[normal]",
      "lg": "px-3 h-[38px] gap-2 text-(length:--ui-font-size-lg)/[normal]",
      "xl": "px-3 h-[46px] gap-2 text-(length:--ui-font-size-2xl)/[normal]"
    },
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
    "rounded": {
      "true": "rounded-(--ui-border-radius-3xl)",
      "false": "rounded-(--ui-border-radius-sm)"
    },
    "noPadding": {
      "true": {
        "base": "px-0"
      }
    },
    "noBorder": {
      "true": "ring-0 focus-visible:ring-0 style-transparent-bg"
    },
    "underline": {
      "true": "ring-0 focus-visible:ring-0 style-transparent-bg border-b-1 border-b-(--ui-color-design-outline-stroke) rounded-none"
    },
    "disabled": {
      "true": {
        "increment": "cursor-not-allowed",
        "decrement": "cursor-not-allowed"
      }
    },
    "orientation": {
      "horizontal": {
        "base": "text-center",
        "increment": "inset-y-0 end-0 py-0 pe-0 [&>button]:p-1",
        "decrement": "inset-y-0 start-0 py-0 ps-0 [&>button]:p-1"
      },
      "vertical": {
        "increment": "top-1 end-0 pe-1 [&>button]:p-0",
        "decrement": "bottom-1 end-0 pe-1 [&>button]:p-0"
      }
    },
    "highlight": {
      "true": ""
    }
  },
  "compoundVariants": [
    {
      "noBorder": false,
      "underline": false,
      "class": ""
    },
    {
      "highlight": true,
      "noBorder": false,
      "underline": false,
      "class": "ring ring-inset ring-(--b24ui-border-color)"
    },
    {
      "noBorder": false,
      "underline": true,
      "class": "focus-visible:border-(--b24ui-border-color)"
    },
    {
      "highlight": true,
      "noBorder": false,
      "underline": true,
      "class": "border-b-(--b24ui-border-color)"
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "rounded": true,
      "class": {
        "increment": "[&>button]:rounded-3xl",
        "decrement": "[&>button]:rounded-3xl"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xss" as typeof size[number],
      "class": {
        "base": "px-[24px]",
        "increment": "[&>button]:p-[2px] [&>button]:h-[24px] scale-70",
        "decrement": "[&>button]:p-[2px] [&>button]:h-[24px] scale-70"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": {
        "base": "px-[24px]",
        "increment": "[&>button]:p-[2px] [&>button]:h-[24px] scale-70",
        "decrement": "[&>button]:p-[2px] [&>button]:h-[24px] scale-70"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": {
        "base": "px-[28px]",
        "increment": "[&>button]:p-[2px] scale-70",
        "decrement": "[&>button]:p-[2px] scale-70"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": {
        "base": "px-[30px]",
        "increment": "[&>button]:p-[2px] scale-60",
        "decrement": "[&>button]:p-[2px] scale-60"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": {
        "base": "px-[30px]",
        "increment": "[&>button]:p-[2px] scale-60",
        "decrement": "[&>button]:p-[2px] scale-60"
      }
    },
    {
      "orientation": "horizontal" as typeof orientation[number],
      "size": "xl" as typeof size[number],
      "class": {
        "base": "px-[40px]",
        "increment": "[&>button]:p-[4px] scale-60",
        "decrement": "[&>button]:p-[4px] scale-60"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xss" as typeof size[number],
      "class": {
        "base": "pe-[24px]",
        "increment": "top-0 pe-0 [&>button]:h-[13px] scale-56",
        "decrement": "bottom-0 pe-0 [&>button]:h-[13px] scale-56"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xs" as typeof size[number],
      "class": {
        "base": "pe-[24px]",
        "increment": "top-0 pe-0 [&>button]:h-[13px] scale-80",
        "decrement": "bottom-0 pe-0 [&>button]:h-[13px] scale-80"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "sm" as typeof size[number],
      "class": {
        "base": "pe-[30px]",
        "increment": "top-0 pe-0 [&>button]:h-[15px] scale-80",
        "decrement": "bottom-0 pe-0 [&>button]:h-[15px] scale-80"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "md" as typeof size[number],
      "class": {
        "base": "pe-[34px]",
        "increment": "top-0 pe-0 [&>button]:h-[18px] scale-80",
        "decrement": "bottom-0 pe-0 [&>button]:h-[18px] scale-80"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "lg" as typeof size[number],
      "class": {
        "base": "pe-[38px]",
        "increment": "[&>button]:h-[16px] scale-80",
        "decrement": "[&>button]:h-[16px] scale-80"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "size": "xl" as typeof size[number],
      "class": {
        "base": "pe-[38px]",
        "increment": "[&>button]:h-[20px] scale-80",
        "decrement": "[&>button]:h-[20px] scale-80"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number],
    "size": "md" as typeof size[number]
  }
}