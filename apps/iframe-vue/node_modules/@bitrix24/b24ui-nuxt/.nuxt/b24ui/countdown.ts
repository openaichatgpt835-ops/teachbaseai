const size = [
  "xs",
  "sm",
  "md",
  "lg",
  "xl"
] as const

export default {
  "slots": {
    "base": "relative flex flex-row flex-nowrap items-center justify-between text-(--b24ui-typography-legend-color)",
    "label": "",
    "leadingIcon": "shrink-0",
    "leadingAvatar": "shrink-0",
    "leadingAvatarSize": "",
    "circleBase": "-scale-x-100 absolute inset-x-0 inset-y-0",
    "circleGroup": "fill-none stroke-none",
    "circleElement": "stroke-transparent stroke-1",
    "circlePath": "stroke-[7px] rotate-90 origin-center stroke-current transition-all duration-1000 ease-linear"
  },
  "variants": {
    "size": {
      "xs": {
        "base": "gap-0.5 text-(length:--ui-font-size-5xs)/(--ui-font-line-height-reset)",
        "leadingIcon": "size-sm",
        "leadingAvatarSize": "3xs"
      },
      "sm": {
        "base": "gap-1 text-(length:--ui-font-size-4xs)/(--ui-font-line-height-reset)",
        "leadingIcon": "size-sm2",
        "leadingAvatarSize": "3xs"
      },
      "md": {
        "base": "gap-1 text-(length:--ui-font-size-md)/(--ui-font-line-height-reset)",
        "leadingIcon": "size-[16px]",
        "leadingAvatarSize": "3xs"
      },
      "lg": {
        "base": "gap-1 text-(length:--ui-font-size-lg)/(--ui-font-line-height-reset)",
        "leadingIcon": "size-[22px]",
        "leadingAvatarSize": "2xs"
      },
      "xl": {
        "base": "gap-1 text-(length:--ui-font-size-xl)/(--ui-font-line-height-reset)",
        "leadingIcon": "size-[26px]",
        "leadingAvatarSize": "xs"
      }
    },
    "leading": {
      "true": ""
    },
    "useCircle": {
      "true": {
        "base": "justify-center",
        "circleBase": "size-full"
      }
    }
  },
  "compoundVariants": [
    {
      "size": "xs" as typeof size[number],
      "useCircle": true,
      "class": "text-(length:--ui-font-size-7xs)/[normal] p-0.5"
    },
    {
      "size": "sm" as typeof size[number],
      "useCircle": true,
      "class": "text-(length:--ui-font-size-6xs)/[normal] p-1.5"
    },
    {
      "size": "md" as typeof size[number],
      "useCircle": true,
      "class": "text-(length:--ui-font-size-3xs)/[normal] p-1.5"
    },
    {
      "size": "lg" as typeof size[number],
      "useCircle": true,
      "class": "text-(length:--ui-font-size-xs)/[normal] p-1.5 pb-2"
    },
    {
      "size": "xl" as typeof size[number],
      "useCircle": true,
      "class": "text-(length:--ui-font-size-sm)/[normal] p-2 pb-2.5"
    }
  ],
  "defaultVariants": {
    "size": "md" as typeof size[number]
  }
}