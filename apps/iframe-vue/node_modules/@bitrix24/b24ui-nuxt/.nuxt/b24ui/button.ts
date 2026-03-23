const color = [
  "air-primary",
  "air-primary-success",
  "air-primary-alert",
  "air-primary-copilot",
  "air-secondary",
  "air-secondary-alert",
  "air-secondary-accent",
  "air-secondary-accent-1",
  "air-secondary-accent-2",
  "air-secondary-no-accent",
  "air-tertiary",
  "air-tertiary-accent",
  "air-tertiary-no-accent",
  "air-selection",
  "air-boost",
  "default",
  "danger",
  "success",
  "warning",
  "primary",
  "secondary",
  "collab",
  "ai",
  "link"
] as const

const depth = [
  "light",
  "normal",
  "dark"
] as const

const size = [
  "xss",
  "xs",
  "sm",
  "md",
  "lg",
  "xl"
] as const

export default {
  "slots": {
    "base": [
      "ui-btn",
      "font-[family-name:var(--ui-font-family-primary)]",
      "select-none cursor-pointer inline-flex items-center",
      "relative",
      "outline-transparent focus-visible:outline-2 focus-visible:outline-offset-2",
      "disabled:cursor-not-allowed aria-disabled:cursor-not-allowed disabled:opacity-30 aria-disabled:opacity-30",
      "transition duration-0 ease-linear",
      "border-(length:--ui-btn-border-width)",
      "text-(--ui-btn-color) bg-(--ui-btn-background) border-(--ui-btn-border-color)",
      "hover:text-(--ui-btn-color-hover) hover:bg-(--ui-btn-background-hover) hover:border-(--ui-btn-border-color-hover)",
      "focus:text-(--ui-btn-color-hover) focus:bg-(--ui-btn-background-hover) focus:border-(--ui-btn-border-color-hover)",
      "active:text-(--ui-btn-color-active) active:bg-(--ui-btn-background-active) active:border-(--ui-btn-border-color-active)",
      "disabled:bg-(--ui-btn-background) disabled:border-(--ui-btn-border-color)",
      "aria-disabled:bg-(--ui-btn-background) aria-disabled:border-(--ui-btn-border-color)",
      "focus-visible:outline-(--ui-btn-background)",
      "ring-(--ui-btn-background-hover) focus:outline-none focus-visible:ring-(--ui-btn-background-hover)",
      "h-(--ui-btn-height)",
      "text-(length:--ui-btn-font-size) leading-(--ui-btn-height) font-(--ui-btn-font-weight)",
      ""
    ],
    "baseLoading": "h-full w-full absolute inset-0 flex flex-row flex-nowrap items-center justify-center",
    "baseLoadingWaitIcon": "text-(--ui-btn-color) size-[calc(var(--ui-btn-wait-icon-size)_+_7px)]",
    "baseLoadingClockIcon": "text-(--ui-btn-color) size-[calc(var(--ui-btn-wait-icon-size)_+_7px)]",
    "baseLoadingSpinnerIcon": "text-(--ui-btn-color) size-(--ui-btn-wait-icon-size) animate-spin stroke-2",
    "baseLine": "w-full inline-flex items-center justify-center gap-(--ui-btn-icon-space) ps-(--ui-btn-padding-left) pe-(--ui-btn-padding-right)",
    "label": "h-(--ui-btn-height) max-w-full inline-flex items-center tracking-(--ui-btn-letter-spacing) overflow-visible text-clip mt-(--ui-btn-title-compensation)",
    "labelInner": "truncate inline-block max-w-full mt-(--ui-btn-title-compensation)",
    "leadingIcon": "text-(--ui-btn-color) shrink-0 size-(--ui-btn-icon-size)",
    "leadingAvatar": "shrink-0 me-[4px]",
    "leadingAvatarSize": "",
    "trailingIcon": "text-(--ui-btn-color) shrink-0 size-(--ui-btn-icon-size) mt-(--ui-btn-title-compensation)",
    "safeList": "invisible"
  },
  "variants": {
    "buttonGroup": {
      "horizontal": "focus-visible:outline-none ring ring-inset ring-0 focus-visible:ring-2 group-[.is-button-group]/items:not-only:first:rounded-e-none group-[.is-button-group]/items:not-only:last:rounded-s-none group-[.is-button-group]/items:not-last:not-first:rounded-none group-[.is-button-group]/items:not-only:first:border-e-0 group-[.is-button-group]/items:not-only:not-first:border-s-0 focus-visible:z-[1]",
      "vertical": "focus-visible:outline-none ring ring-inset ring-0 focus-visible:ring-2 not-only:first:rounded-b-none not-only:last:rounded-t-none not-last:not-first:rounded-none focus-visible:z-[1]"
    },
    "noSplit": {
      "false": "group-[.is-button-group]/items:not-only:not-first:after:content-[''] group-[.is-button-group]/items:not-only:not-first:after:absolute group-[.is-button-group]/items:not-only:not-first:after:top-[7px] group-[.is-button-group]/items:not-only:not-first:after:bottom-[6px] group-[.is-button-group]/items:not-only:not-first:after:left-0 group-[.is-button-group]/items:not-only:not-first:after:w-px group-[.is-button-group]/items:not-only:not-first:after:bg-current/30"
    },
    "color": {
      "air-primary": "--style-filled",
      "air-primary-success": "--style-filled-success",
      "air-primary-alert": "--style-filled-alert",
      "air-primary-copilot": "--style-filled-copilot",
      "air-secondary": "--style-tinted",
      "air-secondary-alert": "--style-tinted-alert",
      "air-secondary-accent": "--style-outline",
      "air-secondary-accent-1": "--style-outline-accent-1",
      "air-secondary-accent-2": "--style-outline-accent-2",
      "air-secondary-no-accent": "--style-outline-no-accent",
      "air-tertiary": "--style-plain",
      "air-tertiary-accent": "--style-plain-accent",
      "air-tertiary-no-accent": "--style-plain-no-accent",
      "air-selection": "--style-selection",
      "air-boost": {
        "base": "--style-filled-boost bg-transparent hover:bg-transparent focus:bg-transparent active:bg-transparent disabled:bg-transparent aria-disabled:bg-transparent from-0% via-58.65% to-100% bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] from-(--ui-color-design-filled-boost-bg-gradient-1) via-(--ui-color-design-filled-boost-bg-gradient-2) to-(--ui-color-design-filled-boost-bg-gradient-3) hover:bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] hover:from-(--hover-color-1) via-(--hover-color-2) hover:via-58.65% hover:to-(--hover-color-3) focus:bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] focus:from-(--hover-color-1) via-(--hover-color-2) focus:via-58.65% to-(--hover-color-3) active:bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] active:from-(--active-color-1) via-(--active-color-2) active:via-58.65% to-(--active-color-3) disabled:bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] disabled:from-(--ui-color-design-filled-boost-bg-gradient-1) via-(--ui-color-design-filled-boost-bg-gradient-2) to-(--ui-color-design-filled-boost-bg-gradient-3) aria-disabled:bg-radial-[110.42%_110.42%_at_-10.42%_31.25%] aria-disabled:from-(--ui-color-design-filled-boost-bg-gradient-1) aria-disabled:via-(--ui-color-design-filled-boost-bg-gradient-2) aria-disabled:to-(--ui-color-design-filled-boost-bg-gradient-3)"
      },
      "default": "",
      "danger": "",
      "success": "",
      "warning": "",
      "primary": "",
      "secondary": "",
      "collab": "",
      "ai": "",
      "link": ""
    },
    "depth": {
      "light": "",
      "normal": "",
      "dark": ""
    },
    "size": {
      "xss": {
        "base": "ui-btn-xss",
        "leadingAvatarSize": "2xs"
      },
      "xs": {
        "base": "ui-btn-xs",
        "leadingAvatarSize": "2xs"
      },
      "sm": {
        "base": "ui-btn-sm",
        "leadingAvatarSize": "xs"
      },
      "md": {
        "base": "ui-btn-md",
        "leadingAvatarSize": "xs"
      },
      "lg": {
        "base": "ui-btn-lg",
        "leadingAvatarSize": "md"
      },
      "xl": {
        "base": "ui-btn-xl",
        "leadingAvatarSize": "md"
      }
    },
    "block": {
      "true": {
        "base": "w-full"
      }
    },
    "rounded": {
      "true": "rounded-(--ui-border-radius-lg)",
      "false": "rounded-(--ui-btn-radius)"
    },
    "leading": {
      "true": ""
    },
    "active": {
      "true": {
        "base": ""
      },
      "false": {
        "base": ""
      }
    },
    "useLabel": {
      "true": "",
      "false": {
        "baseLine": "ps-[4px] pe-[4px]",
        "leadingAvatar": "me-0"
      }
    },
    "useDropdown": {
      "true": ""
    },
    "useWait": {
      "true": ""
    },
    "useClock": {
      "true": ""
    },
    "loading": {
      "true": ""
    },
    "normalCase": {
      "true": "normal-case",
      "false": "uppercase"
    },
    "isAir": {
      "true": "--air",
      "false": ""
    }
  },
  "compoundVariants": [
    {
      "color": "default" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-default-light"
    },
    {
      "color": "default" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-default"
    },
    {
      "color": "default" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-default-dark"
    },
    {
      "color": "danger" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-danger-light"
    },
    {
      "color": "danger" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-danger"
    },
    {
      "color": "danger" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-danger-dark"
    },
    {
      "color": "success" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-success-light"
    },
    {
      "color": "success" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-success"
    },
    {
      "color": "success" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-success-dark"
    },
    {
      "color": "warning" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-warning-light"
    },
    {
      "color": "warning" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-warning"
    },
    {
      "color": "warning" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-warning-dark"
    },
    {
      "color": "primary" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-primary-light"
    },
    {
      "color": "primary" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-primary"
    },
    {
      "color": "primary" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-primary-dark"
    },
    {
      "color": "secondary" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-secondary-light"
    },
    {
      "color": "secondary" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-secondary"
    },
    {
      "color": "secondary" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-secondary-dark"
    },
    {
      "color": "collab" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-collab-light"
    },
    {
      "color": "collab" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-collab"
    },
    {
      "color": "collab" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-collab-dark"
    },
    {
      "color": "ai" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-ai-light"
    },
    {
      "color": "ai" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-ai"
    },
    {
      "color": "ai" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-ai-dark"
    },
    {
      "color": "link" as typeof color[number],
      "depth": "light" as typeof depth[number],
      "class": "--style-link-light"
    },
    {
      "color": "link" as typeof color[number],
      "depth": "normal" as typeof depth[number],
      "class": "--style-link"
    },
    {
      "color": "link" as typeof color[number],
      "depth": "dark" as typeof depth[number],
      "class": "--style-link-dark"
    },
    {
      "leading": true,
      "useLabel": true,
      "useDropdown": false,
      "class": {
        "baseLine": "ps-[calc(var(--ui-btn-padding-left)_-_var(--ui-btn-icon-compensation))]"
      }
    },
    {
      "leading": false,
      "useLabel": true,
      "useDropdown": true,
      "class": {
        "baseLine": "pe-[calc(var(--ui-btn-padding-right)_-_var(--ui-btn-icon-compensation))]"
      }
    },
    {
      "leading": true,
      "useLabel": true,
      "useDropdown": true,
      "class": {
        "baseLine": "ps-[calc(var(--ui-btn-padding-left)_-_var(--ui-btn-icon-compensation))] pe-[calc(var(--ui-btn-padding-right)_-_var(--ui-btn-icon-compensation))]"
      }
    }
  ],
  "defaultVariants": {
    "size": "md" as typeof size[number],
    "color": "air-secondary-no-accent" as typeof color[number],
    "depth": "normal" as typeof depth[number],
    "normalCase": true,
    "isAir": true
  }
}