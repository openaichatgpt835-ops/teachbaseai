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

export default {
  "slots": {
    "root": "isolate relative inline-flex items-center w-full",
    "base": "px-3 w-full pt-[7px] pb-[8px] border-0 focus:outline-none disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-30 disabled:resize-none appearance-none transition duration-300 ease-linear ring ring-inset ring-(--ui-color-design-outline-stroke) text-(--ui-color-base-1) style-blurred-bg-input placeholder:text-(--ui-color-design-plain-na-content-secondary) hover:text-(--ui-color-base-1) focus:text-(--ui-color-base-1) active:text-(--ui-color-base-1) font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-regular) text-(length:--ui-font-size-lg)/(--ui-font-line-height-2xs) align-middle focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-(--b24ui-border-color)",
    "leading": "absolute inset-y-[7px] start-0 flex items-start px-[8px]",
    "leadingIcon": "shrink-0 size-[18px] text-(--b24ui-icon-color)",
    "leadingAvatar": "shrink-0 size-[20px]",
    "leadingAvatarSize": "2xs",
    "trailing": "absolute inset-y-[8px] end-0 flex items-start px-[6px]",
    "trailingIcon": "shrink-0 size-[18px] text-(--b24ui-icon-color)",
    "tag": "pointer-events-none select-none absolute z-10 -top-[6px] right-[12px]"
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
    "autoresize": {
      "true": {
        "base": "resize-none"
      }
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
    "leading": {
      "true": ""
    },
    "trailing": {
      "true": ""
    },
    "loading": {
      "true": ""
    },
    "highlight": {
      "true": "ring ring-inset ring-(--b24ui-border-color)"
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
      "leading": true,
      "noPadding": false,
      "class": "ps-[34px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "class": "pe-[34px]"
    },
    {
      "loading": true,
      "leading": true,
      "class": {
        "leadingIcon": "size-[21px]"
      }
    },
    {
      "loading": true,
      "leading": false,
      "trailing": true,
      "class": {
        "trailingIcon": "size-[21px]"
      }
    }
  ],
  "defaultVariants": {
    "color": "air-primary" as typeof color[number]
  }
}