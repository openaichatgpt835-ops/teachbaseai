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
    "content": "light bg-(--popup-window-background-color) shadow-(--popup-window-box-shadow) rounded-(--popup-window-border-radius) will-change-[opacity] motion-safe:data-[state=open]:animate-[scale-in_100ms_ease-out] motion-safe:data-[state=closed]:animate-[scale-out_100ms_ease-in] origin-(--reka-dropdown-menu-content-transform-origin) font-[family-name:var(--ui-font-family-primary)] relative isolate px-0 py-(--menu-popup-padding) pointer-events-auto",
    "viewport": "relative w-[240px] max-h-[40vh] overflow-x-hidden overflow-y-auto scrollbar-thin",
    "arrow": "fill-(--popup-window-background-color)",
    "group": "grid",
    "label": "w-full min-w-[195px] h-(--popup-window-delimiter-section-height) px-[18px] mt-(--menu-item-block-stack-space) flex flex-row rtl:flex-row-reverse items-center select-none outline-none whitespace-nowrap text-start text-(length:--popup-window-delimiter-font-size) text-(--popup-window-delimiter-text-color) font-(--popup-window-delimiter-font-weight) after:ms-[10px] after:block after:flex-1 after:min-w-[15px] after:h-px after:bg-(--popup-window-delimiter-bg-color)",
    "separator": "my-[8px] mx-[18px] h-[1px] bg-(--popup-window-delimiter-bg-color)",
    "item": "group w-full min-w-[195px] h-[36px] px-[18px] mt-(--menu-item-block-stack-space) relative flex flex-row rtl:flex-row-reverse items-center select-none outline-none whitespace-nowrap cursor-pointer data-disabled:cursor-not-allowed data-disabled:opacity-30 text-start text-(length:--menu-popup-item-font-size) text-(--menu-popup-item-color) hover:text-(--menu-popup-item-color-hover) data-highlighted:text-(--menu-popup-item-color-hover) data-[state=open]:text-(--menu-popup-item-color-hover) hover:bg-(--menu-popup-item-bg-color-hover) data-highlighted:bg-(--menu-popup-item-bg-color-hover) data-[state=open]:bg-(--menu-popup-item-bg-color-hover) transition-colors",
    "itemLeadingIcon": "shrink-0 size-[18px] text-(--ui-color-design-plain-content-icon-secondary) group-data-highlighted:text-(--ui-color-accent-main-primary) group-data-[state=open]:text-(--ui-color-accent-main-primary) group-data-[state=checked]:text-(--ui-color-accent-main-primary) transition-colors",
    "itemLeadingAvatar": "shrink-0 size-[16px] mx-px",
    "itemLeadingAvatarSize": "2xs",
    "itemTrailing": "ml-auto rtl:ml-0 rtl:mr-auto inline-flex gap-1.5 items-center",
    "itemTrailingIcon": "shrink-0 size-[24px] text-(--ui-color-design-plain-content-icon-secondary)",
    "itemTrailingKbds": "shrink-0 hidden lg:inline-flex items-center gap-0.5",
    "itemTrailingKbdsSize": "md",
    "itemLabel": "truncate ms-[2px] -mt-px group-data-[state=checked]:text-(--ui-color-accent-main-primary)",
    "itemLabelExternalIcon": "inline-block size-[16px] text-(--ui-color-design-plain-content-icon-secondary)"
  },
  "variants": {
    "color": {
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
    },
    "active": {
      "true": {
        "item": "text-(--ui-color-accent-main-primary) hover:text-(--ui-color-accent-main-primary)",
        "itemLeadingIcon": "text-(--ui-color-accent-main-primary) hover:text-(--ui-color-accent-main-primary) group-data-[state=open]:text-(--ui-color-accent-main-primary)"
      },
      "false": {}
    },
    "loading": {
      "true": {
        "itemLeadingIcon": "animate-spin"
      }
    }
  },
  "compoundVariants": [
    {
      "color": [
        "air-primary" as typeof color[number],
        "air-primary-success" as typeof color[number],
        "air-primary-alert" as typeof color[number],
        "air-primary-copilot" as typeof color[number],
        "air-primary-warning" as typeof color[number]
      ],
      "active": false,
      "class": {
        "item": "text-(--b24ui-background) data-highlighted:text-(--b24ui-background-hover) data-[state=open]:text-(--b24ui-background-hover)",
        "itemLeadingIcon": "text-(--b24ui-background) group-data-highlighted:text-(--b24ui-background-hover) group-data-[state=open]:text-(--b24ui-background-hover)"
      }
    },
    {
      "color": [
        "air-primary" as typeof color[number],
        "air-primary-success" as typeof color[number],
        "air-primary-alert" as typeof color[number],
        "air-primary-copilot" as typeof color[number],
        "air-primary-warning" as typeof color[number]
      ],
      "active": true,
      "class": {
        "item": "text-(--b24ui-background-active)",
        "itemLeadingIcon": "text-(--b24ui-background-active) group-data-[state=open]:text-(--b24ui-background-active)"
      }
    },
    {
      "color": "default" as typeof color[number],
      "active": false,
      "class": ""
    },
    {
      "color": "default" as typeof color[number],
      "active": true,
      "class": ""
    },
    {
      "color": [
        "danger" as typeof color[number],
        "success" as typeof color[number],
        "warning" as typeof color[number],
        "primary" as typeof color[number],
        "secondary" as typeof color[number],
        "collab" as typeof color[number],
        "ai" as typeof color[number]
      ],
      "active": false,
      "class": {
        "item": "text-(--b24ui-background-active) data-highlighted:text-(--b24ui-background-hover) data-[state=open]:text-(--b24ui-background-hover)",
        "itemLeadingIcon": "text-(--b24ui-icon) group-data-highlighted:text-(--b24ui-icon) group-data-[state=open]:text-(--b24ui-icon)"
      }
    },
    {
      "color": [
        "danger" as typeof color[number],
        "success" as typeof color[number],
        "warning" as typeof color[number],
        "primary" as typeof color[number],
        "secondary" as typeof color[number],
        "collab" as typeof color[number],
        "ai" as typeof color[number]
      ],
      "active": true,
      "class": {
        "item": "text-(--b24ui-background-active)",
        "itemLeadingIcon": "text-(--b24ui-background-active) group-data-[state=open]:text-(--b24ui-background-active)"
      }
    }
  ],
  "defaultVariants": {}
}