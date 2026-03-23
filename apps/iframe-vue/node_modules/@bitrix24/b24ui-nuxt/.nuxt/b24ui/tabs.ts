const variant = [
  "link"
] as const

const orientation = [
  "horizontal",
  "vertical"
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
    "root": [
      "style-outline-accent-2",
      "flex items-center gap-2"
    ],
    "list": "relative flex p-1 group",
    "indicator": "absolute transition-[translate,width] duration-200",
    "trigger": "group relative inline-flex items-center min-w-0 data-[state=inactive]:text-(--ui-color-design-plain-na-content) hover:data-[state=inactive]:not-disabled:text-(--ui-color-design-selection-content) font-(--ui-font-weight-medium) cursor-pointer disabled:cursor-not-allowed disabled:opacity-30 transition-colors rounded-(--ui-border-radius-md)",
    "leadingIcon": "shrink-0",
    "leadingAvatar": "shrink-0",
    "leadingAvatarSize": "",
    "label": "",
    "trailingBadge": "shrink-0",
    "trailingBadgeSize": "sm",
    "content": "focus:outline-none w-full"
  },
  "variants": {
    "variant": {
      "link": {
        "list": "border-(--ui-color-divider-vibrant-accent-more)",
        "indicator": "rounded-(--ui-border-radius-pill)",
        "trigger": "focus:outline-none"
      }
    },
    "orientation": {
      "horizontal": {
        "root": "flex-col",
        "list": "w-full",
        "indicator": "left-0 w-(--reka-tabs-indicator-size) translate-x-(--reka-tabs-indicator-position)",
        "trigger": "justify-center"
      },
      "vertical": {
        "list": "flex-col",
        "indicator": "top-0 h-(--reka-tabs-indicator-size) translate-y-(--reka-tabs-indicator-position)"
      }
    },
    "size": {
      "xss": {
        "trigger": "px-2 py-1 text-(length:--ui-font-size-4xs)/[normal] gap-1",
        "leadingIcon": "size-4",
        "leadingAvatarSize": "3xs"
      },
      "xs": {
        "trigger": "px-2 py-1 text-(length:--ui-font-size-xs)/[normal] gap-1",
        "leadingIcon": "size-4",
        "leadingAvatarSize": "3xs"
      },
      "sm": {
        "trigger": "px-2.5 py-1.5 text-(length:--ui-font-size-sm)/[normal] gap-1.5",
        "leadingIcon": "size-4",
        "leadingAvatarSize": "3xs"
      },
      "md": {
        "trigger": "px-3 py-1.5 text-(length:--ui-font-size-md)/[normal] gap-1.5",
        "leadingIcon": "size-5",
        "leadingAvatarSize": "2xs"
      },
      "lg": {
        "trigger": "px-3 py-2 text-(length:--ui-font-size-lg)/[normal] gap-2",
        "leadingIcon": "size-5",
        "leadingAvatarSize": "2xs"
      },
      "xl": {
        "trigger": "px-3 py-2 text-(length:--ui-font-size-xl)/[normal] gap-2",
        "leadingIcon": "size-6",
        "leadingAvatarSize": "xs"
      }
    }
  },
  "compoundVariants": [
    {
      "orientation": "horizontal" as typeof orientation[number],
      "variant": "link" as typeof variant[number],
      "class": {
        "list": "border-b -mb-px",
        "indicator": "-bottom-px h-px"
      }
    },
    {
      "orientation": "vertical" as typeof orientation[number],
      "variant": "link" as typeof variant[number],
      "class": {
        "list": "border-s -ms-px",
        "indicator": "-start-px w-px"
      }
    },
    {
      "variant": "link" as typeof variant[number],
      "class": {
        "indicator": "bg-(--ui-color-design-selection-content)",
        "trigger": [
          "focus-visible:ring-1 focus-visible:ring-inset",
          "data-[state=active]:text-(--b24ui-color)",
          "focus-visible:ring-(--ui-color-design-selection-content)"
        ]
      }
    }
  ],
  "defaultVariants": {
    "variant": "link" as typeof variant[number],
    "size": "md" as typeof size[number]
  }
}