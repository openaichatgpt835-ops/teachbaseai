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

const type = [
  "file"
] as const

const colorItem = [
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
    "base": "relative inline-flex items-center group px-3 w-full py-0 border-0 focus:outline-none cursor-pointer disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-30 disabled:resize-none appearance-none transition duration-300 ease-linear ring ring-inset ring-(--ui-color-design-outline-stroke) text-(--ui-color-base-1) style-blurred-bg-input hover:text-(--ui-color-base-1) focus:text-(--ui-color-base-1) active:text-(--ui-color-base-1) font-[family-name:var(--ui-font-family-primary)] font-(--ui-font-weight-regular) align-middle text-ellipsis whitespace-nowrap focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-(--b24ui-border-color)",
    "leading": "absolute inset-y-0 start-0 flex items-center",
    "leadingIcon": "shrink-0 text-(--b24ui-icon-color)",
    "leadingAvatar": "shrink-0",
    "leadingAvatarSize": "",
    "trailing": "absolute inset-y-0 end-0 flex items-center",
    "trailingIcon": "shrink-0 text-(--b24ui-icon-color)",
    "tag": "pointer-events-none select-none absolute z-10 -top-[7px] right-[14px] flex flex-col justify-center items-center",
    "value": "truncate pointer-events-none",
    "placeholder": "truncate text-(--ui-color-design-plain-na-content-secondary)",
    "content": "light bg-(--popup-window-background-color) shadow-(--popup-window-box-shadow) rounded-(--popup-window-border-radius) will-change-[opacity] motion-safe:data-[state=open]:animate-[scale-in_100ms_ease-out] motion-safe:data-[state=closed]:animate-[scale-out_100ms_ease-in] origin-(--reka-dropdown-menu-content-transform-origin) font-[family-name:var(--ui-font-family-primary)] relative isolate px-0 py-(--menu-popup-padding) pointer-events-auto",
    "viewport": "relative w-[240px] max-h-[40vh] overflow-x-hidden overflow-y-auto scrollbar-thin",
    "arrow": "fill-(--popup-window-background-color)",
    "group": "grid",
    "empty": "h-(--popup-window-delimiter-section-height) mt-(--menu-item-block-stack-space) py-[8px] select-none outline-none whitespace-nowrap text-center text-(length:--popup-window-delimiter-font-size)/(--ui-font-line-height-lg) text-(--popup-window-delimiter-text-color) font-(--popup-window-delimiter-font-weight)",
    "label": "w-full min-w-[195px] h-(--popup-window-delimiter-section-height) px-[18px] mt-(--menu-item-block-stack-space) flex flex-row rtl:flex-row-reverse items-center select-none outline-none whitespace-nowrap text-start text-(length:--popup-window-delimiter-font-size) text-(--popup-window-delimiter-text-color) font-(--popup-window-delimiter-font-weight) after:ms-[10px] after:block after:flex-1 after:min-w-[15px] after:h-px after:bg-(--popup-window-delimiter-bg-color)",
    "separator": "my-[8px] mx-[18px] h-[1px] bg-(--popup-window-delimiter-bg-color)",
    "item": "group w-full min-w-[195px] h-[36px] px-[18px] mt-(--menu-item-block-stack-space) relative flex flex-row rtl:flex-row-reverse items-center select-none outline-none whitespace-nowrap cursor-pointer data-disabled:cursor-not-allowed data-disabled:opacity-30 text-start text-(length:--menu-popup-item-font-size) text-(--menu-popup-item-color) hover:text-(--menu-popup-item-color-hover) data-highlighted:not-data-disabled:text-(--menu-popup-item-color-hover) data-[state=open]:text-(--menu-popup-item-color-hover) data-[state=checked]:text-(--menu-popup-item-color-hover) hover:bg-(--menu-popup-item-bg-color-hover) data-highlighted:bg-(--menu-popup-item-bg-color-hover) data-[state=open]:bg-(--menu-popup-item-bg-color-hover) transition-colors",
    "itemLeadingIcon": "shrink-0 size-[18px] text-(--ui-color-design-plain-content-icon-secondary) group-data-highlighted:not-data-disabled:text-(--ui-color-accent-main-primary) group-data-[state=open]:text-(--ui-color-accent-main-primary) group-data-[state=checked]:text-(--ui-color-accent-main-primary) transition-colors",
    "itemLeadingAvatar": "shrink-0 size-[16px] mx-px",
    "itemLeadingAvatarSize": "2xs",
    "itemLeadingChip": "shrink-0 size-[16px] mx-px",
    "itemLeadingChipSize": "sm",
    "itemTrailing": "ml-auto rtl:ml-0 rtl:mr-auto inline-flex gap-1.5 items-center",
    "itemTrailingIcon": "shrink-0 size-[24px] text-(--ui-color-design-plain-content-icon-secondary)",
    "itemLabel": "truncate ms-[2px] -mt-px group-data-[state=checked]:text-(--ui-color-accent-main-primary)"
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
      "xss": {
        "base": "h-[20px] gap-1 text-(length:--ui-font-size-4xs)/[normal]",
        "leading": "px-1",
        "trailing": "px-1",
        "leadingIcon": "size-[12px]",
        "leadingAvatarSize": "3xs",
        "trailingIcon": "size-[12px]"
      },
      "xs": {
        "base": "h-[24px] gap-1 text-(length:--ui-font-size-xs)/[normal]",
        "leading": "px-1",
        "trailing": "px-1",
        "leadingIcon": "size-[14px]",
        "leadingAvatarSize": "3xs",
        "trailingIcon": "size-[14px]"
      },
      "sm": {
        "base": "h-[28px] gap-1.5 text-(length:--ui-font-size-sm)/[normal]",
        "leading": "px-1.5",
        "trailing": "px-1.5",
        "leadingIcon": "size-[16px]",
        "leadingAvatar": "size-[16px]",
        "leadingAvatarSize": "2xs",
        "trailingIcon": "size-[16px]"
      },
      "md": {
        "base": "h-[34px] gap-1.5 text-(length:--ui-font-size-lg)/[normal]",
        "leading": "px-2",
        "trailing": "px-2",
        "leadingIcon": "size-[18px]",
        "leadingAvatarSize": "2xs",
        "trailingIcon": "size-[18px]"
      },
      "lg": {
        "base": "h-[38px] gap-2 text-(length:--ui-font-size-lg)/[normal]",
        "leading": "px-2",
        "trailing": "px-2",
        "leadingIcon": "size-[22px]",
        "leadingAvatarSize": "2xs",
        "trailingIcon": "size-[22px]"
      },
      "xl": {
        "base": "h-[46px] gap-2 text-(length:--ui-font-size-2xl)/[normal]",
        "leading": "px-2",
        "trailing": "px-2",
        "leadingIcon": "size-[22px]",
        "leadingAvatarSize": "2xs",
        "trailingIcon": "size-[22px]"
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
    },
    "type": {
      "file": [
        "file:me-1.5",
        "file:text-(--ui-color-design-plain-na-content-secondary)",
        "file:outline-none"
      ]
    },
    "colorItem": {
      "air-primary": {
        "item": "style-filled"
      },
      "air-primary-success": {
        "item": "style-filled-success"
      },
      "air-primary-alert": {
        "item": "style-filled-alert"
      },
      "air-primary-copilot": {
        "item": "style-filled-copilot"
      },
      "air-primary-warning": {
        "item": "style-filled-warning"
      },
      "default": {
        "item": "style-old-default"
      },
      "danger": {
        "item": "style-old-danger"
      },
      "success": {
        "item": "style-old-success"
      },
      "warning": {
        "item": "style-old-warning"
      },
      "primary": {
        "item": "style-old-primary"
      },
      "secondary": {
        "item": "style-old-secondary"
      },
      "collab": {
        "item": "style-old-collab"
      },
      "ai": {
        "item": "style-old-ai"
      }
    }
  },
  "compoundVariants": [
    {
      "colorItem": [
        "air-primary" as typeof colorItem[number],
        "air-primary-success" as typeof colorItem[number],
        "air-primary-alert" as typeof colorItem[number],
        "air-primary-copilot" as typeof colorItem[number],
        "air-primary-warning" as typeof colorItem[number]
      ],
      "active": false,
      "class": {
        "item": "text-(--b24ui-background) data-highlighted:text-(--b24ui-background-hover) data-[state=open]:text-(--b24ui-background-hover)",
        "itemLeadingIcon": "text-(--b24ui-background) group-data-highlighted:text-(--b24ui-background-hover) group-data-[state=open]:text-(--b24ui-background-hover)"
      }
    },
    {
      "colorItem": [
        "air-primary" as typeof colorItem[number],
        "air-primary-success" as typeof colorItem[number],
        "air-primary-alert" as typeof colorItem[number],
        "air-primary-copilot" as typeof colorItem[number],
        "air-primary-warning" as typeof colorItem[number]
      ],
      "active": true,
      "class": {
        "item": "text-(--b24ui-background-active)",
        "itemLeadingIcon": "text-(--b24ui-background-active) group-data-[state=open]:text-(--b24ui-background-active)"
      }
    },
    {
      "colorItem": "default" as typeof colorItem[number],
      "active": false,
      "class": ""
    },
    {
      "colorItem": "default" as typeof colorItem[number],
      "active": true,
      "class": ""
    },
    {
      "colorItem": [
        "danger" as typeof colorItem[number],
        "success" as typeof colorItem[number],
        "warning" as typeof colorItem[number],
        "primary" as typeof colorItem[number],
        "secondary" as typeof colorItem[number],
        "collab" as typeof colorItem[number],
        "ai" as typeof colorItem[number]
      ],
      "active": false,
      "class": {
        "item": "text-(--b24ui-background-active) data-highlighted:text-(--b24ui-background-hover) data-[state=open]:text-(--b24ui-background-hover)",
        "itemLeadingIcon": "text-(--b24ui-icon) group-data-highlighted:text-(--b24ui-icon) group-data-[state=open]:text-(--b24ui-icon)"
      }
    },
    {
      "colorItem": [
        "danger" as typeof colorItem[number],
        "success" as typeof colorItem[number],
        "warning" as typeof colorItem[number],
        "primary" as typeof colorItem[number],
        "secondary" as typeof colorItem[number],
        "collab" as typeof colorItem[number],
        "ai" as typeof colorItem[number]
      ],
      "active": true,
      "class": {
        "item": "text-(--b24ui-background-active)",
        "itemLeadingIcon": "text-(--b24ui-background-active) group-data-[state=open]:text-(--b24ui-background-active)"
      }
    },
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
      "class": "focus:border-(--b24ui-border-color)"
    },
    {
      "highlight": true,
      "noBorder": false,
      "underline": true,
      "class": "border-b-(--b24ui-border-color)"
    },
    {
      "type": "file" as typeof type[number],
      "size": "xss" as typeof size[number],
      "class": "py-[2px]"
    },
    {
      "type": "file" as typeof type[number],
      "size": "xs" as typeof size[number],
      "class": "py-[4px]"
    },
    {
      "type": "file" as typeof type[number],
      "size": "sm" as typeof size[number],
      "class": "py-[5px]"
    },
    {
      "type": "file" as typeof type[number],
      "size": "md" as typeof size[number],
      "class": "py-[7px]"
    },
    {
      "type": "file" as typeof type[number],
      "size": "lg" as typeof size[number],
      "class": "py-[9px]"
    },
    {
      "type": "file" as typeof type[number],
      "size": "xl" as typeof size[number],
      "class": "py-[11px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "xss" as typeof size[number],
      "class": "ps-[20px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "xs" as typeof size[number],
      "class": "ps-[22px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "sm" as typeof size[number],
      "class": "ps-[28px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "md" as typeof size[number],
      "class": "ps-[34px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "lg" as typeof size[number],
      "class": "ps-[38px]"
    },
    {
      "leading": true,
      "noPadding": false,
      "size": "xl" as typeof size[number],
      "class": "ps-[38px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "xss" as typeof size[number],
      "class": "pe-[20px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "xs" as typeof size[number],
      "class": "pe-[22px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "sm" as typeof size[number],
      "class": "pe-[28px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "md" as typeof size[number],
      "class": "pe-[34px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "lg" as typeof size[number],
      "class": "pe-[38px]"
    },
    {
      "trailing": true,
      "noPadding": false,
      "size": "xl" as typeof size[number],
      "class": "pe-[38px]"
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
    "color": "air-primary" as typeof color[number],
    "size": "md" as typeof size[number]
  }
}